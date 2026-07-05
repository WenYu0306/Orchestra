"""
Prompt 模板格式化测试 — 确保 Python .format() 不与 JSON 的 { } 占位符冲突。
"""

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


def test_matcher_prompt_format():
    result = MATCH_PROMPT_TEMPLATE.format(resume_text="测试简历", jd_text="测试JD")
    assert "测试简历" in result
    assert "测试JD" in result
    assert "评分标准" in result


def test_matcher_json_schema_survives_format():
    """验证 JSON 示例的 { } 在 .format() 后没被吃掉——score/reason/confidence 字段必须完整"""
    result = MATCH_PROMPT_TEMPLATE.format(resume_text="R", jd_text="J")
    assert '"score"' in result
    assert '"reason"' in result
    assert '"confidence"' in result
    assert '"is_fake_job"' in result


def test_search_prompt_format():
    result = SEARCH_KEYWORD_PROMPT.format(
        resume_text="测试简历", cities="北京, 长春", keywords="AI, LLM"
    )
    assert "测试简历" in result
    assert "北京, 长春" in result
    assert "AI, LLM" in result


def test_greeting_prompt_format():
    result = GREETING_PROMPT.format(resume="测试简历", jd_text="测试JD")
    assert "测试简历" in result
    assert "测试JD" in result
    assert "招呼语" in result
