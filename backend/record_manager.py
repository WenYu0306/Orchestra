"""
投递记录管理器 —— 读写 applied_jobs.json 和 pending_jobs.json。

所有记录以本地 JSON 文件存储，启动时加载到内存，写入时原子更新。
"""

import json
import os
import time
from pathlib import Path
from typing import Any
from threading import Lock

from .config_loader import get_config, get_project_root


class RecordManager:
    """
    管理投递记录和待选区。

    - applied_jobs.json: 已投递的职位列表
    - pending_jobs.json: 待选区职位列表（最多5个）
    """

    def __init__(self):
        config = get_config()
        project_root = get_project_root()

        self._applied_path = project_root / config.application.get("applied_log_path", "data/applied_jobs.json")
        self._pending_path = project_root / config.application.get("pending_log_path", "data/pending_jobs.json")

        self._applied: list[dict[str, Any]] = []
        self._pending: list[dict[str, Any]] = []
        self._lock = Lock()

        self._applied_path.parent.mkdir(parents=True, exist_ok=True)
        self._pending_path.parent.mkdir(parents=True, exist_ok=True)

        self._load()

        # 分层计数器
        self._tier_counts: dict[str, int] = {"high": 0, "medium": 0, "try": 0}
        self._applied_companies: set[str] = set()

        # 从已有记录恢复计数
        for record in self._applied:
            tier = record.get("tier", "")
            if tier in self._tier_counts:
                self._tier_counts[tier] += 1
            company = record.get("company", "")
            if company:
                self._applied_companies.add(company)

    # ---- 加载与持久化 ----

    def _load(self) -> None:
        """从磁盘加载已有记录"""
        if self._applied_path.exists():
            try:
                with open(self._applied_path, "r", encoding="utf-8") as f:
                    self._applied = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self._applied = []

        if self._pending_path.exists():
            try:
                with open(self._pending_path, "r", encoding="utf-8") as f:
                    self._pending = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self._pending = []

    def _save_applied(self) -> None:
        """原子写入 applied_jobs.json，保留最近 200 条"""
        if len(self._applied) > 200:
            self._applied = self._applied[-200:]
        tmp_path = self._applied_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._applied, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self._applied_path)

    def _save_pending(self) -> None:
        """原子写入 pending_jobs.json"""
        tmp_path = self._pending_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._pending, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self._pending_path)

    # ---- 分层计数查询 ----

    def get_tier_counts(self) -> dict[str, dict[str, int]]:
        """获取各层当前计数和上限"""
        config = get_config()
        return {
            "high": {
                "current": self._tier_counts["high"],
                "max": config.matching.tiers["high"].count,
            },
            "medium": {
                "current": self._tier_counts["medium"],
                "max": config.matching.tiers["medium"].count,
            },
            "try": {
                "current": self._tier_counts["try"],
                "max": config.matching.tiers["try"].count,
            },
        }

    def is_tier_full(self, tier: str) -> bool:
        """检查某一层是否已满"""
        config = get_config()
        tier_config = config.matching.tiers.get(tier)
        if tier_config is None:
            return True
        return self._tier_counts.get(tier, 0) >= tier_config.count

    def is_all_full(self) -> bool:
        """检查是否所有层都已满"""
        return all(self.is_tier_full(t) for t in ["high", "medium", "try"])

    def is_company_applied(self, company: str) -> bool:
        """检查同公司是否已投递"""
        return company in self._applied_companies

    def is_company_recent(self, company: str, days: int = 30) -> bool:
        """检查公司最近 N 天是否已投递/招呼过"""
        cutoff = time.time() - days * 86400
        for record in self._applied:
            if record.get("company") != company:
                continue
            try:
                ts = record.get("timestamp", "")
                # 格式 "2026-07-03 14:30:00"
                record_time = time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))
                if record_time >= cutoff:
                    return True
            except Exception:
                continue
        return False

    # ---- 投递记录 CRUD ----

    def add_record(
        self,
        company: str,
        position: str,
        score: int,
        reason: str,
        tier: str,
        status: str = "success",
        security_id: str = "",
        encrypt_job_id: str = "",
        greeting: str = "",
        salary: str = "",
        search_city: str = "",
        search_kw: str = "",
    ) -> dict[str, Any]:
        """添加一条投递记录"""
        record = {
            "company": company,
            "position": position,
            "score": score,
            "reason": reason,
            "tier": tier,
            "status": status,  # success / partial / failed / dry_run
            "security_id": security_id,
            "encrypt_job_id": encrypt_job_id,
            "greeting": greeting,
            "salary": salary,
            "search_city": search_city,
            "search_kw": search_kw,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        with self._lock:
            self._applied.append(record)
            self._tier_counts[tier] = self._tier_counts.get(tier, 0) + 1
            self._applied_companies.add(company)
            self._save_applied()

        return record

    def update_record_status(self, index: int, status: str) -> None:
        """更新投递状态（如从 success 改为 failed）"""
        with self._lock:
            if 0 <= index < len(self._applied):
                self._applied[index]["status"] = status
                self._save_applied()

    def get_all_records(self) -> list[dict[str, Any]]:
        """获取全部投递记录"""
        return list(self._applied)

    def get_records_by_tier(self, tier: str) -> list[dict[str, Any]]:
        """获取某一层的投递记录"""
        return [r for r in self._applied if r.get("tier") == tier]

    # ---- 待选区 CRUD ----

    def add_pending(
        self,
        company: str,
        position: str,
        score: int,
        reason: str,
        downgrade_reason: str,
    ) -> dict[str, Any]:
        """添加到待选区，自动维护最多 5 条"""
        item = {
            "company": company,
            "position": position,
            "score": score,
            "reason": reason,
            "downgrade_reason": downgrade_reason,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        config = get_config()
        max_count = config.matching.pending.get("max_count", 5)

        with self._lock:
            self._pending.append(item)
            # 按分数降序排列，保留前 max_count 个
            self._pending.sort(key=lambda x: x["score"], reverse=True)
            if len(self._pending) > max_count:
                self._pending = self._pending[:max_count]
            self._save_pending()

        return item

    def get_all_pending(self) -> list[dict[str, Any]]:
        """获取全部待选区"""
        return list(self._pending)

    def get_record_count(self) -> int:
        """获取已投递总数"""
        return len(self._applied)

    def reset_session(self) -> None:
        """
        重置当前会话的计数（不删除历史记录）。
        每次新"开始投递"任务时调用。
        """
        self._tier_counts = {"high": 0, "medium": 0, "try": 0}
        self._applied = []
        self._applied_companies = set()
        # 从文件恢复历史已投公司，跨会话去重
        if self._applied_path.exists():
            try:
                with open(self._applied_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
                for record in history:
                    company = record.get("company", "")
                    if company:
                        self._applied_companies.add(company)
            except Exception:
                pass


# 全局单例
record_manager = RecordManager()
