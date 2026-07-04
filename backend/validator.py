"""
数据校验模块 —— 在数据流入决策层之前做完整性检查。
每个校验函数返回 (passed, warning) —— passed=False 时跳过该岗位，warning 非空时告警。
"""
import re


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


def check_score_concentration(scores: list[int], top_n: int = 10) -> str:
    """检查分数集中度——top N 里只有 1-2 个不同分数值时告警"""
    if not scores:
        return ""
    top = scores[:top_n]
    unique = len(set(top))
    if unique <= 2:
        return f"分数集中度告警: top {top_n} 集中在 {unique} 个值"
    return ""
