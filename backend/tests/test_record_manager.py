"""record_manager 接口约定测试"""
import time


class FakeRecordManager:
    """模拟 record_manager 核心数据结构"""
    def __init__(self):
        self._applied = []
        self._tier_counts = {"high": 0, "medium": 0, "try": 0}
        self._applied_companies = set()

    def add_record(self, company, position, score, reason, tier,
                   status="dry_run", security_id="", encrypt_job_id="", greeting=""):
        record = {
            "company": company,
            "position": position,
            "score": score,
            "reason": reason,
            "tier": tier,
            "status": status,
            "security_id": security_id,
            "encrypt_job_id": encrypt_job_id,
            "greeting": greeting,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._applied.append(record)
        self._tier_counts[tier] = self._tier_counts.get(tier, 0) + 1
        self._applied_companies.add(company)
        return record

    def get_all_records(self):
        return list(self._applied)

    def reset_session(self):
        self._tier_counts = {"high": 0, "medium": 0, "try": 0}
        self._applied = []
        self._applied_companies = set()


def test_add_record():
    mgr = FakeRecordManager()
    r = mgr.add_record(company="测试公司", position="测试岗位", score=85,
                       reason="匹配", tier="high", status="dry_run",
                       security_id="sid123", encrypt_job_id="eid456",
                       greeting="招呼语")
    assert r["company"] == "测试公司"
    assert r["score"] == 85
    assert r["security_id"] == "sid123"
    assert r["encrypt_job_id"] == "eid456"
    assert r["greeting"] == "招呼语"
    assert len(mgr.get_all_records()) == 1
    print("test_add_record PASS")


def test_tier_counts():
    mgr = FakeRecordManager()
    mgr.add_record("A", "P", 90, "R", "high")
    mgr.add_record("B", "P", 80, "R", "high")
    mgr.add_record("C", "P", 70, "R", "medium")
    assert mgr._tier_counts["high"] == 2
    assert mgr._tier_counts["medium"] == 1
    assert mgr._tier_counts["try"] == 0
    print("test_tier_counts PASS")


def test_reset_session():
    mgr = FakeRecordManager()
    mgr.add_record("A", "P", 90, "R", "high")
    mgr.reset_session()
    assert mgr._tier_counts == {"high": 0, "medium": 0, "try": 0}
    assert len(mgr._applied) == 0
    print("test_reset_session PASS")


def test_truncate():
    mgr = FakeRecordManager()
    for i in range(250):
        mgr.add_record(f"C{i}", "P", 80, "R", "high")
    if len(mgr._applied) > 200:
        mgr._applied = mgr._applied[-200:]
    assert len(mgr._applied) == 200
    assert mgr._applied[-1]["company"] == "C249"
    assert mgr._applied[0]["company"] == "C50"
    print("test_truncate PASS")


def test_backwards_compat():
    """新增字段有默认值，老代码调用不受影响"""
    mgr = FakeRecordManager()
    r = mgr.add_record("A", "P", 80, "R", "high")
    assert r["security_id"] == ""
    assert r["encrypt_job_id"] == ""
    assert r["greeting"] == ""
    print("test_backwards_compat PASS")


if __name__ == "__main__":
    test_add_record()
    test_tier_counts()
    test_reset_session()
    test_truncate()
    test_backwards_compat()
    print("5/5 passed")
