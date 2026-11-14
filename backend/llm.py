"""DeepSeek 调用共享层 —— 单一 httpx 客户端。

此前 matcher / greeting_generator / search_generator / agent_runner 各养一个
一模一样的 _shared_client 单例（2026-11-14 造轮子审计），统一收敛到这里。
各调用方用 client.post(..., timeout=N) 保留自己的超时语义。
"""
import httpx

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10))
    return _client


async def aclose() -> None:
    """应用退出时调用（main.py lifespan），避免连接句柄泄漏。"""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
