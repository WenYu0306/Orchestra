"""
平台适配器 —— 每个招聘平台只需实现 5 个抽象方法。

决策层（agent_runner._run）和评分层（matcher, vectordb）不感知平台差异，
只通过 PlatformAdapter 接口调用。

添加新平台步骤：
    1. 实现 PlatformAdapter 子类
    2. 注册到 PLATFORM_REGISTRY
    3. config.yaml 里 platform.name 改为新平台名
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class JobCard:
    """统一岗位数据模型 —— 所有平台的原始岗位都转成这个结构"""
    company: str
    position: str
    salary_desc: str = ""
    city: str = ""
    experience: str = ""
    degree: str = ""
    labels: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    welfare: list[str] = field(default_factory=list)
    security_id: str = ""
    encrypt_job_id: str = ""
    extra: dict = field(default_factory=dict)  # 平台特有的额外字段

    def to_jd_text(self) -> str:
        """拼接成评分用的 JD 文本"""
        parts = [self.position, self.salary_desc, self.city,
                 self.experience, self.degree]
        parts.extend(self.labels)
        parts.extend(self.skills)
        parts.extend(self.welfare)
        return " ".join(str(p) for p in parts if p)


class PlatformAdapter(ABC):
    """招聘平台适配器抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """平台标识，如 'boss', 'zhilian', '51job'"""

    @property
    @abstractmethod
    def login_url(self) -> str:
        """登录后目标页面 URL"""

    @property
    @abstractmethod
    def city_codes(self) -> dict[str, str]:
        """城市名 → 城市代码"""

    @abstractmethod
    async def search(self, keyword: str, city_name: str, city_code: str,
                     page: int = 1, page_size: int = 30) -> list[JobCard]:
        """搜索岗位。返回 JobCard 列表（原始数据，未评分）"""

    @abstractmethod
    async def fetch_job_detail(self, security_id: str) -> str:
        """获取完整 JD 文本"""

    @abstractmethod
    async def send_greeting(self, job_card: JobCard, greeting: str) -> dict:
        """投递/发送招呼语。返回 {'ok': bool, 'reason': str}"""

    async def verify_login(self, tab) -> bool:
        """验证登录状态 —— 各平台可覆盖。默认返回 True"""
        return True

    async def prepare_browser(self) -> dict:
        """各平台可以在启动浏览器前注入特殊配置。返回 kwargs dict"""
        return {}


# ---- 平台注册表 ----

PLATFORM_REGISTRY: dict[str, type[PlatformAdapter]] = {}


def register_platform(cls: type[PlatformAdapter]) -> type[PlatformAdapter]:
    PLATFORM_REGISTRY[cls.name] = cls
    return cls


def get_adapter(name: str) -> PlatformAdapter:
    cls = PLATFORM_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"未知平台: {name}。已注册: {list(PLATFORM_REGISTRY)}")
    return cls()
