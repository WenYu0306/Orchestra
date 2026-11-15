"""DeepSeek 输出解析 / 薪资格式 / 发送时间窗 的金样本回归。

这三个「翻译官」曾分别出过事：AI 回复解析错导致评分全乱、「2-3万」被
误读成 2 千导致高薪岗位误杀（v1.2.0 修复）、畸形时间窗配置放行发送。
本文件固化它们的实际行为，防止后续改动悄悄破坏。金样本来自 2026-11-16
对实现的实测探针，改动解析逻辑前先跑本文件确认意图。
"""
import time
from unittest.mock import patch

import pytest

from backend.matcher import _parse_response
from backend.validator import _parse_salary_low
from backend.agent_runner import AgentRunner


# ---- DeepSeek 输出解析 ----

def test_parse_plain_json():
    r = _parse_response('{"score": 82, "reason": "匹配"}')
    assert r["score"] == 82 and r["reason"] == "匹配" and r["confidence"] == "low"


def test_parse_markdown_wrapped():
    assert _parse_response('```json\n{"score": 72}\n```')["score"] == 72


def test_parse_json_with_prose():
    assert _parse_response('结果：{"score": 65} 以上')["score"] == 65


def test_parse_garbage_raises():
    with pytest.raises(ValueError):
        _parse_response("抱歉，我无法完成解析")


def test_parse_string_score_coerced():
    assert _parse_response('{"score": "82"}')["score"] == 82


def test_parse_missing_fields_defaults():
    assert _parse_response("{}") == {
        "score": 0, "reason": "", "confidence": "low",
        "is_fake_job": False, "cross_industry_friendly": False,
    }


# ---- 薪资格式（元） ----

@pytest.mark.parametrize("sd,expected", [
    ("500-1000元/天", 10875),   # 日薪 × 21.75 工作日
    ("200-300元/天", 4350),
    ("2-3万", 20000),           # v1.2.0 修复的「万被误读成千」回归
    ("15-25万/年", 12500),      # 年薪 ÷ 12
    ("15-25K", 15000),
    ("15k-25K", 15000),         # 大小写不敏感
    ("15-25", 15000),           # 裸区间 <100 按 BOSS 的 K 语义
    ("12-18K", 12000),
    ("面议", None),
    ("", None),
])
def test_parse_salary_low(sd, expected):
    assert _parse_salary_low(sd) == expected


# ---- 发送时间窗 ----

def frozen_clock(h, m):
    return time.struct_time((2026, 11, 16, h, m, 0, 6, 320, 0))


def test_active_hours_inside():
    with patch("time.localtime", return_value=frozen_clock(10, 30)):
        assert AgentRunner._check_active_hours("09:00-20:00") == (True, "")


def test_active_hours_outside():
    with patch("time.localtime", return_value=frozen_clock(7, 0)):
        ok, msg = AgentRunner._check_active_hours("09:00-20:00")
        assert not ok and "09:00-20:00" in msg


def test_active_hours_malformed_fails_open():
    """畸形配置的现状行为：告警并放行（fail-open）。固化为刻意选择——
    有人顺手改成 fail-close 时这个测试会提醒他权衡（发送停摆 vs 误发）。"""
    with patch("time.localtime", return_value=frozen_clock(10, 30)):
        assert AgentRunner._check_active_hours("9点到20点") == (True, "")
        assert AgentRunner._check_active_hours("abc") == (True, "")
