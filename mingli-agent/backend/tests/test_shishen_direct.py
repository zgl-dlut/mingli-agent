"""测试：十神由排盘算法直接算好（不让LLM推），注入到prompt与编造基准。

十神规则（日主天干为基准）：
  同我(比劫)：同阴阳=比肩，异阴阳=劫财
  生我(印枭)：异阴阳=正印，同阴阳=偏印
  我生(食伤)：异阴阳=伤官，同阴阳=食神
  克我(官杀)：异阴阳=正官，同阴阳=七杀(偏官)
  我克(财星)：异阴阳=正财，同阴阳=偏财

例如日主丁火（阴）：
  甲阳木→正印  乙阴木→偏印  丙阳火→劫财  丁阴火→比肩
  戊阳土→伤官  己阴土→食神  庚阳金→正财  辛阴金→偏财
  壬阳水→正官  癸阴水→七杀
"""
import sys
sys.path.insert(0, '.')

from app.services.skill_prompts import (
    _build_context_vars,
    build_authoritative_chart_basis,
)
from app.skills.divination.dayun_liunian_skill import (
    compute_tiangan_shishen,
    analyze_liuyue,
)


TEST_CASES_DING = [
    # (天干, 日主丁阴, 期望十神) 见上方表
    ("甲", "正印"), ("乙", "偏印"), ("丙", "劫财"), ("丁", "比肩"),
    ("戊", "伤官"), ("己", "食神"), ("庚", "正财"), ("辛", "偏财"),
    ("壬", "正官"), ("癸", "七杀"),
]


def test_compute_tiangan_shishen():
    """函数 compute_tiangan_shishen 应存在并按规则输出十神名称"""
    print("=" * 60)
    print("测试 1：compute_tiangan_shishen(day_tian='丁') 10天干十神表正确")
    print("=" * 60)
    ok = True
    for tg, expected in TEST_CASES_DING:
        got = compute_tiangan_shishen(tg, "丁")
        passed = got == expected
        if not passed:
            ok = False
        print(f"  {'✅' if passed else '❌'} 丁日主 + {tg}干 -> {got}(期望{expected})")
    return ok


def test_analyze_liuyue_returns_shishen_fields():
    """analyze_liuyue 返回的每个月必须带 shishen_tian / shishen_di 字段"""
    print()
    print("=" * 60)
    print("测试 2：analyze_liuyue 每个月含十神字段(shishen_tian/shishen_di)")
    print("=" * 60)
    pillars = {
        "年柱": {"gan": "乙", "di": "亥"},
        "月柱": {"gan": "己", "di": "丑"},
        "日柱": {"gan": "丁", "di": "未"},
        "时柱": {"gan": "庚", "di": "戌"},
    }
    liuyue = analyze_liuyue("丁未", "丁", pillars, "木", "水", is_strong=False)
    ok = True
    for lm in liuyue:
        has_st = "shishen_tian" in lm and isinstance(lm.get("shishen_tian"), str) and bool(lm["shishen_tian"])
        has_sd = "shishen_di" in lm and isinstance(lm.get("shishen_di"), str) and bool(lm["shishen_di"])
        if not has_st or not has_sd:
            ok = False
            print(f"  ❌ {lm['solar_month']}月({lm['month_ganzhi']}) 缺十神字段 shishen_tian={lm.get('shishen_tian')} shishen_di={lm.get('shishen_di')}")
    if ok:
        # 月干支校验：9=己酉,10=庚戌,11=辛亥,12=壬子
        expected_mgz = {9: "己酉", 10: "庚戌", 11: "辛亥", 12: "壬子"}
        for m, mgz in expected_mgz.items():
            row = [l for l in liuyue if l['solar_month'] == m][0]
            good = row["month_ganzhi"] == mgz
            if not good:
                ok = False
            print(f"  {'✅' if good else '❌'} {m}月={row['month_ganzhi']}(期望{mgz}) tian十神={row['shishen_tian']} di十神={row['shishen_di']}【{row['judge']}】")
    return ok


