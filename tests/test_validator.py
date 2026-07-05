"""
validator 模块单元测试 —— 只测三个纯逻辑函数，不依赖任何外部服务。
"""
from backend.validator import check_city, check_salary, check_company


# ============ check_city ============

def test_check_city_match():
    ok, warn = check_city({"cityName": "北京"}, "北京")
    assert ok and not warn

def test_check_city_mismatch():
    ok, warn = check_city({"cityName": "南京"}, "长春")
    assert ok and warn

def test_check_city_empty():
    ok, warn = check_city({"cityName": ""}, "北京")
    assert ok and not warn


# ============ check_salary ============

def test_check_salary_too_low():
    ok, warn = check_salary({"salaryDesc": "8K-12K"}, 15000)
    assert not ok  # 8K < 15K, 应跳过

def test_check_salary_ok():
    ok, warn = check_salary({"salaryDesc": "20K-30K"}, 15000)
    assert ok and not warn

def test_check_salary_no_limit():
    ok, warn = check_salary({"salaryDesc": "5K-8K"}, 0)
    assert ok and not warn

def test_check_salary_jd_encoding():
    """BOSS 薪资有时不带 K 单位, '15-25' 实际是 15K-25K"""
    ok, warn = check_salary({"salaryDesc": "25-35K"}, 15000)
    assert ok and not warn

def test_check_salary_empty():
    ok, warn = check_salary({"salaryDesc": ""}, 15000)
    assert ok and not warn


# ============ check_company ============

def test_check_company_normal():
    ok, warn = check_company({"brandName": "蚂蚁集团"})
    assert ok and not warn

def test_check_company_empty():
    ok, warn = check_company({"brandName": ""})
    assert ok and warn

def test_check_company_question_mark():
    ok, warn = check_company({"brandName": "?"})
    assert ok and warn

def test_check_company_too_long():
    ok, warn = check_company({"brandName": "参与公司产品的研发，技术方案的规划和落地"})
    assert ok and warn
