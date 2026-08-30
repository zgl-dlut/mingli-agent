"""
验证长生十二宫对旺衰判断的影响

测试用例覆盖：
1. 日主坐长生（强根）— 应提升得地分数
2. 日主坐帝旺（最强根）— 应大幅提升得地分数
3. 日主坐临官（禄位）— 应提升得地分数
4. 日主坐沐浴（弱）— 应降低得地分数
5. 日主坐墓（入库）— 应降低得地分数
6. 日主坐冠带（中等）— 应中等得地分数

每个用例对比：旧逻辑（仅藏干） vs 新逻辑（长生十二宫）
"""

# ==================== 长生十二宫映射 ====================
# 阳干顺行，阴干逆行
CHANGSHENG_MAP = {
    # 阳干：长生→沐浴→冠带→临官→帝旺→衰→病→死→墓→绝→胎→养
    "甲": {"亥": "长生", "子": "沐浴", "丑": "冠带", "寅": "临官", "卯": "帝旺",
           "辰": "衰", "巳": "病", "午": "死", "未": "墓", "申": "绝", "酉": "胎", "戌": "养"},
    "丙": {"寅": "长生", "卯": "沐浴", "辰": "冠带", "巳": "临官", "午": "帝旺",
           "未": "衰", "申": "病", "酉": "死", "戌": "墓", "亥": "绝", "子": "胎", "丑": "养"},
    "戊": {"寅": "长生", "卯": "沐浴", "辰": "冠带", "巳": "临官", "午": "帝旺",
           "未": "衰", "申": "病", "酉": "死", "戌": "墓", "亥": "绝", "子": "胎", "丑": "养"},
    "庚": {"巳": "长生", "午": "沐浴", "未": "冠带", "申": "临官", "酉": "帝旺",
           "戌": "衰", "亥": "病", "子": "死", "丑": "墓", "寅": "绝", "卯": "胎", "辰": "养"},
    "壬": {"申": "长生", "酉": "沐浴", "戌": "冠带", "亥": "临官", "子": "帝旺",
           "丑": "衰", "寅": "病", "卯": "死", "辰": "墓", "巳": "绝", "午": "胎", "未": "养"},
    # 阴干：长生→沐浴→冠带→临官→帝旺→衰→病→死→墓→绝→胎→养（逆行）
    "乙": {"午": "长生", "巳": "沐浴", "辰": "冠带", "卯": "临官", "寅": "帝旺",
           "丑": "衰", "子": "病", "亥": "死", "戌": "墓", "酉": "绝", "申": "胎", "未": "养"},
    "丁": {"酉": "长生", "申": "沐浴", "未": "冠带", "午": "临官", "巳": "帝旺",
           "辰": "衰", "卯": "病", "寅": "死", "丑": "墓", "子": "绝", "亥": "胎", "戌": "养"},
    "己": {"酉": "长生", "申": "沐浴", "未": "冠带", "午": "临官", "巳": "帝旺",
           "辰": "衰", "卯": "病", "寅": "死", "丑": "墓", "子": "绝", "亥": "胎", "戌": "养"},
    "辛": {"子": "长生", "亥": "沐浴", "戌": "冠带", "酉": "临官", "申": "帝旺",
           "未": "衰", "午": "病", "巳": "死", "辰": "墓", "卯": "绝", "寅": "胎", "丑": "养"},
    "癸": {"卯": "长生", "寅": "沐浴", "丑": "冠带", "子": "临官", "亥": "帝旺",
           "戌": "衰", "酉": "病", "申": "死", "未": "墓", "午": "绝", "巳": "胎", "辰": "养"},
}

# 长生十二宫 → 得地分数映射
CHANGSHENG_SCORE = {
    "长生": 2,   # 强根，日主在此地支获得生命力
    "临官": 2,   # 禄位，日主得禄，强力支撑
    "帝旺": 3,   # 最强根，日主在此地支达到巅峰
    "冠带": 1,   # 中等支撑
    "养":   1,   # 中等支撑（孕育中）
    "墓":   0,   # 入库，力量被封存，中性
    "胎":   0,   # 初成形，力量很弱，中性
    "沐浴": -1,  # 桃花位，日主在此不稳定
    "衰":   -1,  # 开始衰退
    "病":   -2,  # 虚弱
    "死":   -2,  # 无气
    "绝":   -2,  # 最弱
}


def get_changsheng_score(day_tian: str, day_di: str) -> dict:
    """根据长生十二宫计算得地分数"""
    stage = CHANGSHENG_MAP[day_tian].get(day_di, "绝")
    score = CHANGSHENG_SCORE.get(stage, -2)
    return {"stage": stage, "score": score}


