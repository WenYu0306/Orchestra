"""
validator 模块单元测试 —— 只测三个纯逻辑函数，不依赖任何外部服务。
"""
from backend.validator import check_city, check_salary, check_company


# ============ check_city ============

def test_check_city_match():
    ok, warn = check_city({"cityName": "北京·朝阳区"}, "北京")
    assert ok and not warn

def test_check_city_mismatch():
    # 城市不符 = 硬拒绝（无人值守宁漏勿错）
    ok, warn = check_city({"cityName": "南京"}, "长春")
    assert not ok

def test_check_city_empty():
    # 城市缺失 = 硬拒绝
    ok, warn = check_city({"cityName": ""}, "北京")
    assert not ok


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

def test_check_salary_bare_numbers():
    """BOSS 薪资有时不带 K 单位, '15-25' 实际是 15K-25K"""
    ok, warn = check_salary({"salaryDesc": "15-25"}, 15000)
    assert ok and not warn
    ok, _ = check_salary({"salaryDesc": "8-12"}, 15000)
    assert not ok

def test_check_salary_wan_format():
    """'2-3万' = 20K-30K。修复前被解析成 2K，高薪岗位被误杀"""
    ok, _ = check_salary({"salaryDesc": "2-3万"}, 15000)
    assert ok
    ok, _ = check_salary({"salaryDesc": "1-2万"}, 15000)
    assert not ok

def test_check_salary_daily_format():
    """日薪 500-800元/天 ≈ 10.9K-17.4K/月"""
    ok, _ = check_salary({"salaryDesc": "500-800元/天"}, 10000)
    assert ok
    ok, _ = check_salary({"salaryDesc": "200-300元/天"}, 10000)
    assert not ok

def test_check_salary_annual_wan():
    """'30-50万/年' 月薪下限 2.5万"""
    ok, _ = check_salary({"salaryDesc": "30-50万/年"}, 20000)
    assert ok

def test_check_salary_unparseable():
    """'面议' 解析不了 → 放行但给出告警"""
    ok, warn = check_salary({"salaryDesc": "面议"}, 15000)
    assert ok and warn

def test_check_salary_empty():
    ok, warn = check_salary({"salaryDesc": ""}, 15000)
    assert ok and warn


# ============ check_company ============

def test_check_company_normal():
    ok, warn = check_company({"brandName": "蚂蚁集团"})
    assert ok and not warn

def test_check_company_empty():
    ok, warn = check_company({"brandName": ""})
    assert not ok

def test_check_company_question_mark():
    ok, warn = check_company({"brandName": "?"})
    assert not ok

def test_check_company_too_long():
    ok, warn = check_company({"brandName": "这是一个超过三十个字符的非常长的公司名称用来测试校验逻辑是否正确触发告警机制请勿删"})
    assert not ok

def test_check_company_fake_pattern():
    ok, warn = check_company({"brandName": "XX科技教育培训基地"}, ["科技教育"])
    assert not ok


if __name__ == "__main__":
    import sys
    failed = 0
    for name, fn in sorted({k: v for k, v in globals().items()
                            if k.startswith("test_") and callable(v)}.items()):
        try:
            fn()
            print(f"{name} PASS")
        except AssertionError:
            failed += 1
            print(f"{name} FAIL")
    sys.exit(1 if failed else 0)
