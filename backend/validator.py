"""
数据校验模块 —— 在数据流入决策层之前做完整性检查。
只做预防性校验，不做观察性统计。每个函数返回 (passed, warning)。
"""
import re


def check_city(job: dict, expected_city: str) -> tuple[bool, str]:
    """校验城市是否匹配预期"""
    actual = job.get("cityName", "")
    if actual and expected_city not in actual:
        return False, f"城市不匹配: 期望{expected_city}, 实际{actual}"
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
        # 去掉 BOSS 自定义字体编码的特殊字符
        low_str = re.sub(r'[^\d]', '', low_str)
        if not low_str: return True, ""
        low_val = int(low_str)
        if low_val < 100:
            low_val *= 1000
        if low_val < min_salary:
            return False, f"薪资过滤: {sd}"
    except (ValueError, IndexError):
        pass
    return True, ""


def check_company(job: dict) -> tuple[bool, str]:
    """检查公司名是否为空、乱码或数据提取错误"""
    co = job.get("brandName", "")
    if not co:
        return True, "公司名为空"
    if co == "?":
        return True, "公司名异常: ?"
    if len(co) > 30:
        return True, f"公司名异常长({len(co)}字), 可能是提取错误"
    return True, ""
