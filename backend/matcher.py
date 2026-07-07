"""
简历-JD 智能匹配器 — 直调 DeepSeek API（httpx.AsyncClient + asyncio.wait_for）。
"""

import json
import re
import asyncio
import httpx
from .config_loader import get_api_key, get_llm_base_url

_shared_client = None

MATCH_PROMPT_TEMPLATE = """你是一位专业的招聘匹配分析师。对比以下简历和职位描述，给出匹配评分和分析。

## 评分标准（总分 100）
- 技术栈重合度：50%
- 项目经验相关性：30%
- 基本条件满足度：20%
- 跨行业友好加分：额外 +5 分

## 虚假招聘识别
JD含培训/转行/包就业等培训机构特征 → 标记虚假
公司名含教育/培训/实训等关键词 → 标记虚假

## 输出要求
只返回一个 JSON 对象：
{{"score": <0-100整数>, "reason": "<匹配理由>", "confidence": "<high|medium|low>", "is_fake_job": <true|false>, "cross_industry_friendly": <true|false>}}

## 候选人简历
{resume_text}

## 职位描述
{jd_text}"""


async def _call_ds(prompt: str, timeout=8.0) -> dict:
    """直调 DeepSeek API，共享客户端避免连接池泄漏。"""
    global _shared_client
    if _shared_client is None:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=5.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10))
    url = f"{get_llm_base_url('deepseek')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {get_api_key('deepseek')}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个精确的 JSON 输出器。只返回 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 512,
    }
    r = await _shared_client.post(url, json=body, headers=headers)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"] or ""
    return _parse_response(content)


async def match(resume_text: str, jd_text: str) -> dict:
    """异步匹配打分（兼容旧调用方 await matcher.match(...)）。"""
    prompt = MATCH_PROMPT_TEMPLATE.format(
        resume_text=resume_text[:3000],
        jd_text=jd_text[:2000],
    )
    try:
        return await asyncio.wait_for(_call_ds(prompt, timeout=8.0), timeout=10.0)
    except Exception:
        return {
            "score": 0,
            "reason": "匹配评分失败",
            "confidence": "low",
            "is_fake_job": False,
            "cross_industry_friendly": False,
        }


def _parse_response(content: str) -> dict:
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
    if json_match:
        content = json_match.group(1)
    try:
        result = json.loads(content.strip())
    except json.JSONDecodeError:
        brace_match = re.search(r'\{[\s\S]*\}', content)
        if brace_match:
            result = json.loads(brace_match.group(0))
        else:
            raise ValueError(f"无法解析 DeepSeek 返回: {content[:200]}")
    return {
        "score": int(result.get("score", 0)),
        "reason": str(result.get("reason", "")),
        "confidence": str(result.get("confidence", "low")),
        "is_fake_job": bool(result.get("is_fake_job", False)),
        "cross_industry_friendly": bool(result.get("cross_industry_friendly", False)),
    }
