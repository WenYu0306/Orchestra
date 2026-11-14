"""record_manager 真实实现测试。

用临时目录隔离，不碰 data/ 生产文件。
覆盖：记录持久化、reset_session 不丢历史（回归：旧实现会把文件覆盖成只剩本次会话）、
30 天去重窗口、mark_sent 状态流转、send_failed 解除拉黑、损坏文件备份、待选区上限。
"""
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.record_manager import RecordManager


def _fresh_manager(tmpdir: Path) -> RecordManager:
    """构造一个指向临时目录的 RecordManager（不读写 data/ 生产文件）"""
    m = RecordManager()
    m._applied_path = tmpdir / "applied_jobs.json"
    m._pending_path = tmpdir / "pending_jobs.json"
    m._applied = []
    m._pending = []
    m._applied_companies = set()
    m._tier_counts = {"high": 0, "medium": 0, "try": 0}
    m._session_start = 0
    return m


def test_add_record_and_persist(tmp_path):
    m = _fresh_manager(tmp_path)
    r = m.add_record(company="测试公司", position="AI工程师", score=85, reason="匹配",
                     tier="high", status="dry_run", security_id="sid", encrypt_job_id="eid",
                     greeting="你好", salary="20-30K", search_city="北京", search_kw="LLM")
    assert r["salary"] == "20-30K" and r["encrypt_job_id"] == "eid"
    assert m.get_record_count() == 1
    on_disk = json.loads(m._applied_path.read_text(encoding="utf-8"))
    assert len(on_disk) == 1 and on_disk[0]["company"] == "测试公司"
    print("test_add_record_and_persist PASS")


def test_reset_session_keeps_history(tmp_path):
    """回归：旧实现 reset_session 清空内存记录，下一次 add_record 会把文件覆盖成
    只剩本次会话 → 跨会话去重失效。新实现必须保留历史。"""
    m = _fresh_manager(tmp_path)
    m.add_record("公司A", "岗位", 90, "r", "high")
    m.add_record("公司B", "岗位", 80, "r", "high")
    assert len(m.get_all_records()) == 2

    m.reset_session()
    # 会话视图清零，但历史仍在、去重仍然生效
    assert m.get_all_records() == []
    assert m.is_company_recent("公司A")

    m.add_record("公司C", "岗位", 70, "r", "medium")
    on_disk = json.loads(m._applied_path.read_text(encoding="utf-8"))
    assert len(on_disk) == 3, f"历史被覆盖！文件里只剩 {len(on_disk)} 条"
    assert m.is_company_recent("公司B")
    print("test_reset_session_keeps_history PASS")


def test_recent_window_30_days(tmp_path):
    m = _fresh_manager(tmp_path)
    old_ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 31 * 86400))
    m._applied = [{"company": "旧公司", "tier": "high", "status": "dry_run", "timestamp": old_ts}]
    m._rebuild_companies()
    assert not m.is_company_recent("旧公司")
    assert m.is_company_recent("旧公司", days=60)
    print("test_recent_window_30_days PASS")


def test_mark_sent_and_daily_count(tmp_path):
    m = _fresh_manager(tmp_path)
    m.add_record("公司A", "岗位", 90, "r", "high", encrypt_job_id="eid1")
    assert m.mark_sent("公司A", "eid1", "sent")
    rec = m._applied[-1]
    assert rec["status"] == "sent" and rec.get("sent_at")
    assert m.get_sent_count_today() == 1
    assert not m.mark_sent("不存在的公司", "eidX", "sent")
    print("test_mark_sent_and_daily_count PASS")


def test_send_failed_unblocks_company(tmp_path):
    """发送失败的公司不应被永久拉黑——下次运行可以重试"""
    m = _fresh_manager(tmp_path)
    m.add_record("失败公司", "岗位", 90, "r", "high", encrypt_job_id="eid1")
    assert m.is_company_recent("失败公司")
    m.mark_sent("失败公司", "eid1", "send_failed")
    assert not m.is_company_recent("失败公司")
    print("test_send_failed_unblocks_company PASS")


def test_corrupt_file_backed_up(tmp_path):
    m = _fresh_manager(tmp_path)
    m._applied_path.write_text("{ 这不是合法JSON", encoding="utf-8")
    m._load()
    assert m._applied == []
    backups = list(tmp_path.glob("applied_jobs.json.corrupt.*"))
    assert len(backups) == 1, "损坏文件应被备份而不是静默丢弃"
    print("test_corrupt_file_backed_up PASS")


def test_pending_cap(tmp_path):
    m = _fresh_manager(tmp_path)
    for i in range(7):
        m.add_pending(f"公司{i}", "岗位", 40 + i, "r", "低置信度")
    assert len(m.get_all_pending()) == 5
    assert m.get_all_pending()[0]["score"] == max(40 + i for i in range(7))
    print("test_pending_cap PASS")


def test_unknown_tier_normalized(tmp_path):
    m = _fresh_manager(tmp_path)
    r = m.add_record("公司X", "岗位", 90, "r", "Try")  # 错误大小写
    assert r["tier"] == "try"
    print("test_unknown_tier_normalized PASS")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_add_record_and_persist(tmp)
        test_reset_session_keeps_history(tmp)
        test_recent_window_30_days(tmp)
        test_mark_sent_and_daily_count(tmp)
        test_send_failed_unblocks_company(tmp)
        test_corrupt_file_backed_up(tmp)
        test_pending_cap(tmp)
        test_unknown_tier_normalized(tmp)
    print("8/8 passed")
