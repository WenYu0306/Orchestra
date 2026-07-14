"""
招呼语生成器 — 直调 DeepSeek API（httpx.AsyncClient）。
"""

import json
import re
import httpx
from .config_loader import get_api_key, get_llm_base_url

_shared_client = None

GREETING_PROMPT = """你是正在找工作的开发者。看了下方的岗位描述和你的背景。脑子里冒出的第一句是什么？写下来。10-30 字，别说客套话。

## 你的背景
{resume}

## 让你感兴趣的岗位
{jd_text}

好参考："看了你们的JD，我做的项目正好是Agent编排这一套，聊聊？"
当然你的话可以跟这个完全不同。

JSON: {{"greeting": "..."}}"""


async def generate(jd_text: str, resume: str = "") -> str:
    prompt = GREETING_PROMPT.format(jd_text=jd_text[:1500], resume=resume[:800] or "简历未提供")
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