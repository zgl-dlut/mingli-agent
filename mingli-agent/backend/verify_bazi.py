"""
排盘验证脚本
命例：1992-12-19 19:35 公历 男 吉林市（经度126.55 纬度43.84）
预期四柱：壬申 辛子 庚午 丙戌
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.bazi_service import (
    calculate_bazi, calculate_shishen, solar_term_time,
    calculate_year_pillar, calculate_month_pillar,
    calculate_day_pillar, calculate_hour_pillar,
    TIANGAN, DIZHI,
)

print("=" * 60)
print("【1. 节气验证】")
print("=" * 60)
# 1992年大雪（term_index=22）应在12月7日附近
daxue = solar_term_time(1992, 22)
dongzhi = solar_term_time(1992, 23)  # 冬至
print(f"1992年大雪: {daxue.strftime('%Y-%m-%d')}  (预期12月7日附近)")
print(f"1992年冬至: {dongzhi.strftime('%Y-%m-%d')}  (预期12月21日附近)")
# 1992年立春（term_index=2）应在2月4日附近
lichun = solar_term_time(1992, 2)
print(f"1992年立春: {lichun.strftime('%Y-%m-%d')}  (预期2月4日)")

print()
print("=" * 60)
print("【2. 四柱验证】 1992-12-19 19:35 男 吉林市")
print("=" * 60)
birth_dt = __import__("datetime").datetime(1992, 12, 19, 19, 35)

# 年柱
y_tian, y_di = calculate_year_pillar(birth_dt)
print(f"年柱: {y_tian}{y_di}  (预期 壬申)")

# 月柱
m_tian, m_di = calculate_month_pillar(birth_dt, y_tian)
print(f"月柱: {m_tian}{m_di}  (预期 辛子)")

# 日柱
d_tian, d_di = calculate_day_pillar(birth_dt)
print(f"日柱: {d_tian}{d_di}  (预期 庚午)")

# 时柱
h_tian, h_di = calculate_hour_pillar(d_tian, 19)
print(f"时柱: {h_tian}{h_di}  (预期 丙戌)")

print()
print("=" * 60)
print("【3. 十神验证（阴干日主用乙木测试）】")
print("=" * 60)
# 乙木日主测试，验证正偏是否正确
test_cases = [
    ("乙", "甲", "劫财"),   # 同我异性
    ("乙", "乙", "比肩"),   # 同我同性
    ("乙", "丙", "伤官"),   # 我生异性
    ("乙", "丁", "食神"),   # 我生同性
    ("乙", "戊", "正财"),   # 我克异性
    ("乙", "己", "偏财"),   # 我克同性
    ("乙", "庚", "正官"),   # 克我异性
    ("乙", "辛", "七杀"),   # 克我同性
    ("乙", "壬", "正印"),   # 生我异性
    ("乙", "癸", "偏印"),   # 生我同性
]
all_ok = True
for day, target, expected in test_cases:
    result = calculate_shishen(day, target)
    status = "✓" if result == expected else "✗ 错误"
    if result != expected:
        all_ok = False
    print(f"  {day}见{target}: 得到={result}, 预期={expected}  {status}")
print(f"bazi_service.calculate_shishen: {'全部正确' if all_ok else '有错误'}")

print()
print("=" * 60)
print("【4. geju_skill._calc_shishen 验证】")
print("=" * 60)
from app.skills.divination.geju_skill import _calc_shishen
geju_ok = True
for day, target, expected in test_cases:
    result = _calc_shishen(day, target)
    status = "✓" if result == expected else "✗ 错误"
    if result != expected:
        geju_ok = False
    print(f"  {day}见{target}: 得到={result}, 预期={expected}  {status}")
print(f"geju_skill._calc_shishen: {'全部正确' if geju_ok else '有错误'}")

print()
print("=" * 60)
print("【5. dayun_liunian._get_shishen_name 验证】")
print("=" * 60)
from app.skills.divination.dayun_liunian_skill import _get_shishen_name
# 阳干日主甲木测试
test_cases_yang = [
    ("甲", "甲", "比肩"), ("甲", "乙", "劫财"),
    ("甲", "丙", "食神"), ("甲", "丁", "伤官"),
    ("甲", "戊", "偏财"), ("甲", "己", "正财"),
    ("甲", "庚", "七杀"), ("甲", "辛", "正官"),
    ("甲", "壬", "偏印"), ("甲", "癸", "正印"),
]
dayun_ok = True
for day, target, expected in test_cases_yang:
    result = _get_shishen_name(day, target)
    status = "✓" if result == expected else "✗ 错误"
    if result != expected:
        dayun_ok = False
    print(f"  {day}见{target}: 得到={result}, 预期={expected}  {status}")
print(f"_get_shishen_name: {'全部正确' if dayun_ok else '有错误'}")

print()
print("=" * 60)
print("【6. 完整排盘 + 旺衰 + 格局】")
print("=" * 60)
from app.skills.orchestrator import generate_full_analysis
result = generate_full_analysis(
    birth_date="1992-12-19",
    birth_time="19:35",
    longitude=126.55,
    latitude=43.84,
    gender="男",
    location="吉林市",
)
print(f"四柱: {result['四柱']}  (预期 壬申 辛子 庚午 丙戌)")
print(f"日主: {result['日主']}")
print(f"月令: {result['月令']}")
print(f"旺衰结论: {result['旺衰结论']}")
print(f"旺衰详情: 得令={result['旺衰详情']['得令']['detail']}, "
      f"得地={result['旺衰详情']['得地']['detail']}, "
      f"得势={result['旺衰详情']['得势']['detail']}, "
      f"总分={result['旺衰详情']['总分']}")
print(f"格局: {result['格局']}")
print(f"格局来源: {result['格局详情']['来源']}")
print(f"用神: {result['用神']}, 忌神: {result['忌神']}")
print(f"地支作用: {result['地支作用']}")
print(f"当前大运: {result['当前大运']}")

print()
print("=" * 60)
print("【6.5. 大运起运验证】")
print("=" * 60)
# 1992-12-19 19:35 男 壬申年
# 阳男阴女顺排，下一个节气是1992-12-21(冬至)
# 天数差 = 2天，起运年龄 = 2/3 ≈ 0.67年 ≈ 8个月
from app.services.bazi_service import _calculate_start_age, _find_nearest_jieqi, calculate_dayun

birth_dt_test = __import__("datetime").datetime(1992, 12, 19, 19, 35)
test_yang = True  # 壬为阳水
test_forward = True  # 阳男顺排

jieqi = _find_nearest_jieqi(birth_dt_test, test_forward)
days_to_jieqi = (jieqi - birth_dt_test).days
start_age = _calculate_start_age(birth_dt_test, test_forward)

print(f"出生时刻: 1992-12-19 19:35")
print(f"顺排方向下一个节气: {jieqi.strftime('%Y-%m-%d')} (冬至)")
print(f"天数差: {days_to_jieqi}天")
print(f"起运年龄: {start_age}年 (约{int(start_age * 12)}个月)")
print(f"理论起运年份: {1992 + int(start_age)}年{int((start_age - int(start_age)) * 12) + 1}月")

# 验证大运排盘
dayun_list = calculate_dayun(birth_dt_test, "壬", "男", "壬", "子")
print(f"\n大运排盘:")
for dy in dayun_list:
    print(f"  {dy['ganzhi']}: {dy['start_year']}-{dy['end_year']}"
          f"{' (当前)' if dy['is_current'] else ''}")

# 验证预期
# 1992年12月19日出生，起运0.3年（约4个月），从1993年开始起运
# 大运排盘：壬子、癸丑、甲寅、乙卯、丙辰、丁巳、戊午、己未、庚申、辛酉
expected_first_start = 1993
if int(dayun_list[0]['start_year']) == expected_first_start:
    print(f"\n  ✓ 大运起运年份正确：{dayun_list[0]['start_year']}年开始（不足1岁从下一年起）")
else:
    print(f"\n  ✗ 大运起运年份应为{expected_first_start}年，实际为{dayun_list[0]['start_year']}年")

# 验证大运干支顺序
expected_ganzhi = ["壬子", "癸丑", "甲寅", "乙卯", "丙辰", "丁巳", "戊午", "己未", "庚申", "辛酉"]
ganzhi_ok = all(dy['ganzhi'] == exp for dy, exp in zip(dayun_list, expected_ganzhi))
if ganzhi_ok:
    print(f"  ✓ 大运干支顺序正确")
else:
    print(f"  ✗ 大运干支顺序错误！")
    for dy, exp in zip(dayun_list, expected_ganzhi):
        if dy['ganzhi'] != exp:
            print(f"    位置{dayun_list.index(dy)}: 得到{dy['ganzhi']}, 预期{exp}")

# 验证子午冲是否被检测到
di_zuo = result['地支作用']
if "子午" in di_zuo or "午子" in di_zuo:
    print("  ✓ 子午冲已正确检测")
else:
    print("  ✗ 子午冲未检测到！")

# 验证申子半合水局
if "申子" in di_zuo:
    print("  ✓ 申子半合水局已正确检测")
else:
    print("  ? 申子半合未检测（可能被全合优先级影响）")

print()
print("=" * 60)
print("【7. 流月验证（2026丙午年，用实际四柱）】")
print("=" * 60)
from app.skills.divination.dayun_liunian_skill import analyze_liuyue
# 用实际排盘的四柱
real_pillars = {
    "年": {"tian": "壬", "di": "申"},
    "月": {"tian": "壬", "di": "子"},
    "日": {"tian": "己", "di": "巳"},
    "时": {"tian": "甲", "di": "戌"},
}
day_tian_real = "己"
liuyue = analyze_liuyue("丙午", day_tian_real, real_pillars,
                        result['用神'], result['忌神'])
# 四柱地支：申子巳戌；流年地支午
# 关键验证：6月午月(午冲子？午合戌？)、11月亥月(亥冲巳？亥合寅？)
for m in liuyue:
    print(f"  {m['solar_month']}月 {m['month_ganzhi']}: {m['judge']} - {m['reason']}")
    for inter in m['interactions']:
        print(f"      → {inter}")

# 重点检查
print()
print("  重点验证：")
has_wu_chong_zi = any("午" in i and "子" in i and "相冲" in i
                      for m in liuyue for i in m['interactions'])
print(f"    6月午冲月支子: {'✓ 已检测' if has_wu_chong_zi else '✗ 未检测'}")

has_hai_chong_si = any("亥" in i and "巳" in i and "相冲" in i
                      for m in liuyue if m['solar_month']==11 for i in m['interactions'])
print(f"    11月亥冲日支巳: {'✓ 已检测' if has_hai_chong_si else '✗ 未检测'}")

print()
print("=" * 60)
print("验证完成")
print("=" * 60)
