"""
数据校验模块 —— 在数据流入决策层之前做完整性检查。
只做预防性校验，不做观察性统计。每个函数返回 (passed, warning)。
"""
import re


def check_city(job: dict, expected_city: str) -> tuple[bool, str]:
    """校验城市是否匹配预期。城市缺失视为不通过（无人值守时宁漏勿错）。"""
    actual = job.get("cityName", "")
    if not actual:
        return False, "城市信息缺失"
    if expected_city not in actual:
        return False, f"城市不匹配: 期望{expected_city}, 实际{actual}"
    return True, ""


# BOSS 薪资格式：20-30K / 20K-30K / 15-25 / 2-3万 / 30-50万/年 / 200-300元/天 / 面议
_DAILY_RE = re.compile(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)元/天")
_WAN_RE = re.compile(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)万")
_K_RE = re.compile(r"(\d+(?:\.\d+)?)K?\s*-\s*(\d+(?:\.\d+)?)K", re.IGNORECASE)
_BARE_RE = re.compile(r"^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)")


def _parse_salary_low(sd: str) -> int | None:
    """解析月薪下限（元）。无法解析返回 None。"""
    s = sd.replace(" ", "")
    m = _DAILY_RE.search(s)
    if m:  # 日薪按 21.75 个工作日折月薪
        return int(float(m.group(1)) * 21.75)
    m = _WAN_RE.search(s)
    if m:
        low = int(float(m.group(1)) * 10000)
        return low // 12 if "/年" in s else low
    m = _K_RE.search(s)
    if m:
        return int(float(m.group(1)) * 1000)
    m = _BARE_RE.match(s)
    if m:  # "15-25" 不带单位，BOSS 语义为 15K-25K
        v = float(m.group(1))
        return int(v * 1000) if v < 100 else int(v)
    return None


def check_salary(job: dict, min_salary: int) -> tuple[bool, str]:
    """硬过滤薪资不足。解析不了但确实写了薪资的岗位放行并告警（如「面议」）。"""
    if min_salary <= 0:
        return True, ""
    sd = job.get("salaryDesc", "")
    if not sd:
        return True, "薪资缺失"
    low_val = _parse_salary_low(sd)
    if low_val is None:
        return True, f"薪资无法解析: {sd}"
    if low_val < min_salary:
        return False, f"薪资过滤: {sd}"
    return True, ""


def check_company(job: dict, fake_patterns: list[str] | None = None) -> tuple[bool, str]:
    """校验公司名：空、乱码、超长、命中培训机构模式均不通过。"""
    co = job.get("brandName", "")
    if not co:
        return False, "公司名为空"
    if co == "?":
        return False, "公司名异常: ?"
    if len(co) > 30:
        return False, f"公司名异常长({len(co)}字), 可能是提取错误"
    for pat in fake_patterns or []:
        if pat and pat in co:
            return False, f"疑似培训机构: {co}"
    return True, ""
