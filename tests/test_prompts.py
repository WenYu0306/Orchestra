"""
Prompt 模板测试 —— 直接 import 真实模块的模板（不再持有会过期的复制品），
确保 Python .format() 不与 JSON 的 { } 占位符冲突，且关键指令在。
"""
from backend.matcher import MATCH_PROMPT_TEMPLATE
from backend.greeting_generator import GREETING_PROMPT
from backend.search_generator import SEARCH_KEYWORD_PROMPT


def test_matcher_prompt_format():
    result = MATCH_PROMPT_TEMPLATE.format(resume_text="测试简历", jd_text="测试JD")
    assert "测试简历" in result
    assert "测试JD" in result
    # 评分锚点必须在场（防止 60-75 中间分塌缩）
    assert "90-100" in result
    assert "60-74" in result
    assert "禁止把所有岗位都打进 60-75" in result
    # JSON schema 字段在 format 后完整存活
    assert '"score"' in result
    assert '"reason"' in result
    assert '"confidence"' in result
    assert '"is_fake_job"' in result


def test_search_prompt_format():
    result = SEARCH_KEYWORD_PROMPT.format(
        resume_text="测试简历", cities="天津, 长春", keywords="AI应用开发, LLM")
    assert "测试简历" in result
    assert "天津, 长春" in result
    assert "AI应用开发, LLM" in result


def test_greeting_prompt_format():
    result = GREETING_PROMPT.format(profiles="技能档案", jd_text="测试JD")
    assert "技能档案" in result
    assert "测试JD" in result
    assert "greeting" in result


if __name__ == "__main__":
    test_matcher_prompt_format()
    test_search_prompt_format()
    test_greeting_prompt_format()
    print("3/3 passed")
