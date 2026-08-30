"""测试：命盘权威基准构建（编造误报源头修复）

问题：之前编造检测把 chart_data 前2000字当"命盘权威基准"，但analysis_data前2000字常不含
完整流年信息，导致报告里用到的2027等年份（prompt里已注入详细）被检测器判为"命盘未提供"的编造。
修复：生成报告时与编造检测时共用同一份"精简权威基准"，双方看到的流年/流月范围完全一致。
"""
import sys, json
sys.path.insert(0, '.')

from app.services.skill_prompts import (
    _build_context_vars,
    _extract_question_years,
    _format_question_year_block,
    build_authoritative_chart_basis,
)
from app.services.eval.llm_scorer import _build_fabrication_basis  # 修复后新增


# ---- 构造最小 analysis_data（模拟排盘输出，覆盖2026-2030共5年，吉凶按27年为凶）----
def _ly(year, ganzhi, judge, reason, big_month_judge=None):
    liuyue = []
    for m in range(1, 13):
        ganzhi_map = {1: "庚寅", 2: "辛卯", 3: "壬辰", 4: "癸巳", 5: "甲午", 6: "乙未",
                      7: "丙申", 8: "丁酉", 9: "戊戌", 10: "己亥", 11: "庚子", 12: "辛丑"}
        j = "平"
        if big_month_judge and m in big_month_judge:
            j = big_month_judge[m]
        liuyue.append({"solar_month": m, "month_ganzhi": ganzhi_map[m], "judge": j, "reason": "十神作用"})
    return {
        "year": year, "ganzhi": ganzhi, "judge": judge, "reason": reason,
        "detail": {"overall_judge": judge},
        "liuyue": liuyue,
    }


ANALYSIS_DATA = {
    "四柱": "乙亥 己丑 丁未 庚戌",
    "日主": "丁火",
    "旺衰结论": "身弱",
    "用神": "木火",
    "忌神": "金水",
    "当前大运": "辛卯 2024-2033",
    # 重点流年：只给前5条，且按吉凶排序2026大吉=第1条，2027凶可能排靠后——故意构造为排不在前5的情况
    "重点流年": [
        _ly(2026, "丙午", "大吉", "纯木火用神年"),
        _ly(2030, "庚戌", "大凶", "双忌神年"),
        _ly(2035, "乙卯", "大吉", "纯用神木，官运"),
        _ly(2040, "庚申", "大凶", "金忌神年"),
        _ly(2029, "己酉", "平", "食伤旺"),
        # 以下不在前5——模拟真实"排了但没展示"的情况，故意放2027、2028
        _ly(2027, "丁未", "凶", "冲克日支", {10: "吉", 12: "大凶"}),
        _ly(2028, "戊申", "凶", "伤官当值"),
    ],
    "五行应用": {},
}
# 扩展"重点流年"覆盖2021-2045（排盘实际算了25年），模拟真实结构
_full_years = list(range(2021, 2046))
GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
_extra = []
for y in _full_years:
    if y in {d['year'] for d in ANALYSIS_DATA["重点流年"]}:
        continue
    gz = GAN[(y - 4) % 10] + ZHI[(y - 4) % 12]
    _extra.append(_ly(y, gz, "平", "平稳年"))
ANALYSIS_DATA["重点流年"].extend(_extra)


def test_extract_question_years():
    cases = [
        ("26年9月…27年是否可以离开公司", {2026, 2027}, "两位数年份"),
        ("2027年丁未年运势", {2027}, "四位数+干支"),
        ("今年2026年，问2028年能跳槽吗", {2026, 2028}, "四位数混合"),
        ("我90年出生，27年合适吗", {2027}, "'90年'为出生年且在范围外，应过滤"),
    ]
    print("=" * 60)
    print("测试 1：用户问题年份提取")
    print("=" * 60)
    ok = True
    for q, expected, desc in cases:
        got = set(_extract_question_years(q, 2021, 2045))
        passed = got == expected
        if not passed:
            ok = False
        print(f"  {'✅' if passed else '❌'} {desc}: 期望{sorted(expected)}，实际{sorted(got)}")
    return ok


