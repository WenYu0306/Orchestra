"""
数据校验模块 —— 在数据流入决策层之前做完整性检查。
两类函数：
- check_xxx: 逐岗位检查，返回 (passed, warning)
- HealthTracker: 跨调用状态追踪（fetch失败率、详情API健康度）
"""
import re


# ======== 逐岗位检查 ========

def check_city(job: dict, expected_city: str) -> tuple[bool, str]:
    """校验城市是否匹配预期"""
    actual = job.get("cityName", "")
    if actual and expected_city not in actual:
        return True, f"城市不匹配: 期望{expected_city}, 实际{actual}"
    return True, ""


def check_salary(job: dict, min_salary: int) -> tuple[bool, str]:
    """硬过滤薪资不足"""
    if min_salary <= 0:
        return True, ""
    sd = job.get("salaryDesc", "")
    if not sd:
        return True, ""
    try:
        low_str = sd.replace("K", "000").replace("k", "000").split("-")[0].strip()
        low_val = int(low_str)
        if low_val < min_salary:
            return False, f"薪资过滤: {sd}"
    except (ValueError, IndexError):
        pass
    return True, ""


def check_company(job: dict) -> tuple[bool, str]:
    """检查公司名是否为空、乱码或疑似数据提取错误"""
    co = job.get("brandName", "") or job.get("brandName", "")
    if not co:
        return True, "公司名为空"
    if co == "?":
        return True, "公司名异常: ?"
    # 误把JD正文当公司名——长度超过30个字的"公司名"一定是提取错误
    if len(co) > 30:
        return True, f"公司名异常长({len(co)}字), 可能是提取错误"
    return True, ""


def check_jd_quality(jd: str) -> tuple[bool, str]:
    """检查 JD 文本质量——太短说明只有标签拼接没有真实职位描述"""
    if not jd:
        return True, "JD为空"
    if len(jd) < 50:
        return True, f"JD过短({len(jd)}字), 仅有标签拼接"
    return True, ""


def check_score_concentration(scores: list[int], top_n: int = 10) -> str:
    """检查分数集中度——top N 里只有 1-2 个不同分数值时告警"""
    if not scores:
        return ""
    top = scores[:top_n]
    unique = len(set(top))
    if unique <= 2:
        return f"分数集中度告警: top {top_n} 集中在 {unique} 个值"
    return ""


# ======== 跨调用状态追踪 ========

class HealthTracker:
    """追踪 fetch 成功率、详情 API 健康度等跨岗位状态"""

    def __init__(self):
        self._fetch_ok = 0
        self._fetch_fail = 0
        self._detail_ok = 0
        self._detail_fail = 0
        self._company_empty = 0
        self._total_jobs = 0

    def track_fetch(self, success: bool):
        if success:
            self._fetch_ok += 1
        else:
            self._fetch_fail += 1

    def track_detail(self, success: bool):
        if success:
            self._detail_ok += 1
        else:
            self._detail_fail += 1

    def track_job(self, company_ok: bool):
        self._total_jobs += 1
        if not company_ok:
            self._company_empty += 1

    def fetch_warnings(self) -> list[str]:
        """fetch 失败率告警"""
        total = self._fetch_ok + self._fetch_fail
        if total == 0:
            return []
        rate = self._fetch_fail / total
        msgs = []
        if rate > 0.3:
            msgs.append(f"⚠️  fetch失败率过高: {self._fetch_fail}/{total} ({rate:.0%})")
        if self._fetch_fail >= 3:
            msgs.append(f"⚠️  fetch累积失败{self._fetch_fail}次, 可能触发风控")
        return msgs

    def detail_warnings(self) -> list[str]:
        """详情API健康告警"""
        total = self._detail_ok + self._detail_fail
        if total == 0:
            return []
        msgs = []
        rate = self._detail_fail / total
        if rate > 0.3:
            msgs.append(f"⚠️  详情API失败率高: {self._detail_fail}/{total} ({rate:.0%})")
        if self._detail_fail >= 5:
            msgs.append(f"⚠️  详情API可能被封, 建议切换到标签评分备选方案")
        return msgs

    def company_warnings(self) -> list[str]:
        """公司名空值率告警"""
        if self._total_jobs == 0:
            return []
        rate = self._company_empty / self._total_jobs
        if rate > 0.2:
            return [f"⚠️  公司名空值率: {self._company_empty}/{self._total_jobs} ({rate:.0%})"]
        return []
