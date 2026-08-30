#!/usr/bin/env python3
"""调试起运年龄和流年判断问题"""
import sys
from pathlib import Path
from datetime import datetime

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.bazi_service import (
    calculate_bazi,
    _find_nearest_jieqi,
    _calculate_start_age,
    TIANGAN_YANG,
)
from app.skills.divination.dayun_liunian_skill import (
    analyze_liunian,
    _analyze_interactions,
    _compute_overall_judge,
    TIANGAN_WUXING,
    DIZHI_WUXING,
)
from app.skills.orchestrator import generate_full_analysis

# ========== 调试起运年龄 ==========
print("=" * 60)
print("【调试1: 起运年龄计算】")
print("=" * 60)

birth_date = "1990-11-10"
birth_time = "08:00"
longitude = 112.7
gender = "女"

birth_datetime = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
print(f"出生时间: {birth_datetime}")

# 先计算八字获取日主
bazi = calculate_bazi(birth_date, birth_time, longitude, gender)
day_tian = bazi.pillars["日"]["tian"]
print(f"日主天干: {day_tian}")
print(f"日主阴阳: {'阳' if day_tian in TIANGAN_YANG else '阴'}")
print(f"性别: {gender}")

# 大运方向判断
yang = day_tian in TIANGAN_YANG
forward = (gender == "男" and yang) or (gender == "女" and not yang)
print(f"大运方向: {'顺' if forward else '逆'}")
print(f"  - 阳男阴女顺排: (男 and 阳) or (女 and 阴) = {forward}")

# 找最近的节气
jieqi_forward = _find_nearest_jieqi(birth_datetime, True)
jieqi_backward = _find_nearest_jieqi(birth_datetime, False)
print(f"\n找最近的节气:")
print(f"  - 顺排（找之后的第一个节）: {jieqi_forward}")
print(f"  - 逆排（找之前的第一个节）: {jieqi_backward}")

# 实际用哪个
jieqi_used = jieqi_forward if forward else jieqi_backward
days_diff = abs((jieqi_used - birth_datetime).days)
seconds_diff = abs((jieqi_used - birth_datetime).total_seconds())
print(f"\n实际使用节气: {jieqi_used}")
print(f"天数差: {days_diff} 天")
print(f"秒数差: {seconds_diff} 秒 = {seconds_diff/86400:.4f} 天")
print(f"起运年龄（三天一年法）: {days_diff / 3.0:.1f} 年")
print(f"起运年龄（精确天计算）: {seconds_diff/86400/3.0:.1f} 年")

# 标准数据集期望的起运年龄是0.8年
# 那意味着天数差应该是 0.8 * 3 = 2.4 天
print(f"\n【对照标准数据集】")
print(f"期望起运年龄: 0.8 年")
print(f"反推天数差: 0.8 * 3 = 2.4 天")
print(f"当前算法天数差: {days_diff} 天 -> {days_diff/3:.1f} 年")

# 标准说的起运日期是 1991年08月20日
# 让我们看看从出生到这个日期有多少天
expected_start_date = datetime(1991, 8, 20)
print(f"\n标准起运日期: 1991年08月20日")
actual_days_to_start = (expected_start_date - birth_datetime).days
print(f"从出生到标准起运日期: {actual_days_to_start} 天 = {actual_days_to_start/365:.2f} 年")
print(f"按三天一年: {actual_days_to_start/3:.1f} 年")

# ========== 调试流年判断 ==========
print("\n" + "=" * 60)
print("【调试2: 流年判断问题】")
print("=" * 60)

# 获取调候用神
result = generate_full_analysis(
    birth_date=birth_date,
    birth_time=birth_time,
    longitude=longitude,
    latitude=37.7,
    gender=gender,
    location="山西省晋中市",
)

yongshen = result.get("用神", "")
jishen = result.get("忌神", "")
print(f"用神: {yongshen}")
print(f"忌神: {jishen}")

# 当前大运
current_dayun = None
for d in bazi.dayun:
    if d.is_current:
        current_dayun = d.ganzhi
        break
print(f"当前大运: {current_dayun}")

pillars = bazi.pillars
print(f"四柱地支: {[pillars[k]['di'] for k in ['年','月','日','时']]}")

# 分析几个有问题的流年
problem_years = [2021, 2022, 2023, 2027, 2028, 2029, 2030]

