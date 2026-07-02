"""
SSE 事件管理器 —— 管理 Server-Sent Events 连接池和事件推送。

前端通过 GET /api/events 订阅，后端通过此模块推送事件。
"""

import asyncio
import json
import time
from enum import Enum
from typing import Any, Optional

from starlette.responses import StreamingResponse


class SSEEventType(str, Enum):
    STATUS = "status"
    RECORD = "record"
    PENDING = "pending"
    CAPTCHA = "captcha"
    COMPLETE = "complete"
    ERROR = "error"


class AppStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    NEED_CAPTCHA = "need_captcha"
    COMPLETED = "completed"
    ERROR = "error"


class SSEManager:
    """SSE 连接管理器。优雅关闭：通过 _shutdown_event 通知所有连接退出。"""

    def __init__(self):
        self._queues: list[asyncio.Queue] = []
        self._status: AppStatus = AppStatus.IDLE
        self._shutdown_event = asyncio.Event()

    @property
    def status(self) -> AppStatus:
        return self._status

    def set_status(self, status: AppStatus) -> None:
        self._status = status

    async def shutdown(self) -> None:
        """通知所有 SSE 连接退出"""
        self._shutdown_event.set()
        for queue in self._queues:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
        self._queues.clear()

    async def subscribe(self) -> StreamingResponse:
        """创建 SSE 订阅端点"""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._queues.append(queue)

        async def event_generator():
            try:
                # 发送初始状态
                yield self._format_event(SSEEventType.STATUS, {
                    "status": self._status.value,
                    "timestamp": time.time(),
                })

                while not self._shutdown_event.is_set():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=25.0)
                        if event is None:  # 关闭信号
                            break
                        yield event
                    except asyncio.TimeoutError:
                        yield ": heartbeat\n\n"
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            finally:
                try:
                    self._queues.remove(queue)
                except ValueError:
                    pass

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def emit(self, event_type: SSEEventType, data: dict[str, Any]) -> None:
        """向所有已连接的客户端推送事件"""
        if self._shutdown_event.is_set():
            return
        message = self._format_event(event_type, data)
        dead_queues = []
        for queue in self._queues:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                dead_queues.append(queue)
        for queue in dead_queues:
            try:
                self._queues.remove(queue)
            except ValueError:
                pass

    async def emit_status(self, status: AppStatus, extra: Optional[dict[str, Any]] = None) -> None:
        self._status = status
        data = {"status": status.value, "timestamp": time.time()}
        if extra:
            data.update(extra)
        await self.emit(SSEEventType.STATUS, data)

    async def emit_record(self, record: dict[str, Any]) -> None:
        await self.emit(SSEEventType.RECORD, record)

    async def emit_pending(self, pending_list: list[dict[str, Any]]) -> None:
        await self.emit(SSEEventType.PENDING, {"items": pending_list})

    async def emit_captcha(self, message: str = "检测到验证码，请手动处理") -> None:
        await self.emit_status(AppStatus.NEED_CAPTCHA, {"message": message})
        await self.emit(SSEEventType.CAPTCHA, {"message": message})

    async def emit_complete(self, summary: dict[str, Any]) -> None:
        await self.emit_status(AppStatus.COMPLETED, summary)
        await self.emit(SSEEventType.COMPLETE, summary)

    async def emit_error(self, message: str) -> None:
        await self.emit_status(AppStatus.ERROR, {"message": message})
        await self.emit(SSEEventType.ERROR, {"message": message})

    @staticmethod
    def _format_event(event_type: SSEEventType, data: dict[str, Any]) -> str:
        payload = {**data, "event_type": event_type.value}
        return f"event: {event_type.value}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


# 全局单例
sse_manager = SSEManager()
