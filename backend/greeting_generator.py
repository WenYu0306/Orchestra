"""
招呼语生成器 — 直调 DeepSeek API（httpx.AsyncClient）。
"""

import json
import re
import httpx
from .config_loader import get_api_key, get_llm_base_url

_shared_client = None

GREETING_PROMPT = """你是求职者本人。下面是你的技能档案，选一条跟岗位最相关的，以第一人称（"我做过X"或"我的X项目"）接上一个点。不客气不构思。

{profiles}

## 岗位
{jd_text}

JSON: {{"greeting": "..."}}"""


async def generate(jd_text: str, profiles: str = "") -> str:
    prompt = GREETING_PROMPT.format(jd_text=jd_text[:1500], profiles=profiles or "AI全栈开发，有Agent编排和RAG经验")
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