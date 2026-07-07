"""
动态搜索词生成器 — 直调 DeepSeek API（httpx.AsyncClient）。
"""

import json
import re
import httpx
from .config_loader import get_api_key, get_llm_base_url

_shared_client = None

SEARCH_KEYWORD_PROMPT = """你是一位职业规划分析师。请分析以下简历，为求职者生成最优的职位搜索关键词组合。

## 任务
1. 从简历中提取候选人的核心技能领域
2. 识别可迁移技能（跨行业适用的技能）
3. 生成 3-5 个搜索方向，每个方向包含 1-2 个核心关键词
4. 按优先级排序（最有竞争力的方向排最前）

## 输出格式
必须只返回一个 JSON 数组：
```json
[
  {{
    "direction": "<方向名称>",
    "keywords": ["<关键词1>", "<关键词2>"],
    "priority": 1,
    "rationale": "<推荐理由>"
  }}
]
```

## 搜索约束
- 搜索城市限定：{cities}
- 搜索关键词参考：{keywords}
- 排除：纯硬件、嵌入式、游戏开发等与简历无关的方向

## 候选人简历
{resume_text}"""


async def generate(resume_text: str) -> list[dict]:
    """分析简历并生成搜索方向列表。"""
    from .config_loader import get_config
    cfg = get_config()
    cities = ', '.join(c['name'] for c in cfg.search.get('cities', []))
    kws = ', '.join(cfg.search.get('primary_keywords', []))
    prompt = SEARCH_KEYWORD_PROMPT.format(
        resume_text=resume_text[:4000], cities=cities, keywords=kws)

    url = f"{get_llm_base_url('deepseek')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {get_api_key('deepseek')}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个精确的 JSON 输出器。只返回 JSON 数组。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    try:
        global _shared_client
        if _shared_client is None:
            _shared_client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=5.0),
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=10))
        r = await _shared_client.post(url, json=body, headers=headers)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"] or ""
        return _parse_response(content)
    except Exception:
        # 降级：使用默认搜索词
        return [
            {"direction": "AI应用开发", "keywords": ["AI应用开发"], "priority": 1,
             "rationale": "默认搜索方向"},
            {"direction": "LLM", "keywords": ["LLM"], "priority": 2,
             "rationale": "默认搜索方向"},
            {"direction": "全栈开发", "keywords": ["全栈开发"], "priority": 3,
             "rationale": "默认搜索方向"},
        ]


def _parse_response(content: str) -> list[dict]:
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
    if json_match:
        content = json_match.group(1)
    try:
        result = json.loads(content.strip())
    except json.JSONDecodeError:
        array_match = re.search(r'\[[\s\S]*\]', content)
        if array_match:
            result = json.loads(array_match.group(0))
        else:
            raise ValueError(f"无法解析搜索词: {content[:200]}")
    if not isinstance(result, list):
        raise ValueError(f"搜索词生成结果不是数组: {type(result)}")
    return result