def test_build_authoritative_basis_has_question_year_liuyue():
    """authoritative_basis 必须包含：
    ① 范围内全部年份的年干支（25年完整列表）
    ② 用户问题涉及的年份（2026/2027）对应12个月流月明细
    不满足 → 编造检测仍然误报
    """
    print()
    print("=" * 60)
    print("测试 2：authoritative_basis 含25年完整流年 + 问题年12流月")
    print("=" * 60)
    question = "26年9月回去岗位是否会变动，27年是否可以离开，几月能拿到赔偿"
    basis = build_authoritative_chart_basis(ANALYSIS_DATA, question, 1995)
    checks = []

    # ① 25个年份干支齐全（格式："2021辛丑平"紧凑格式）
    missing_year_tags = []
    for y in range(2021, 2046):
        tag = f"{y}{GAN[(y-4)%10]}{ZHI[(y-4)%12]}"
        if tag not in basis:
            missing_year_tags.append(tag)
    checks.append(("25年全量流年", len(missing_year_tags) == 0, missing_year_tags[:5]))

    # ② 问题年份2026、2027对应的12个流月全部存在（在"★用户问题涉及年份"段落后）
    q_years = _extract_question_years(question, 2021, 2045)
    for target_year, desc in [(y, f"{y}流月") for y in sorted(q_years)]:
        # 在"X年 干支：…★用户问题涉及年份"后的1500字内找12个月签名
        anchor = f"{target_year}年"
        year_idx = basis.find(anchor)
        star_idx = basis.find("★用户问题涉及年份", year_idx) if year_idx != -1 else -1
        window = basis[star_idx:star_idx+1500] if star_idx != -1 else ""
        missing_months = [f"{m}月(" for m in range(1, 13) if f"{m}月(" not in window]
        checks.append((desc, len(missing_months) == 0, missing_months[:5]))

    # ③ 数据边界声明存在
    checks.append(("数据边界声明", "覆盖范围" in basis and "★用户问题涉及年份" in basis, None))

    ok = True
    for desc, passed, extra in checks:
        if not passed:
            ok = False
        print(f"  {'✅' if passed else '❌'} {desc}{('；未通过项: ' + str(extra)) if extra and not passed else ''}")
    if not ok:
        # 调试：打印末尾1000字以便定位
        print(f"  ── 基准末段:\n{basis[-800:]}")
    return ok


def test_fabrication_basis_matches_authoritative():
    """编造检测的基准必须用同一份authoritative basis，不能再用chart_data前2000字。
    这样报告生成者、评测者看到的命盘范围完全一致，消除"前者拿到了后者没拿到"的误报。
    """
    print()
    print("=" * 60)
    print("测试 3：编造检测基准 与 报告生成基准 一致（误报防火墙）")
    print("=" * 60)
    question = "27年能否离职，10月合适吗"
    gen_basis = build_authoritative_chart_basis(ANALYSIS_DATA, question, 1995)
    eval_basis = _build_fabrication_basis(ANALYSIS_DATA, question, 1995)
    checks = []
    checks.append(("25年全量列表", "2021辛丑" in eval_basis and "2045乙丑" in eval_basis))
    checks.append(("2027年完整12流月", "2027年" in eval_basis and all(f"{m}月(" in eval_basis.split("2027年", 1)[-1][:2500] for m in range(1, 13))))
    # 匹配构造数据集里的2027流月值（注意：该测试用的固定ganzhi_map生成10月=己亥而非五虎遁辛亥，验证两边使用同源即可）
    checks.append(("2027+10月吉流月标注与构造数据一致", "10月(己亥)【吉】" in eval_basis))
    checks.append(("2027+12月大凶标注与构造数据一致", "12月(辛丑)【大凶】" in eval_basis))
    checks.append(("不再使用 2000 字符截断", "五行应用" not in eval_basis))
    ok = True
    for desc, passed in checks:
        if not passed:
            ok = False
        print(f"  {'✅' if passed else '❌'} {desc}")
    if not ok:
        print(f"  ── 评测基准末段:\n{eval_basis[-800:]}")
    return ok


def test_prompt_injects_basis():
    """_build_context_vars 构建的 context['key_liunian'] 必须包含生成基准（authoritative block），
    即"★用户问题涉及年份"区块、流月明细、边界声明全部进入。
    """
    print()
    print("=" * 60)
    print("测试 4：prompt context['key_liunian'] 已注入问题年份流月+边界")
    print("=" * 60)
    question = "26年9月回去，27年能否离职，几月可以离开"
    ctx = _build_context_vars(ANALYSIS_DATA, "男", question, "1995-01-01")
    kly = ctx.get("key_liunian", "")
    # 实际输出格式："- 2027年 丁未：凶（冲克日支），32岁 ★用户问题涉及年份"
    checks = [
        ("注入2026年区块", "2026年" in kly and "★用户问题涉及年份" in kly and "2026年" in kly.split("★用户问题涉及年份", 1)[0][-500:]),
        ("注入2027年区块+★标记", "2027年 丁未：" in kly and "★用户问题涉及年份" in kly),
        ("2027年12流月明细", "2027年 丁未" in kly and all(f"{m}月(" in kly.split("2027年 丁未", 1)[-1][:1500] for m in range(1, 13))),
        ("数据边界声明(2021-2045)", "命盘流年数据覆盖范围：2021-2045年" in kly or "流年覆盖范围 2021-2045" in kly),
    ]
    ok = True
    for desc, passed in checks:
        if not passed:
            ok = False
        print(f"  {'✅' if passed else '❌'} {desc}")
    return ok


if __name__ == "__main__":
    results = []
    results.append(test_extract_question_years())
    results.append(test_build_authoritative_basis_has_question_year_liuyue())
    results.append(test_fabrication_basis_matches_authoritative())
    results.append(test_prompt_injects_basis())
    print()
    print("=" * 60)
    print(f"总结果：{sum(results)}/{len(results)} 通过")
    print("=" * 60)
    sys.exit(0 if all(results) else 1)
