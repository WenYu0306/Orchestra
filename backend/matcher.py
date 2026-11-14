"""
简历-JD 智能匹配器 — 直调 DeepSeek API（httpx.AsyncClient + asyncio.wait_for）。
"""

import json
import re
import asyncio
import logging
import httpx
from .config_loader import get_api_key, get_llm_base_url

_log = logging.getLogger("matcher")

_shared_client = None

MATCH_PROMPT_TEMPLATE = """你是一位严苛但公道的招聘匹配评估师。对比简历与职位描述，输出 0-100 匹配分。

## 评分锚点（必须对号入座，禁止把所有岗位都打进 60-75 的中间地带）
- 90-100：岗位就是为这类候选人准备的——技术方向、核心技术栈、项目类型三项全命中
- 75-89：方向正确，核心技术栈大半命中，有 1-2 处缺口但不影响上岗
- 60-74：方向沾边、技术栈命中约一半，或方向不同但有明确可迁移的项目证据
- 40-59：方向不符或核心技术明显缺失，仅零散关键词重合
- 0-39：完全不对口

## 评分构成
- 技术方向与核心技术栈命中（权重最高），以简历中的真实证据为准
- 项目经验相关性：简历里是否有同类或可迁移的完整项目
- 基本条件：仅当 JD 写明硬性门槛（学历/年限/证书）且简历明确不满足时才扣分；
  不确定的不要凭空扣分，禁止因候选人非科班背景而统一压分
- 跨行业成功迁移证据（如独立交付过完整项目）最多 +5

## 虚假招聘识别
JD含培训/转行/包就业等培训机构特征 → 标记虚假
公司名含教育/培训/实训等关键词 → 标记虚假

## 输出要求
只返回一个 JSON 对象：
{{"score": <0-100整数>, "reason": "<一句话：命中了什么/缺什么>", "confidence": "<high|medium|low>", "is_fake_job": <true|false>, "cross_industry_friendly": <true|false>}}

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
    except httpx.HTTPStatusError as e:
        # 401/402 是买家最常见的两类故障——人话原因直传 UI（评分熔断时展示）
        if e.response.status_code == 401:
            reason = "匹配评分失败：DeepSeek Key 无效——请在设置里重新填写（sk- 开头完整复制）"
        elif e.response.status_code == 402:
            reason = "匹配评分失败：DeepSeek 余额不足——请到 platform.deepseek.com 充值后重试"
        else:
            reason = f"匹配评分失败：DeepSeek 返回 HTTP {e.response.status_code}"
        # DeepSeek 故障会让这批岗位全部按 0 分被丢弃，必须留痕
        _log.warning("%s | JD前80字: %s", reason, jd_text[:80])
        return {
            "score": 0,
            "reason": reason,
            "confidence": "low",
            "is_fake_job": False,
            "cross_industry_friendly": False,
        }
    except Exception as e:
        _log.warning("DeepSeek 匹配评分失败（岗位将被跳过）: %s | JD前80字: %s", e, jd_text[:80])
        return {
            "score": 0,
            "reason": "匹配评分失败：网络异常，请检查网络后重试",
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