for year in problem_years:
    print(f"\n--- {year}年 ---")
    from app.skills.divination.dayun_liunian_skill import _year_to_ganzhi, _find_dayun_for_year
    
    ganzhi = _year_to_ganzhi(year)
    dayun_list = []
    for d in bazi.dayun:
        dayun_list.append({
            "ganzhi": d.ganzhi,
            "start_year": d.start_year,
            "end_year": d.end_year,
            "is_current": d.is_current,
        })
    dayun = _find_dayun_for_year(dayun_list, year)
    dayun_ganzhi = dayun.get("ganzhi", "")
    
    tian = ganzhi[0]
    di = ganzhi[1]
    tian_wx = TIANGAN_WUXING[tian]
    di_wx = DIZHI_WUXING[di]
    
    print(f"流年干支: {ganzhi} (天干={tian_wx}, 地支={di_wx})")
    print(f"所处大运: {dayun_ganzhi}")
    
    # 详细分析
    analysis = analyze_liunian(ganzhi, dayun_ganzhi, day_tian, pillars, yongshen, jishen)
    
    print(f"用神判定: 天干={'吉' if tian_wx==yongshen else ('凶' if tian_wx==jishen else '平')}, "
          f"地支={'吉' if di_wx==yongshen else ('凶' if di_wx==jishen else '平')}")
    
    print("相互作用:")
    for inter in analysis["interactions"]:
        print(f"  - {inter}")
    
    print(f"综合判断: {analysis['overall_judge']}")
    
    # 手动计算分数
    from app.skills.divination.dayun_liunian_skill import _wuxing_judge
    scores = [_wuxing_judge(tian_wx, yongshen, jishen), _wuxing_judge(di_wx, yongshen, jishen)]
    ji_count = scores.count("吉")
    xiong_count = scores.count("凶")
    print(f"基础分数: 吉={ji_count}, 凶={xiong_count}, scores={scores}")
    
    has_chong = False
    has_zi_xing = False
    has_he_ji = False
    for inter in analysis["interactions"]:
        if "自刑" in inter:
            has_zi_xing = True
        if "冲用神" in inter:
            has_chong = True
            xiong_count += 2
            print(f"  [扣分] 冲用神: xiong+2 -> {xiong_count}")
        elif "冲忌神" in inter:
            ji_count += 1
            print(f"  [加分] 冲忌神: ji+1 -> {ji_count}")
        elif "相冲，主变动" in inter:
            has_chong = True
            xiong_count += 1
            print(f"  [扣分] 中性冲: xiong+1 -> {xiong_count}")
        elif "三会" in inter and "克身" in inter:
            has_he_ji = True
            xiong_count += 3
            print(f"  [扣分] 三会化忌克身: xiong+3 -> {xiong_count}")
        elif "三会" in inter and "生身" in inter:
            ji_count += 3
            print(f"  [加分] 三会化用生身: ji+3 -> {ji_count}")
        elif "三合" in inter and "克身" in inter:
            has_he_ji = True
            xiong_count += 2
            print(f"  [扣分] 三合化忌克身: xiong+2 -> {xiong_count}")
        elif "三合" in inter and "生身" in inter:
            ji_count += 2
            print(f"  [加分] 三合化用生身: ji+2 -> {ji_count}")
        elif "半合" in inter and "克身" in inter:
            xiong_count += 1
            print(f"  [扣分] 半合化忌克身: xiong+1 -> {xiong_count}")
        elif "半合" in inter and "生身" in inter:
            ji_count += 1
            print(f"  [加分] 半合化用生身: ji+1 -> {ji_count}")
        elif "合化" in inter and "忌神" in inter:
            xiong_count += 1
            print(f"  [扣分] 天干合化忌神: xiong+1 -> {xiong_count}")
        elif "合化" in inter and "用神" in inter:
            ji_count += 1
            print(f"  [加分] 天干合化用神: ji+1 -> {ji_count}")
        elif "六合绊用神" in inter:
            xiong_count += 1
            print(f"  [扣分] 六合绊用神: xiong+1 -> {xiong_count}")
        elif "六合绊忌神" in inter:
            ji_count += 1
            print(f"  [加分] 六合绊忌神: ji+1 -> {ji_count}")
    
    print(f"最终分数: 吉={ji_count}, 凶={xiong_count}, has_chong={has_chong}, has_zi_xing={has_zi_xing}, has_he_ji={has_he_ji}")
