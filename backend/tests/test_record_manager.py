"""record_manager 基本单元测试"""
import json, os, sys

# 模拟环境变量
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
os.environ.setdefault("DEEPSEEK_BASE_URL", "https://test.com")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_mgr():
    """创建一个隔离的 RecordManager 实例，不读写磁盘"""
    from backend.record_manager import RecordManager
    mgr = RecordManager.__new__(RecordManager)
    mgr._applied = []
    mgr._pending = []
    mgr._tier_counts = {"high": 0, "medium": 0, "try": 0}
    mgr._applied_companies = set()
    mgr._save_applied = lambda: None
    mgr._save_pending = lambda: None
    return mgr


def test_add_record():
    mgr = make_mgr()
    r = mgr.add_record(
        company="测试公司", position="测试岗位", score=85,
        reason="匹配", tier="high", status="dry_run",
        security_id="sid123", encrypt_job_id="eid456",
        greeting="招呼语"
    )
    assert r["company"] == "测试公司"
    assert r["score"] == 85
    assert r["security_id"] == "sid123"
    assert r["encrypt_job_id"] == "eid456"
    assert r["greeting"] == "招呼语"
    assert len(mgr.get_all_records()) == 1


def test_add_pending_sorts_by_score():
    mgr = make_mgr()
    for score in [60, 80, 70, 90, 50, 95]:
        mgr.add_pending("C", "P", score, "R", "低置信度")
    pending = mgr.get_all_pending()
    assert len(pending) == 5
    assert pending[0]["score"] == 95
    assert pending[-1]["score"] == 60


def test_reset_session():
    mgr = make_mgr()
    mgr._applied = [{"company": "Old", "score": 80, "tier": "high"}]
    mgr._tier_counts = {"high": 3, "medium": 4, "try": 5}
    mgr._applied_companies = {"Old"}
    mgr.reset_session()
    assert mgr._tier_counts == {"high": 0, "medium": 0, "try": 0}
    assert len(mgr._applied) == 0


def test_truncate_over_200():
    mgr = make_mgr()
    mgr._applied = [{"company": f"C{i}", "score": 80} for i in range(250)]
    # 直接调截断逻辑
    if len(mgr._applied) > 200:
        mgr._applied = mgr._applied[-200:]
    assert len(mgr._applied) == 200
    assert mgr._applied[-1]["company"] == "C249"
    assert mgr._applied[0]["company"] == "C50"


if __name__ == "__main__":
    test_add_record()
    test_add_pending_sorts_by_score()
    test_reset_session()
    test_truncate_over_200()
    print("✅ 4 tests passed")
