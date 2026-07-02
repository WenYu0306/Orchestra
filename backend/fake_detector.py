"""
虚假招聘甄别器 —— 基于规则 + LLM 双重检测。

规则层：关键词匹配、公司名模式匹配（快速过滤）
LLM 层：对不确定的 JD 调用 DeepSeek 二次确认
"""

from .config_loader import get_config


class FakeDetector:
    """
    虚假招聘检测器。

    两层过滤：
    1. 规则层（Rule-based）：关键词精确匹配，速度快，零成本
    2. LLM 层：规则不确定时调用 DeepSeek 二次判断
    """

    def __init__(self):
        config = get_config()
        fd_config = config.fake_job_detection

        self._enabled = fd_config.enabled
        self._keywords: list[str] = fd_config.keywords
        self._company_patterns: list[str] = fd_config.company_name_patterns

    def check_rule_based(self, jd_text: str, company_name: str) -> dict:
        """
        规则层检测 —— 关键词 + 公司名匹配。

        Returns:
            {
                "is_fake": bool,
                "matched_rules": [str, ...],  # 命中的规则描述
                "certainty": "high" | "uncertain",
            }
        """
        matched = []

        if not self._enabled:
            return {"is_fake": False, "matched_rules": [], "certainty": "high"}

        # 检查 JD 文本中的虚假招聘关键词
        jd_lower = jd_text.lower()
        for kw in self._keywords:
            if kw.lower() in jd_lower:
                matched.append(f"JD包含关键词: {kw}")

        # 检查公司名是否匹配培训机构模式
        company_lower = company_name.lower()
        for pattern in self._company_patterns:
            if pattern.lower() in company_lower:
                matched.append(f"公司名匹配培训模式: {pattern}")

        # 额外规则：薪资异常（如 20K-50K 的"零经验"岗位）
        if "零经验" in jd_text and "20K" in jd_text:
            matched.append("薪资虚高+零经验组合")

        is_fake = len(matched) > 0
        certainty = "high" if is_fake else "uncertain"

        return {
            "is_fake": is_fake,
            "matched_rules": matched,
            "certainty": certainty,
        }

    def is_blacklisted_company(self, company_name: str) -> bool:
        """检查公司名是否在所有模式的黑名单中"""
        if not self._enabled:
            return False

        company_lower = company_name.lower()
        for pattern in self._company_patterns:
            if pattern.lower() in company_lower:
                return True
        return False


# 全局单例
fake_detector = FakeDetector()
