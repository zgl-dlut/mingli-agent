"""RED：核查流月数据全覆盖（25年×12月×2十神+五虎遁正确）

目标：保证排盘分析函数给每个重点流年的liuyue列表（若提供）必含12个月，
每个月都有：月干支、天十神、地十神、用忌神、吉凶、原因、冲合。
同时五虎遁逐月对（按2021-2045每年正月寅月干支=五虎遁(年干)匹配，然后逐月递增）
"""
import sys
sys.path.insert(0, '.')
from app.skills.orchestrator import generate_full_analysis  # 主排盘入口
from app.skills.divination.dayun_liunian_skill import (
    compute_tiangan_shishen,
    analyze_liuyue,
    TIANGAN, DIZHI, WU_HU_DUN, DIZHI_CANGGAN,
)


PILLARS_DING = {
    "年柱": {"gan": "乙", "di": "亥"},
    "月柱": {"gan": "己", "di": "丑"},
    "日柱": {"gan": "丁", "di": "未"},
    "时柱": {"gan": "庚", "di": "戌"},
}


def _check_wu_hu_dun(year_ganzhi, liuyue_list):
    """五虎遁校验：liunian年干→正月寅月天干；然后每月天干地支各+1循环
    返回缺失的月份列表或空列表（全部匹配）。
    """
    # 五虎遁：找寅月天干
    nian_gan = year_ganzhi[0]
    yin_gan_expected = WU_HU_DUN.get(nian_gan)
    if yin_gan_expected is None:
        return [f"{year_ganzhi}年五虎遁配置缺失"]
    errors = []
    # 按liuyue_list顺序，正月对应第0条还是第solar_month=2的那条？
    # 注意LIUYUE_MONTHS定义:
    # 0→(2,寅)  1→(3,卯)  ... 10→(12,子) 11→(1,丑)
    # 所以按solar_month排序后得到 [2月寅,3月卯,...,12月子,1月丑]
    sorted_ly = sorted(liuyue_list, key=lambda x: x["solar_month"] if x["solar_month"] != 1 else 13)
    start_idx = TIANGAN.index(yin_gan_expected)
    di_order_start_idx = DIZHI.index("寅")
    for offset, lm in enumerate(sorted_ly):
        tian_expected = TIANGAN[(start_idx + offset) % 10]
        di_expected = DIZHI[(di_order_start_idx + offset) % 12]
        mgz_expected = tian_expected + di_expected
        if lm["month_ganzhi"] != mgz_expected:
            errors.append(f"{year_ganzhi} solar_month={lm['solar_month']} 期望{mgz_expected} 实际{lm['month_ganzhi']}")
    return errors


def test_range_25_years_liuyue_integrity():
    """2021-2045共25年，每年调用analyze_liuyue后核查：
    ① 12个月齐全 ② 五虎遁正确 ③ shishen_tian/shishen_di都非空且与compute_tiangan_shishen一致
    """
    print("=" * 60)
    print("测试 1：2021-2045 25年×12月=300个月 十神+五虎遁完整性")
    print("=" * 60)
    failures = []
    total_months = 0
    total_ok_months = 0
    for y in range(2021, 2046):
        gz = TIANGAN[(y - 4) % 10] + DIZHI[(y - 4) % 12]
        liuyue = analyze_liuyue(gz, "丁", PILLARS_DING, "木", "水", is_strong=False)
        if len(liuyue) != 12:
            failures.append(f"{y}{gz}: 月份数不是12，是{len(liuyue)}")
            continue
        # 五虎遁
        wh_err = _check_wu_hu_dun(gz, liuyue)
        failures.extend(wh_err[:3])
        # 字段完整性
        for lm in liuyue:
            total_months += 1
            ok = True
            req = ["solar_month", "month_ganzhi", "tian_wuxing", "di_wuxing",
                   "is_yongshen", "is_jishen", "judge", "reason", "interactions",
                   "shishen_tian", "shishen_di"]
            missing = [k for k in req if k not in lm or (isinstance(lm[k], str) and not lm[k])]
            if missing:
                ok = False
                failures.append(f"{y}{gz} M{lm['solar_month']}({lm.get('month_ganzhi','?')}) 缺字段{missing}")
            # 十神一致性
            mgz = lm.get("month_ganzhi", "")
            if len(mgz) == 2:
                tg, dg = mgz[0], mgz[1]
                exp_tian_shi = compute_tiangan_shishen(tg, "丁")
                from app.skills.divination.dayun_liunian_skill import DIZHI_CANGGAN
                main_gan = (DIZHI_CANGGAN.get(dg) or [""])[0]
                exp_di_shi = compute_tiangan_shishen(main_gan, "丁") if main_gan else ""
                if exp_tian_shi and exp_tian_shi != lm.get("shishen_tian"):
                    ok = False
                    failures.append(f"{y}{gz} M{lm['solar_month']} tian十神不一致：期望{exp_tian_shi} 实际{lm.get('shishen_tian')}")
                if exp_di_shi and exp_di_shi != lm.get("shishen_di"):
                    ok = False
                    failures.append(f"{y}{gz} M{lm['solar_month']} di十神不一致：期望{exp_di_shi} 实际{lm.get('shishen_di')}")
            if ok:
                total_ok_months += 1
    print(f"  检查月份总数: {total_months}")
    print(f"  全部字段+十神一致的月份数: {total_ok_months}")
    if failures:
        print(f"  ❌ 前{min(15,len(failures))}条失败:")
        for f in failures[:15]:
            print(f"    - {f}")
    passed = len(failures) == 0 and total_months == 25 * 12 and total_ok_months == 25 * 12
    print(f"  {'✅' if passed else '❌'} 总体 {total_ok_months}/{total_months} 通过，失败类{len(failures)}条")
    return passed


