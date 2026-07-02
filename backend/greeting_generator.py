"""
招呼语生成器 — 直调 DeepSeek API（httpx.AsyncClient）。
"""

import json
import re
import httpx
from .config_loader import get_api_key, get_llm_base_url

GREETING_PROMPT = """你是求职者本人，要诚实、克制地给 HR 发一条招呼语。

## 你的真实简历摘要（只能说自己确实有的经历，不能编造）
{resume}

## 职位描述
{jd_text}

## 要求
- 长度 50-100 字
- 只能提及简历里真实存在的技能或经历
- 不要夸大年限、不要编造头衔、不要说"精通"如果没有
- 语气自然，像真人发的，不要模板化
- 如果没有特别匹配的点，就说"我对这个方向很感兴趣，希望能进一步了解"

## 输出格式
只返回 JSON：
{{"greeting": "<招呼语>"}}"""


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
        "temperature": 0.5,
        "max_tokens": 256,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            r = await client.post(url, json=body, headers=headers)
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"] or ""
        raw = re.sub(r"```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```", "", raw)
        return json.loads(raw.strip()).get("greeting", "您好，我对这个职位很感兴趣。")
    except Exception:
        return "您好，我对这个职位很感兴趣，希望能进一步了解。"