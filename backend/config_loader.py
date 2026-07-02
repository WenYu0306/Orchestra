"""
配置加载器 —— 读取 config.yaml 和 .env，提供统一配置访问。

所有模块通过 get_config() 获取配置，不直接读文件。
"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel


# ============ 配置数据模型 ============

class CityConfig(BaseModel):
    name: str
    min_salary: int


class TierConfig(BaseModel):
    min_score: int
    count: int
    max_score: Optional[int] = None  # high tier has no upper bound


class MatchingCriteria(BaseModel):
    skill_overlap_weight: int = 50
    experience_relevance: int = 30
    qualification_match: int = 20
    cross_industry_bonus: bool = True
    cross_industry_bonus_value: int = 5


class MatchingConfig(BaseModel):
    criteria: MatchingCriteria
    tiers: dict[str, TierConfig]
    pending: dict[str, int]


class FakeJobDetectionConfig(BaseModel):
    enabled: bool = True
    keywords: list[str] = []
    company_name_patterns: list[str] = []


class PersonalInfoConfig(BaseModel):
    name: str = ""
    phone: str = ""
    email: str = ""
    education: str = ""
    school: str = ""
    major: str = ""
    work_status: str = ""
    work_years: str = ""
    current_company: str = ""
    expected_salary: str = ""


class SafetyConfig(BaseModel):
    min_delay: int = 3
    max_delay: int = 8
    captcha_handling: str = "pause_notify"
    headless: bool = False


class WebUIConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5000
    auto_open: bool = True


class AppConfig(BaseModel):
    """顶层配置容器"""
    platform: dict[str, str]
    resume: dict[str, str]
    search: dict[str, Any]
    matching: MatchingConfig
    fake_job_detection: FakeJobDetectionConfig
    personal_info: PersonalInfoConfig
    application: dict[str, str]
    safety: SafetyConfig
    web_ui: WebUIConfig


# ============ 加载逻辑 ============

_config: Optional[AppConfig] = None
_project_root: Optional[Path] = None


def get_project_root() -> Path:
    """获取项目根目录（config.yaml 所在目录）"""
    global _project_root
    if _project_root is None:
        # 从当前文件向上找两级：backend/config_loader.py → job-hunter/
        _project_root = Path(__file__).resolve().parent.parent
    return _project_root


def _load_raw_config() -> dict:
    """加载 config.yaml 原始字典"""
    config_path = get_project_root() / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"config.yaml not found at {config_path}. "
            "Copy config.yaml from the project template."
        )

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError("config.yaml is empty or invalid YAML")
    return raw


def _load_env(env_path: Optional[Path] = None) -> None:
    """加载 .env 环境变量"""
    if env_path is None:
        env_path = get_project_root() / ".env"

    if env_path.exists():
        load_dotenv(env_path)
    else:
        # 尝试 .env.example 作为 fallback（开发环境）
        example_path = get_project_root() / ".env.example"
        if example_path.exists():
            load_dotenv(example_path)
        # 也尝试从系统环境变量读取


def get_config() -> AppConfig:
    """获取全局配置单例"""
    global _config
    if _config is None:
        _load_env()
        raw = _load_raw_config()

        # 合并 .env 中的敏感信息到 personal_info
        raw_personal = raw.get("personal_info", {})
        raw_personal["name"] = os.getenv("NAME", raw_personal.get("name", ""))
        raw_personal["phone"] = os.getenv("PHONE", raw_personal.get("phone", ""))
        raw_personal["email"] = os.getenv("EMAIL", raw_personal.get("email", ""))

        # 构建 MatchingConfig
        matching_raw = raw.get("matching", {})
        criteria = MatchingCriteria(**matching_raw.get("criteria", {}))
        tiers_raw = matching_raw.get("tiers", {})
        tiers = {
            "high": TierConfig(**tiers_raw.get("high", {"min_score": 80, "count": 5})),
            "medium": TierConfig(**tiers_raw.get("medium", {"min_score": 60, "max_score": 79, "count": 7})),
            "try": TierConfig(**tiers_raw.get("try", {"min_score": 40, "max_score": 59, "count": 8})),
        }
        pending = matching_raw.get("pending", {"max_count": 5})

        _config = AppConfig(
            platform=raw.get("platform", {}),
            resume=raw.get("resume", {}),
            search=raw.get("search", {}),
            matching=MatchingConfig(criteria=criteria, tiers=tiers, pending=pending),
            fake_job_detection=FakeJobDetectionConfig(**raw.get("fake_job_detection", {})),
            personal_info=PersonalInfoConfig(**raw_personal),
            application=raw.get("application", {}),
            safety=SafetyConfig(**raw.get("safety", {})),
            web_ui=WebUIConfig(**raw.get("web_ui", {})),
        )
    return _config


def get_api_key(provider: str) -> str:
    """获取指定 LLM 提供商的 API Key"""
    env_map = {
        "deepseek": "DEEPSEEK_API_KEY",
        "qwen_vl": "QWEN_VL_API_KEY",
    }
    key_name = env_map.get(provider)
    if key_name is None:
        raise ValueError(f"Unknown provider: {provider}")

    api_key = os.getenv(key_name, "")
    if not api_key or api_key.startswith("your_"):
        raise ValueError(
            f"{key_name} is not set. "
            f"Copy .env.example to .env and fill in your API keys."
        )
    return api_key


def get_llm_base_url(provider: str) -> str:
    """获取指定 LLM 提供商的 Base URL"""
    url_map = {
        "deepseek": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "qwen_vl": os.getenv("QWEN_VL_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    }
    return url_map.get(provider, "")
