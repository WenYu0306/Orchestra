"""
投递记录管理器 —— 读写 applied_jobs.json 和 pending_jobs.json。

核心语义：
- applied_jobs.json 是跨会话的去重数据源，历史记录永久保留（受 max_records 上限截断）。
- "当前会话"只是一个视图：get_all_records() 返回本次运行起点之后的切片。
- 写入使用临时文件 + os.replace 原子替换；文件损坏时先备份再从空记录继续，绝不静默丢弃。
"""

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any
from threading import Lock

from .config_loader import get_config, get_project_root

_log = logging.getLogger("record_manager")

# 发送失败的公司不参与去重（下次运行可重试）
_NON_BLOCKING_STATUS = {"send_failed"}


class RecordManager:
    """
    管理投递记录和待选区。

    - applied_jobs.json: 投递记录（跨会话保留，去重数据源）
    - pending_jobs.json: 待选区职位列表（最多 max_count 个）
    """

    def __init__(self):
        config = get_config()
        project_root = get_project_root()

        self._applied_path = project_root / config.application.get("applied_log_path", "data/applied_jobs.json")
        self._pending_path = project_root / config.application.get("pending_log_path", "data/pending_jobs.json")
        self._max_records = int(config.application.get("max_records", 2000))

        self._applied: list[dict[str, Any]] = []
        self._pending: list[dict[str, Any]] = []
        self._applied_companies: set[str] = set()
        self._lock = Lock()
        self._session_start = 0
        self._tier_counts: dict[str, int] = {"high": 0, "medium": 0, "try": 0}

        self._applied_path.parent.mkdir(parents=True, exist_ok=True)
        self._pending_path.parent.mkdir(parents=True, exist_ok=True)

        self._load()
        self._rebuild_companies()
        # 启动后当前会话视图为空
        self._session_start = len(self._applied)

    # ---- 加载与持久化 ----

    def _load(self) -> None:
        """从磁盘加载记录（损坏时备份后从空开始）"""
        self._applied = self._read_json(self._applied_path)
        self._pending = self._read_json(self._pending_path)

    def _read_json(self, path: Path) -> list:
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as e:
            backup = path.with_name(f"{path.name}.corrupt.{time.strftime('%Y%m%d%H%M%S')}")
            try:
                shutil.copy2(path, backup)
                _log.error("记录文件损坏，已备份到 %s，从空记录继续: %s", backup, e)
            except OSError as copy_err:
                _log.error("记录文件损坏且备份失败: %s / %s", e, copy_err)
            return []

    def _save_applied(self) -> None:
        """原子写入 applied_jobs.json，保留最近 max_records 条"""
        if len(self._applied) > self._max_records:
            self._applied = self._applied[-self._max_records:]
            self._session_start = min(self._session_start, len(self._applied))
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

    def _rebuild_companies(self) -> None:
        """从全部历史记录重建去重集合（send_failed 的公司不拉黑）"""
        self._applied_companies = {
            r.get("company", "")
            for r in self._applied
            if r.get("company") and r.get("status") not in _NON_BLOCKING_STATUS
        }

    @staticmethod
    def _parse_ts(ts: str) -> float | None:
        try:
            return time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))
        except (ValueError, TypeError):
            return None

    # ---- 去重查询 ----

    def is_company_recent(self, company: str, days: int = 30) -> bool:
        """检查公司最近 N 天是否已投递/招呼过（基于全部历史记录）"""
        cutoff = time.time() - days * 86400
        for record in reversed(self._applied):
            if record.get("company") != company:
                continue
            if record.get("status") in _NON_BLOCKING_STATUS:
                continue
            ts = self._parse_ts(record.get("timestamp", ""))
            # 时间戳缺失按"最近"处理（宁可错拦不可重发）
            if ts is None or ts >= cutoff:
                return True
        return False

    # ---- 投递记录 CRUD ----

    def add_record(
        self,
        company: str,
        position: str,
        score: int,
        reason: str,
        tier: str,
        status: str = "dry_run",
        security_id: str = "",
        encrypt_job_id: str = "",
        greeting: str = "",
        salary: str = "",
        search_city: str = "",
        search_kw: str = "",
        greeting_is_default: bool = False,
    ) -> dict[str, Any]:
        """添加一条投递记录"""
        if tier not in ("high", "medium", "try"):
            _log.warning("未知分层 %r，按 try 处理", tier)
            tier = "try"
        record = {
            "company": company,
            "position": position,
            "score": score,
            "reason": reason,
            "tier": tier,
            "status": status,  # dry_run / sent / send_failed / review_only
            "security_id": security_id,
            "encrypt_job_id": encrypt_job_id,
            "greeting": greeting,
            "greeting_is_default": greeting_is_default,
            "salary": salary,
            "search_city": search_city,
            "search_kw": search_kw,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        with self._lock:
            self._applied.append(record)
            self._tier_counts[tier] = self._tier_counts.get(tier, 0) + 1
            if status not in _NON_BLOCKING_STATUS:
                self._applied_companies.add(company)
            self._save_applied()

        return record

    def mark_sent(self, company: str, encrypt_job_id: str, status: str) -> bool:
        """按 公司+encryptJobId 把 dry_run 记录更新为 sent / send_failed。

        发送失败的公司同时移出去重集合，下次运行可重试；成功则确保进入集合。
        """
        with self._lock:
            target = None
            for record in reversed(self._applied):
                if record.get("company") != company:
                    continue
                if encrypt_job_id and record.get("encrypt_job_id") != encrypt_job_id:
                    continue
                target = record
                break
            if target is None:
                _log.warning("mark_sent 未找到记录: %s / %s", company, encrypt_job_id[:20])
                return False
            target["status"] = status
            target["sent_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            if status in _NON_BLOCKING_STATUS:
                self._applied_companies.discard(company)
            else:
                self._applied_companies.add(company)
            self._save_applied()
            return True

    def get_all_records(self) -> list[dict[str, Any]]:
        """获取当前会话的投递记录（不含历史会话）"""
        return list(self._applied[self._session_start:])

    def get_record_count(self) -> int:
        """当前会话的记录数"""
        return max(0, len(self._applied) - self._session_start)

    def get_tier_counts(self) -> dict[str, int]:
        """当前会话各层计数"""
        return {t: self._tier_counts.get(t, 0) for t in ("high", "medium", "try")}

    def get_sent_count_today(self) -> int:
        """今天（本地时区）真实发送成功的条数，跨会话累计"""
        today = time.strftime("%Y-%m-%d")
        return sum(
            1 for r in self._applied
            if r.get("status") == "sent" and str(r.get("sent_at", "")).startswith(today)
        )

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

    def reset_session(self) -> None:
        """开始新的一次运行：从磁盘重载历史（去重源），会话视图清零。不删除历史。"""
        with self._lock:
            self._load()
            self._rebuild_companies()
            self._session_start = len(self._applied)
            self._tier_counts = {"high": 0, "medium": 0, "try": 0}


# 全局单例
record_manager = RecordManager()
