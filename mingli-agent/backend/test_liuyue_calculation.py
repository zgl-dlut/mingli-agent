"""
单元测试：验证流月计算和传入逻辑
"""
import sys
sys.path.insert(0, '/Users/zhangguangling/Downloads/命理推算/mingli-agent/backend')

from app.skills.divination.dayun_liunian_skill import analyze_liuyue, WU_HU_DUN, TIANGAN, DIZHI


def test_wuhu_dun():
    """测试五虎遁表是否正确"""
    print("=== 测试五虎遁表 ===")
    
    # 五虎遁规则：
    # 甲己之年丙作首（甲年或己年，正月是丙寅）
    # 乙庚之岁戊为头（乙年或庚年，正月是戊寅）
    # 丙辛必定寻庚起（丙年或辛年，正月是庚寅）
    # 丁壬壬位顺行流（丁年或壬年，正月是壬寅）
    # 戊癸甲寅之上好追求（戊年或癸年，正月是甲寅）
    
    expected = {
        "甲": "丙", "己": "丙",
        "乙": "戊", "庚": "戊",
        "丙": "庚", "辛": "庚",
        "丁": "壬", "壬": "壬",
        "戊": "甲", "癸": "甲",
    }
    
    for year_tian, expected_month_tian in expected.items():
        actual = WU_HU_DUN.get(year_tian)
        assert actual == expected_month_tian, f"五虎遁错误：{year_tian}年正月应该是{expected_month_tian}寅，实际是{actual}寅"
        print(f"✓ {year_tian}年正月 = {actual}寅")
    
    print()


def test_2027_liuyue():
    """测试2027年（丁未年）的流月计算"""
    print("=== 测试2027年（丁未年）流月 ===")
    
    # 2027年是丁未年
    liunian_ganzhi = "丁未"
    day_tian = "己"  # 日主天干（假设）
    pillars = {
        "年": {"tian": "庚", "di": "午"},
        "月": {"tian": "丁", "di": "亥"},
        "日": {"tian": "己", "di": "卯"},
        "时": {"tian": "戊", "di": "辰"},
    }
    yongshen = "金"
    jishen = "火"
    
    result = analyze_liuyue(
        liunian_ganzhi=liunian_ganzhi,
        day_tian=day_tian,
        pillars=pillars,
        yongshen=yongshen,
        jishen=jishen,
    )
    
    # 丁年正月应该是壬寅（根据五虎遁）
    # 2027年流月应该是：
    # 正月(2月): 壬寅
    # 二月(3月): 癸卯
    # 三月(4月): 甲辰
    # 四月(5月): 乙巳
    # 五月(6月): 丙午
    # 六月(7月): 丁未
    # 七月(8月): 戊申
    # 八月(9月): 己酉
    # 九月(10月): 庚戌
    # 十月(11月): 辛亥
    # 十一月(12月): 壬子
    # 十二月(1月): 癸丑
    
    expected_months = {
        2: "壬寅",   # 正月
        3: "癸卯",   # 二月
        4: "甲辰",   # 三月
        5: "乙巳",   # 四月
        6: "丙午",   # 五月
        7: "丁未",   # 六月
        8: "戊申",   # 七月
        9: "己酉",   # 八月
        10: "庚戌",  # 九月
        11: "辛亥",  # 十月
        12: "壬子",  # 十一月
        1: "癸丑",   # 十二月
    }
    
    print(f"2027年（丁未年）流月干支：")
    for month_data in result:
        solar_month = month_data.get("solar_month")
        month_ganzhi = month_data.get("month_ganzhi")
        expected = expected_months.get(solar_month)
        
        if expected:
            status = "✓" if month_ganzhi == expected else "✗"
            print(f"{status} {solar_month}月: {month_ganzhi} (期望: {expected})")
            assert month_ganzhi == expected, f"{solar_month}月干支错误：期望{expected}，实际{month_ganzhi}"
    
    print()


def test_2026_liuyue():
    """测试2026年（丙午年）的流月计算"""
    print("=== 测试2026年（丙午年）流月 ===")
    
    # 2026年是丙午年
    liunian_ganzhi = "丙午"
    day_tian = "己"
    pillars = {
        "年": {"tian": "庚", "di": "午"},
        "月": {"tian": "丁", "di": "亥"},
        "日": {"tian": "己", "di": "卯"},
        "时": {"tian": "戊", "di": "辰"},
    }
    yongshen = "金"
    jishen = "火"
    
    result = analyze_liuyue(
        liunian_ganzhi=liunian_ganzhi,
        day_tian=day_tian,
        pillars=pillars,
        yongshen=yongshen,
        jishen=jishen,
    )
    
    # 丙年正月应该是庚寅（根据五虎遁）
    # 2026年流月应该是：
    # 正月(2月): 庚寅
    # 二月(3月): 辛卯
    # 三月(4月): 壬辰
    # 四月(5月): 癸巳
    # 五月(6月): 甲午
    # 六月(7月): 乙未
    # 七月(8月): 丙申
    # 八月(9月): 丁酉
    # 九月(10月): 戊戌
    # 十月(11月): 己亥
    # 十一月(12月): 庚子
    # 十二月(1月): 辛丑
    
    expected_months = {
        2: "庚寅",   # 正月
        3: "辛卯",   # 二月
        4: "壬辰",   # 三月
        5: "癸巳",   # 四月
        6: "甲午",   # 五月
        7: "乙未",   # 六月
        8: "丙申",   # 七月
        9: "丁酉",   # 八月
        10: "戊戌",  # 九月
        11: "己亥",  # 十月
        12: "庚子",  # 十一月
        1: "辛丑",   # 十二月
    }
    
    print(f"2026年（丙午年）流月干支：")
    for month_data in result:
        solar_month = month_data.get("solar_month")
        month_ganzhi = month_data.get("month_ganzhi")
        expected = expected_months.get(solar_month)
        
        if expected:
            status = "✓" if month_ganzhi == expected else "✗"
            print(f"{status} {solar_month}月: {month_ganzhi} (期望: {expected})")
            assert month_ganzhi == expected, f"{solar_month}月干支错误：期望{expected}，实际{month_ganzhi}"
    
    print()


if __name__ == "__main__":
    test_wuhu_dun()
    test_2026_liuyue()
    test_2027_liuyue()
    print("所有测试通过！")