def test_prompt_injects_shishen_names():
    """prompt里流月明细行需包含十神名（用户可见+检测器可见都用同一份）"""
    print()
    print("=" * 60)
    print("测试 3：prompt流月明细行直接带十神名(含庚正财/辛偏财/己食神典型)")
    print("=" * 60)
    pillars = {
        "年柱": {"gan": "乙", "di": "亥"}, "月柱": {"gan": "己", "di": "丑"},
        "日柱": {"gan": "丁", "di": "未"}, "时柱": {"gan": "庚", "di": "戌"},
    }
    liuyue = analyze_liuyue("丁未", "丁", pillars, "木", "水", is_strong=False)
    # 构造假 analysis_data
    analysis_data = {
        "四柱": "乙亥 己丑 丁未 庚戌",
        "日主": "丁火", "旺衰结论": "身弱",
        "用神": "木火", "忌神": "金水",
        "当前大运": "辛卯 2024-2033",
        "重点流年": [{
            "year": 2027, "ganzhi": "丁未", "judge": "凶",
            "reason": "冲克日支",
            "liuyue": liuyue,
        }] + [
            {"year": y, "ganzhi": "a", "judge": "平", "liuyue": []}
            for y in list(range(2021, 2027)) + list(range(2028, 2046))
        ],
    }
    q = "27年9月启动求职、10月谈离职可行吗"
    kly = _build_context_vars(analysis_data, "男", q, "1995-01-01")["key_liunian"]
    basis = build_authoritative_chart_basis(analysis_data, q, 1995)
    # 丁日主+2027丁未年（五虎遁丁年壬寅正月起=对应2月）：
    #   9月=己酉(己土=食神，酉金=偏财)
    #   10月=庚戌(庚金=正财，戌土藏干主气戊土=伤官)
    #   11月=辛亥(辛金=偏财，亥水藏干主气壬水=正官)
    checks = [
        ("9月(己酉) 天干十神=食神", "9月(己酉)" in kly and ("·食神" in kly.split("9月(己酉)", 1)[-1][:200])),
        ("9月(己酉) 地支十神=偏财", "9月(己酉)" in kly and ("·偏财" in kly.split("9月(己酉)", 1)[-1][:200])),
        ("10月(庚戌) 天干十神=正财", "10月(庚戌)" in kly and ("·正财" in kly.split("10月(庚戌)", 1)[-1][:200])),
        ("10月(庚戌) 地支十神=伤官", "10月(庚戌)" in kly and ("·伤官" in kly.split("10月(庚戌)", 1)[-1][:200])),
        ("11月(辛亥) 地支十神=正官", "11月(辛亥)" in kly and ("·正官" in kly.split("11月(辛亥)", 1)[-1][:200])),
        ("生成/评测基准一致：9月十神同现", "9月(己酉)" in basis and "·食神" in basis.split("9月(己酉)", 1)[-1][:200]),
        ("约束写：十神名称严格使用明细行给的", "十神名称：严格使用流月明细行" in kly),
    ]
    ok = True
    for desc, passed in checks:
        if not passed:
            ok = False
        print(f"  {'✅' if passed else '❌'} {desc}")
    if not ok:
        i = kly.find("9月(庚戌)")
        print(f"  ── 实际9月行附近:\n{kly[i:i+300]}")
    return ok


if __name__ == "__main__":
    results = []
    for fn in [test_compute_tiangan_shishen, test_analyze_liuyue_returns_shishen_fields, test_prompt_injects_shishen_names]:
        try:
            results.append(fn())
        except Exception as e:
            results.append(False)
            print(f"  🔥 {fn.__name__} 抛出异常: {e}")
    print()
    print(f"总结果：{sum(results)}/{len(results)} 通过")
    sys.exit(0 if all(results) else 1)
