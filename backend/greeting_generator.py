"""
招呼语生成器 — 直调 DeepSeek API（httpx.AsyncClient）。
"""

import json
import re
import httpx
from .config_loader import get_api_key, get_llm_base_url

_shared_client = None

GREETING_PROMPT = """你是求职者本人。下面是你的三个技能侧面，每次只用其中一个去接岗位上的某个点。以第一人称（"我做过X"或"我的X项目"）说一句话——不客气，不构思。

## 你的三个侧面
1. AI Agent / CDP：独立设计并实现过三层解耦的AI Agent编排框架，支持Agent自主决策和 Chrome DevTools Protocol 自定义消息注入
2. RAG / 知识库 / 建工智脑：做过施工知识助手，25表建模、FSM自检、64个测试通过，覆盖从数据清洗到引用溯源的全流程
3. 全栈开发 / 工程化：用Python和Java交付过完整AI产品，熟悉前后端架构、API抽象层、多平台内容引擎

## 岗位
{jd_text}

JSON: {{"greeting": "..."}}"""


async def generate(jd_text: str, resume: str = "") -> str:
    prompt = GREETING_PROMPT.format(jd_text=jd_text[:1500])
    url = f"{get_llm_base_url('deepseek')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {get_api_key('deepseek')}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个诚实的求职者。只返回JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 256,
    }
    try:
        global _shared_client
        if _shared_client is None:
            _shared_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=10))
        r = await _shared_client.post(url, json=body, headers=headers)
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"] or ""
        raw = re.sub(r"```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```", "", raw)
        return json.loads(raw.strip()).get("greeting", "您好，我对这个职位很感兴趣。")
    except Exception:
        return "您好，我对这个职位很感兴趣，希望能进一步了解。"