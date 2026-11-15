"""
招呼语生成器 — 直调 DeepSeek API（共享客户端 backend/llm.py）。
"""

import json
import re
import logging
from .config_loader import get_api_key, get_llm_base_url
from .llm import get_client

_log = logging.getLogger("greeting")

# 生成失败时的降级文案——全链路唯一来源（agent_runner 同样引用）
DEFAULT_GREETING = "您好，我对这个职位很感兴趣，希望能进一步了解。"

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
        r = await get_client().post(url, json=body, headers=headers)
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"] or ""
        raw = re.sub(r"```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```", "", raw)
        return json.loads(raw.strip()).get("greeting", DEFAULT_GREETING)
    except Exception as e:
        # 降级为通用招呼语——发给了真实招聘方，必须留痕让操作者知道
        _log.warning("招呼语生成失败，降级为通用文案: %s | JD前60字: %s", e, jd_text[:60])
        return DEFAULT_GREETING