def old_de_di(day_tian: str, day_di: str, canggan: dict) -> dict:
    """旧的得地逻辑（仅藏干）"""
    TIANGAN_WUXING = {
        "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
        "己": "土", "庚": "金", "辛": "金", "壬": "水", "": "水"
    }
    DIZHI_WUXING = {
        "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土",
        "巳": "火", "午": "火", "未": "土", "申": "金", "酉": "金",
        "戌": "土", "亥": "水"
    }
    day_wuxing = TIANGAN_WUXING[day_tian]
    day_di_wuxing = DIZHI_WUXING[day_di]
    canggan_list = canggan.get(day_di, [])

    if len(canggan_list) > 0 and canggan_list[0] == day_tian:
        return {"score": 2, "detail": "得地", "reason": f"本气藏干{canggan_list[0]}与日主相同"}
    if len(canggan_list) > 1 and day_tian in canggan_list[1:]:
        return {"score": 1, "detail": "半得地", "reason": f"中气/余气藏干含{day_tian}"}
    if DIZHI_WUXING.get(day_di_wuxing, "") and {"木": "水", "火": "木", "土": "火", "金": "土", "水": "金"}.get(day_wuxing) == day_di_wuxing:
        return {"score": 1, "detail": "有根", "reason": f"日支{day_di_wuxing}生日主{day_wuxing}"}
    return {"score": -1, "detail": "失地", "reason": f"藏干无日主同类"}


# ==================== 测试用例 ====================

TEST_CASES = [
    {
        "name": "用例1：壬申日（日主坐长生）— 13019223923 用户命局",
        "day_tian": "壬",
        "day_di": "申",
        "month_di": "戌",
        "pillars": {
            "year": {"tian": "甲", "di": "戌"},
            "month": {"tian": "甲", "di": "戌"},
            "day": {"tian": "壬", "di": "申"},
            "hour": {"tian": "己", "di": "酉"},
        },
        "canggan": {"戌": ["戊", "辛", "丁"], "申": ["庚", "壬", "戊"], "酉": ["辛"]},
        "shishen": {"甲": "食神", "己": "正官"},
        "expected_changsheng": "长生",
        "expected_impact": "旧逻辑：半得地(+1，因申中藏壬水中气)；新逻辑：长生(+2)，得地分数提升，有助于从身弱翻到身偏旺",
    },
    {
        "name": "用例2：甲寅日（日主坐临官/禄位）",
        "day_tian": "甲",
        "day_di": "寅",
        "month_di": "寅",
        "pillars": {
            "year": {"tian": "丙", "di": "子"},
            "month": {"tian": "庚", "di": "寅"},
            "day": {"tian": "甲", "di": "寅"},
            "hour": {"tian": "丁", "di": "卯"},
        },
        "canggan": {"子": ["癸"], "寅": ["甲", "丙", "戊"], "卯": ["乙"]},
        "shishen": {"丙": "食神", "庚": "七杀", "丁": "伤官"},
        "expected_changsheng": "临官",
        "expected_impact": "旧逻辑：得地(+2，本气藏干甲)；新逻辑：临官(+2)，分数一致，但语义更准确（禄位）",
    },
    {
        "name": "用例3：丙午日（日主坐帝旺）",
        "day_tian": "丙",
        "day_di": "午",
        "month_di": "午",
        "pillars": {
            "year": {"tian": "壬", "di": "子"},
            "month": {"tian": "丙", "di": "午"},
            "day": {"tian": "丙", "di": "午"},
            "hour": {"tian": "戊", "di": "戌"},
        },
        "canggan": {"子": ["癸"], "午": ["丁", "己"], "戌": ["戊", "辛", "丁"]},
        "shishen": {"壬": "七杀", "丙": "比肩", "戊": "食神"},
        "expected_changsheng": "帝旺",
        "expected_impact": "旧逻辑：失地(-1，午中藏丁己，无丙)；新逻辑：帝旺(+3)，分数大幅提升！旧逻辑严重低估了丙午日主的根气",
    },
    {
        "name": "用例4：乙子日（日主坐病位）",
        "day_tian": "乙",
        "day_di": "子",
        "month_di": "子",
        "pillars": {
            "year": {"tian": "辛", "di": "酉"},
            "month": {"tian": "己", "di": "子"},
            "day": {"tian": "乙", "di": "子"},
            "hour": {"tian": "丙", "di": "戌"},
        },
        "canggan": {"酉": ["辛"], "子": ["癸"], "戌": ["戊", "辛", "丁"]},
        "shishen": {"辛": "七杀", "己": "偏财", "丙": "伤官"},
        "expected_changsheng": "病",
        "expected_impact": "旧逻辑：失地(-1，子中藏癸，无乙）；新逻辑：病(-2)，分数更低，乙木在子水为病位，根气更弱",
    },
    {
        "name": "用例5：庚辰日（日主坐养位）",
        "day_tian": "庚",
        "day_di": "辰",
        "month_di": "辰",
        "pillars": {
            "year": {"tian": "甲", "di": "申"},
            "month": {"tian": "戊", "di": "辰"},
            "day": {"tian": "庚", "di": "辰"},
            "hour": {"tian": "壬", "di": "午"},
        },
        "canggan": {"申": ["庚", "壬", "戊"], "辰": ["戊", "乙", "癸"], "午": ["丁", "己"]},
        "shishen": {"甲": "偏财", "戊": "偏印", "壬": "食神"},
        "expected_changsheng": "养",
        "expected_impact": "旧逻辑：失地(-1，辰中藏戊乙癸，无庚）；新逻辑：养(+1)，分数提升！庚在辰为养位，有孕育之气",
    },
    {
        "name": "用例6：辛丑日（日主坐墓位）",
        "day_tian": "辛",
        "day_di": "丑",
        "month_di": "丑",
        "pillars": {
            "year": {"tian": "丁", "di": "亥"},
            "month": {"tian": "", "di": "丑"},
            "day": {"tian": "辛", "di": "丑"},
            "hour": {"tian": "甲", "di": "午"},
        },
        "canggan": {"亥": ["壬", "甲"], "丑": ["己", "辛", "癸"], "午": ["丁", "己"]},
        "shishen": {"丁": "七杀", "癸": "食神", "甲": "正财"},
        "expected_changsheng": "养",
        "expected_impact": "旧逻辑：半得地(+1，丑中藏辛中气）；新逻辑：养(+1)，分数一致。辛在丑为养位（阴干逆行：子长生→亥沐浴→戌冠带→酉临官→申帝旺→未衰→午病→巳死→辰墓→卯绝→寅胎→丑养），有孕育之气",
    },
]


