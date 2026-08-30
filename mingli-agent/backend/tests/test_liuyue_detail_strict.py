"""测试：★问题年份流月注入含完整用忌神+交互+硬约束（消除ID100类真编造）

问题复现：报告里9月(丁酉月)错应为庚戌月；"庚戌月，劫财帮身"十神不在流月数据字段；
"9月启动求职吉窗口""11月底入职安全稳妥"是超吉凶级别的行为结论。
"""
import sys, json
sys.path.insert(0, '.')

from app.services.skill_prompts import (
    _build_context_vars,
    _format_question_year_block,
    build_authoritative_chart_basis,
)
from app.skills.divination.dayun_liunian_skill import analyze_liuyue

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

GAN_WX = {"甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土","庚":"金","辛":"金","壬":"水","癸":"水"}
ZHI_WX = {"子":"水","丑":"土","寅":"木","卯":"木","辰":"土","巳":"火","午":"火","未":"土","申":"金","酉":"金","戌":"土","亥":"水"}

PILLARS_DING = {
    "年柱": {"gan": "乙", "di": "亥"},
    "月柱": {"gan": "己", "di": "丑"},
    "日柱": {"gan": "丁", "di": "未"},
    "时柱": {"gan": "庚", "di": "戌"},
}


def _make_analysis():
    analysis = {
        "四柱": "乙亥 己丑 丁未 庚戌",
        "日主": "丁火", "旺衰结论": "身弱",
        "用神": "木火", "忌神": "金水",
        "当前大运": "辛卯 2024-2033",
        "重点流年": [],
    }
    # 25年范围：问题涉及的2027年用真实analyze_liuyue算，其他给空
    for y in range(2021, 2046):
        gz = GAN[(y - 4) % 10] + ZHI[(y - 4) % 12]
        # 丁日主 + 丁未年(2027)：真实五虎遁12月 + 典型冲合交互给的interactions
        #   9月=己酉、10月=庚戌、11月=辛亥、12月=壬子
        if y == 2027:
            liuyue = analyze_liuyue("丁未", "丁", PILLARS_DING, "木", "水", is_strong=False)
            # 叠加典型交互（模拟真实排盘interactions）
            for m in liuyue:
                if m["solar_month"] == 10:
                    m["interactions"] = ["月令亥冲年支巳，主变动（冲用神=凶）"]
                    m["reason"] = m["reason"] + "，月令亥冲年支巳冲用神"
                if m["solar_month"] == 9:
                    m["interactions"] = ["月令戌与日支未六合，主合作与稳定"]
                    m["reason"] = m["reason"] + "，有合主合作"
                if m["solar_month"] == 12:
                    m["interactions"] = ["月令丑与日支未相冲，主变动"]
                if m["solar_month"] == 11:
                    m["interactions"] = ["月令子未害，注意人际纠葛"]
                    m["reason"] = m["reason"] + "，子未害"
            judge = "凶"
            reason = "冲克日支"
        else:
            liuyue = []
            judge = "平"
            reason = ""
        analysis["重点流年"].append({
            "year": y, "ganzhi": gz, "judge": judge, "reason": reason, "liuyue": liuyue,
        })
    return analysis


ANALYSIS_DATA = _make_analysis()


def test_liuyue_detail_inject():
    """★问题年份必须写入完整流月明细：月干支/用忌神/吉凶/reason/interactions。
    少任何一项 → 模型自己补月干支或十神 → 编造。"""
    print("=" * 60)
    print("测试 1：问题年份注入12流月完整字段(干支+用忌+吉凶+reason+冲合)")
    print("=" * 60)
    question = "27年9月启动求职、10月谈离职、11月入职可行吗"
    basis = build_authoritative_chart_basis(ANALYSIS_DATA, question, 1995)
    # 找2027年段
    if "★用户问题涉及年份" not in basis or "2027" not in basis:
        print("  ❌ 未找到 2027 年★区块")
        return False
    # 2027行锚点："2027年 丁未：...★用户问题涉及年份"
    anchor = "2027年 丁未："
    start = basis.find(anchor)
    star_idx = basis.find("★用户问题涉及年份", start)
    after = basis[star_idx:star_idx+2500]
    expected_sigs = {
        "9月(己酉)": ("9月己酉月", "五虎遁9月=己酉"),
        "10月(庚戌)": ("10月庚戌月", "10月=庚戌"),
        "11月(辛亥)": ("11月辛亥月", "11月=辛亥"),
        "12月(壬子)": ("12月壬子月", "12月=壬子（实际推对防止之前的庚子月乱配错误）"),
        "地支水忌神": ("地支水忌神", "忌神标注传递到位"),
        "月令戌与日支未六合": ("月令戌与日支未六合", "冲合interactions传递到位"),
        "月令亥冲年支巳": ("月令亥冲年支巳", "典型冲合传递到位"),
        "必须严格使用本行内给出的名称": ("严格使用明细语", "明细表头强制正确使用"),
        "·食神": ("·食神", "十神名已带（天十神己=食神）"),
        "·正财": ("·正财", "十神名已带（天十神庚=正财）"),
    }
    ok = True
    for sig, (short, desc) in expected_sigs.items():
        hit = sig in after
        if not hit:
            ok = False
        print(f"  {'✅' if hit else '❌'} [{sig}] {desc}")
    if not ok:
        print(f"  ── 2027 年★后1500字:\n{after[:1500]}")
    return ok


def test_month_ganzhi_exact_rule_in_prompt():
    """prompt上下文必须包含"严格使用流月给出的月干支，禁止自行配对"等硬约束，
    否则模型会把庚戌月写成丁酉月。"""
    print()
    print("=" * 60)
    print("测试 2：prompt上下文含月干支/十神/行为结论硬约束")
    print("=" * 60)
    question = "27年9月启动求职、10月谈离职、11月入职可行吗"
    ctx = _build_context_vars(ANALYSIS_DATA, "男", question, "1995-01-01")
    kly = ctx.get("key_liunian", "")
    rules = [
        ("严格使用上方流月明细行中给出的月干支", "严格禁止1条款"),
        ("十神名称：严格使用流月明细行", "严格禁止2条款（十神强制引用）"),
        ("月份具体建议：只能基于【吉凶】等级 + 原因 + 冲合 + 十神名 四类字段展开", "严格禁止3条款（行为结论边界）"),
    ]
    ok = True
    for rule_text, desc in rules:
        hit = rule_text in kly
        if not hit:
            ok = False
        print(f"  {'✅' if hit else '❌'} [{rule_text[:20]}…] {desc}")
    return ok


if __name__ == "__main__":
    results = [test_liuyue_detail_inject(), test_month_ganzhi_exact_rule_in_prompt()]
    print()
    print(f"总结果：{sum(results)}/{len(results)} 通过")
    sys.exit(0 if all(results) else 1)
