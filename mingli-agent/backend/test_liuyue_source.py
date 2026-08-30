"""
验证流月数据源是否正确
"""

# 五虎遁表（年干 → 寅月天干）
WU_HU_DUN = {
    "甲": "丙", "己": "丙",  # 甲己之年丙作首
    "乙": "戊", "庚": "戊",  # 乙庚之岁戊为头
    "丙": "庚", "辛": "庚",  # 丙辛必定寻庚起
    "丁": "壬", "壬": "壬",  # 丁壬壬位顺行流
    "戊": "甲", "癸": "甲",  # 戊癸甲寅之上好追求
}

# 天干地支
TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]


def calculate_liuyue(year_ganzhi: str) -> list:
    """
    根据流年干支计算该年12个月的流月干支
    
    五虎遁规则：
    - 甲己之年丙作首（甲年或己年，正月是丙寅）
    - 乙庚之岁戊为头（乙年或庚年，正月是戊寅）
    - 丙辛必定寻庚起（丙年或辛年，正月是庚寅）
    - 丁壬壬位顺行流（丁年或壬年，正月是壬寅）
    - 戊癸甲寅之上好追求（戊年或癸年，正月是甲寅）
    """
    year_tian = year_ganzhi[0]  # 取流年天干
    yin_tian = WU_HU_DUN.get(year_tian, "丙")  # 正月天干
    yin_idx = TIANGAN.index(yin_tian)
    
    results = []
    for i, month_di in enumerate(DIZHI):
        # 月干：从寅月天干开始，按天干顺序递推
        month_tian = TIANGAN[(yin_idx + i) % 10]
        month_ganzhi = month_tian + month_di
        results.append(month_ganzhi)
    
    return results


def test_2026_liuyue():
    """测试2026年（丙午年）流月"""
    print("=== 2026年（丙午年）流月 ===")
    liuyue = calculate_liuyue("丙午")
    
    # 丙年正月应该是庚寅
    expected = [
        "庚寅", "辛卯", "壬辰", "癸巳", "甲午", "乙未",
        "丙申", "丁酉", "戊戌", "己亥", "庚子", "辛丑"
    ]
    
    for i, (actual, exp) in enumerate(zip(liuyue, expected)):
        month_name = ["正月", "二月", "三月", "四月", "五月", "六月",
                      "七月", "八月", "九月", "十月", "十一月", "十二月"][i]
        status = "✓" if actual == exp else "✗"
        print(f"{status} {month_name}: {actual} (期望: {exp})")
    
    print()


def test_2027_liuyue():
    """测试2027年（丁未年）流月"""
    print("=== 2027年（丁未年）流月 ===")
    liuyue = calculate_liuyue("丁未")
    
    # 丁年正月应该是壬寅
    expected = [
        "壬寅", "癸卯", "甲辰", "乙巳", "丙午", "丁未",
        "戊申", "己酉", "庚戌", "辛亥", "壬子", "癸丑"
    ]
    
    for i, (actual, exp) in enumerate(zip(liuyue, expected)):
        month_name = ["正月", "二月", "三月", "四月", "五月", "六月",
                      "七月", "八月", "九月", "十月", "十一月", "十二月"][i]
        status = "✓" if actual == exp else "✗"
        print(f"{status} {month_name}: {actual} (期望: {exp})")
    
    print()


def test_2028_liuyue():
    """测试2028年（戊申年）流月"""
    print("=== 2028年（戊申年）流月 ===")
    liuyue = calculate_liuyue("戊申")
    
    # 戊年正月应该是甲寅
    expected = [
        "甲寅", "乙卯", "丙辰", "丁巳", "戊午", "己未",
        "庚申", "辛酉", "壬戌", "癸亥", "甲子", "乙丑"
    ]
    
    for i, (actual, exp) in enumerate(zip(liuyue, expected)):
        month_name = ["正月", "二月", "三月", "四月", "五月", "六月",
                      "七月", "八月", "九月", "十月", "十一月", "十二月"][i]
        status = "✓" if actual == exp else "✗"
        print(f"{status} {month_name}: {actual} (期望: {exp})")
    
    print()


if __name__ == "__main__":
    test_2026_liuyue()
    test_2027_liuyue()
    test_2028_liuyue()
    print("验证完成！")