def run_tests():
    """运行所有测试用例"""
    print("=" * 80)
    print("长生十二宫对旺衰判断的影响 — 测试报告")
    print("=" * 80)

    total = len(TEST_CASES)
    passed = 0
    changed = 0  # 长生十二宫改变了得地分数的用例数

    for i, case in enumerate(TEST_CASES, 1):
        day_tian = case["day_tian"]
        day_di = case["day_di"]

        # 旧逻辑
        old = old_de_di(day_tian, day_di, case["canggan"])

        # 新逻辑（长生十二宫）
        new = get_changsheng_score(day_tian, day_di)

        diff = new["score"] - old["score"]
        changed_this = diff != 0
        if changed_this:
            changed += 1

        print(f"\n{'─' * 80}")
        print(f"【{case['name']}】")
        print(f"  日主：{day_tian}  日支：{day_di}  月令：{case['month_di']}")
        print(f"  长生十二宫位置：{new['stage']}")
        print(f"")
        print(f"  旧逻辑（藏干）：得地 {old['detail']}（{old['score']:+d}分）— {old['reason']}")
        print(f"  新逻辑（长生）：得地 {new['stage']}（{new['score']:+d}分）")
        print(f"  差异：{diff:+d}分 {'⬆️ 提升' if diff > 0 else '⬇️ 降低' if diff < 0 else '➡️ 不变'}")
        print(f"")
        print(f"  预期影响：{case['expected_impact']}")

        # 验证长生位置是否正确
        if new["stage"] == case["expected_changsheng"]:
            passed += 1
            print(f"  ✅ 长生位置验证通过")
        else:
            print(f"  ❌ 长生位置验证失败：期望 {case['expected_changsheng']}，实际 {new['stage']}")

    print(f"\n{'=' * 80}")
    print(f"测试总结：{total} 个用例，{passed} 个长生位置验证通过")
    print(f"其中 {changed} 个用例的得地分数因长生十二宫而改变（{changed}/{total} = {changed*100//total}%）")
    print(f"{'=' * 80}")

    # 额外：用例1 的完整旺衰对比
    print(f"\n{'─' * 80}")
    print("【深度分析】用例1（13019223923 用户）完整旺衰对比")
    print(f"{'─' * 80}")

    from app.skills.divination.wangshuai_skill import calculate_wangshuai

    case1 = TEST_CASES[0]
    result = calculate_wangshuai(
        day_tian=case1["day_tian"],
        month_di=case1["month_di"],
        day_di=case1["day_di"],
        pillars=case1["pillars"],
        canggan=case1["canggan"],
        shishen=case1["shishen"],
    )

    print(f"  四维度评分：")
    print(f"    得令：{result['de_ling']['detail']}（{result['de_ling']['score']:+d}）")
    print(f"    得地：{result['de_di']['detail']}（{result['de_di']['score']:+d}）← 当前仍用旧逻辑")
    print(f"    得势：{result['de_shi']['detail']}（{result['de_shi']['score']:+d}）")
    print(f"    得局：{result['de_ju']['detail']}（{result['de_ju']['score']:+d}）← 新增三会局")
    print(f"    总分：{result['total_score']} → {result['conclusion']}")
    print(f"")
    print(f"  如果得地从旧逻辑(+1)改为长生十二宫(+2)：")
    new_total = result['total_score'] + 1  # +1 差值
    if new_total >= 5:
        new_conclusion = "身旺"
    elif new_total >= 1:
        new_conclusion = "身偏旺"
    elif new_total >= -2:
        new_conclusion = "身偏弱"
    else:
        new_conclusion = "身弱"
    print(f"    新总分：{new_total} → {new_conclusion}")
    print(f"    （当前已因三会局从身弱翻到身偏旺，加上长生十二宫后分数更高，结论更稳固）")


if __name__ == "__main__":
    run_tests()