def test_main_paipan_returns_liuyue_shishen():
    """主排盘generate_full_analysis返回的analysis_data -> 重点流年 -> 每条应该都有liuyue list且含十神字段"""
    print()
    print("=" * 60)
    print("测试 2：主排盘 generate_full_analysis 重点流年含 12流月 + 十神 全覆盖")
    print("=" * 60)
    try:
        # 北京经纬度 116.4,39.9
        result = generate_full_analysis(
            birth_date="1995-06-15",
            birth_time="14:30",
            longitude=116.4, latitude=39.9,
            gender="男",
            location="北京",
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  🔥 主排盘抛异常: {e}")
        return False
    if isinstance(result, tuple):
        result = result[0]  # sometimes returns tuple (analysis, extra)
    # generate_full_analysis 直接返回analysis对象（不包analysis_data）
    analysis = result if isinstance(result, dict) and "重点流年" in (result or {}) else {}
    if isinstance(result, dict) and "analysis_data" in result:
        analysis = result["analysis_data"]
    key_liunian = analysis.get("重点流年", []) if isinstance(analysis, dict) else []
    year_cnt = len(key_liunian)
    sizhu = analysis.get("四柱", "")
    yongshen = analysis.get("用神", "")
    jishen = analysis.get("忌神", "")
    print(f"  四柱: {sizhu}  用神: {yongshen}  忌神: {jishen}")
    missing_months = []
    checked_years = 0
    for ly in key_liunian:
        if not isinstance(ly, dict):
            continue
        liuyue = ly.get("liuyue", [])
        y = ly.get("year")
        gz = ly.get("ganzhi")
        checked_years += 1
        if len(liuyue) != 12:
            missing_months.append(f"{y}{gz}: liuyue不是12条（{len(liuyue)}条）")
            continue
        for m in liuyue:
            if not m.get("shishen_tian") or not m.get("shishen_di"):
                missing_months.append(f"{y}{gz} M{m.get('solar_month')}({m.get('month_ganzhi')}) 缺十神 st={m.get('shishen_tian')} sd={m.get('shishen_di')}")
                break
    passed = (checked_years >= 25 and len(missing_months) == 0)
    print(f"  重点流年条目数: {year_cnt}  非空年数: {checked_years} {'✅' if checked_years>=25 else '❌(<25)'}")
    print(f"  完整12流月+十神齐全的年数: {checked_years - len([x for x in missing_months if '不是12条' in x]) - len([x for x in missing_months if '缺十神' in x])}/{checked_years}")
    if missing_months:
        print(f"  失败项前15:")
        for f in missing_months[:15]:
            print(f"    - {f}")
    print(f"  {'✅' if passed else '❌'} 综合")
    return passed


if __name__ == "__main__":
    r1 = test_range_25_years_liuyue_integrity()
    r2 = test_main_paipan_returns_liuyue_shishen()
    print()
    print(f"总结果：{sum([r1,r2])}/2 通过")
    sys.exit(0 if r1 and r2 else 1)
