"""
招呼语生成器 — 直调 DeepSeek API（httpx.AsyncClient）。
"""

import json
import re
import httpx
from .config_loader import get_api_key, get_llm_base_url

_shared_client = None

GREETING_PROMPT = """你用求职者本人的语气给 HR 发私信。40-60 字，像朋友简单说两句，不要长。

## 简历（只写真实的）
{resume}

## 岗位
{jd_text}

## 硬规矩
- 第一条必须呼应岗位里一个具体点（比如他们用的技术栈、做的业务方向），不是泛泛说"我对这个岗位感兴趣"
- 不要列举项目数量（"三个月做了三个项目"这种删掉）
- 不要AI模板词：赋能/闭环/抓手/深度/全面/助力/协同/沉淀/裸辞转行
- 不要"希望能进一步沟通"/"期待您的回复"这类客套结尾——前面说得自然、最后直接话尾即可
- 不要说"精通"如果没有
- 如果没有真的好写的，就说一句朴素的话

## 输出
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
        "temperature": 0.5,
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