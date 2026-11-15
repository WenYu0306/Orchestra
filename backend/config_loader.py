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
    """展示分层阈值：high / medium；低于投递线的岗位不再分层（UI 折叠区）。

    旧版的 count / max_score 是早期规则评分系统的死配置，2026-11-14 审计删除
    （_assign_tier 只读 min_score；pydantic 忽略旧配置文件里的多余键，兼容无损）。
    """
    min_score: int


class MatchingConfig(BaseModel):
    tiers: dict[str, TierConfig]
    pending: dict[str, int]
    # 投递线：低于此分数的岗位进「低于投递线」折叠区（不自动生成招呼语、不占发送额度）
    min_apply_score: int = 40


class FakeJobDetectionConfig(BaseModel):
    """虚假招聘甄别：公司名黑名单 regex 前置（省 LLM 调用）；
    JD 内容判断由 DeepSeek（is_fake_job）单轨承担，关键词 regex 已删（2026-11-14 审计）。"""
    enabled: bool = True
    company_name_patterns: list[str] = []


class SafetyConfig(BaseModel):
    min_delay: int = 3
    max_delay: int = 8
    # 发送招呼语间隔（秒）—— 对平台可见的真实动作，需要远大于内部评分间隔
    send_delay_min: int = 45
    send_delay_max: int = 120
    # 每日发送上限（按 applied_jobs.json 里当天 status=sent 的记录计数）
    daily_send_cap: int = 25
    # 允许发送的时间窗口，如 "09:00-20:00"；留空表示不限制
    active_hours: str = ""
    headless: bool = False


class WebUIConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5001  # macOS AirPlay 接收器占用 5000
    auto_open: bool = True


class AppConfig(BaseModel):
    """顶层配置容器"""
    platform: dict[str, str]
    resume: dict[str, str]
    search: dict[str, Any]
    matching: MatchingConfig
    fake_job_detection: FakeJobDetectionConfig
    application: dict[str, Any]
    safety: SafetyConfig
    web_ui: WebUIConfig


# ============ 加载逻辑 ============

_config: Optional[AppConfig] = None
_project_root: Optional[Path] = None


def get_project_root() -> Path:
    """获取项目根目录（config.yaml 所在目录）。

    打包发布形态（pyinstaller）下 __file__ 位于打包目录内部，
    由 launcher 通过 ORCHESTRA_ROOT 指向可执行文件所在的真实目录。
    """
    global _project_root
    if _project_root is None:
        root = os.environ.get("ORCHESTRA_ROOT")
        _project_root = Path(root).resolve() if root else Path(__file__).resolve().parent.parent
    return _project_root


def _load_user_overrides(raw: dict) -> None:
    """合并设置界面写入的用户级配置（data/user_settings.yaml）。

    只覆盖 search.cities / search.primary_keywords，其余仍以 config.yaml 为准；
    config.yaml 本体不被改写（保留注释），用户设置可随时删除该文件恢复默认。
    """
    path = get_project_root() / "data" / "user_settings.yaml"
    if not path.exists():
        return
    try:
        overrides = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        print(f"⚠ user_settings.yaml 解析失败，忽略用户覆盖: {e}")
        return
    search = overrides.get("search")
    if isinstance(search, dict):
        raw.setdefault("search", {})
        for key in ("cities", "primary_keywords"):
            if key in search:
                raw["search"][key] = search[key]


def get_user_flag(name: str) -> bool:
    """读取 data/user_settings.yaml 里的顶层布尔标记（如 wizard_done）。

    与 _load_user_overrides 的 search 覆盖互不影响；文件损坏按 False 处理。
    """
    path = get_project_root() / "data" / "user_settings.yaml"
    if not path.exists():
        return False
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return bool(data.get(name, False))
    except Exception as e:
        print(f"⚠ user_settings.yaml 读取失败（{name}）: {e}")
        return False


def reload_config() -> None:
    """设置保存后调用：下次 get_config() 重新读取（含用户覆盖）"""
    global _config
    _config = None


def _load_raw_config() -> dict:
    """加载 config.yaml 原始字典"""
    config_path = get_project_root() / "config.yaml"
    if not config_path.exists():
        # 帮新人自动从模板生成
        example_path = config_path.with_name("config.yaml.example")
        import shutil
        if example_path.exists():
            shutil.copy(example_path, config_path)
            print(f"✓ 已从 config.yaml.example 生成 config.yaml，请编辑后重新启动", flush=True)
            raise SystemExit(0)
        raise FileNotFoundError(
            f"config.yaml not found at {config_path}. "
            "Copy config.yaml.example to config.yaml and edit it."
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


def get_config() -> AppConfig:
    """获取全局配置单例"""
    global _config
    if _config is None:
        _load_env()
        raw = _load_raw_config()
        _load_user_overrides(raw)

        # 构建 MatchingConfig（criteria/count/max_score 死配置已删，见 TierConfig 注释）
        matching_raw = raw.get("matching", {})
        tiers_raw = matching_raw.get("tiers", {})
        tiers = {
            "high": TierConfig(**tiers_raw.get("high", {"min_score": 80})),
            "medium": TierConfig(**tiers_raw.get("medium", {"min_score": 60})),
        }
        pending = matching_raw.get("pending", {"max_count": 5})

        _config = AppConfig(
            platform=raw.get("platform", {}),
            resume=raw.get("resume", {}),
            search=raw.get("search", {}),
            matching=MatchingConfig(
                tiers=tiers,
                pending=pending,
                min_apply_score=matching_raw.get("min_apply_score", 40),
            ),
            fake_job_detection=FakeJobDetectionConfig(**raw.get("fake_job_detection", {})),
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
