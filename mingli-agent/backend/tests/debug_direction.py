#!/usr/bin/env python3
"""调试大运方向问题"""
import sys
from pathlib import Path
from datetime import datetime

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.bazi_service import (
    TIANGAN_YANG, TIANGAN, DIZHI,
    _find_nearest_jieqi, _calculate_start_age,
    calculate_year_pillar, calculate_month_pillar,
    calculate_day_pillar, calculate_hour_pillar,
    calculate_true_solar_time,
)

# 出生信息
birth_date = "1990-11-10"
birth_time = "08:00"
longitude = 112.7
gender = "女"

birth_datetime = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
true_time = calculate_true_solar_time(birth_datetime, longitude)

print(f"出生时间: {birth_datetime}")
print(f"真太阳时: {true_time}")

# 计算四柱
year_tian, year_di = calculate_year_pillar(true_time)
month_tian, month_di = calculate_month_pillar(true_time, year_tian)
day_tian, day_di = calculate_day_pillar(true_time)
hour_tian, hour_di = calculate_hour_pillar(day_tian, true_time.hour)

print(f"\n四柱: {year_tian}{year_di} {month_tian}{month_di} {day_tian}{day_di} {hour_tian}{hour_di}")
print(f"日主天干: {day_tian}")
print(f"月柱天干: {month_tian}")

# 当前代码的方向计算
yang = day_tian in TIANGAN_YANG
print(f"\n日主是否阳干: {yang}")
print(f"性别: {gender}")

# 当前代码逻辑
current_forward = (gender == "男" and yang) or (gender == "女" and not yang)
print(f"当前代码 forward = {current_forward}")
print(f"当前代码 direction = {'顺' if current_forward else '逆'}")

# 标准答案的方向
print(f"\n标准答案 direction = 顺")

# 验证：如果方向是逆，大运列表应该是什么？
print(f"\n=== 验证大运序列 ===")
print(f"月柱: {month_tian}{month_di}")

tian_idx = TIANGAN.index(month_tian)
di_idx = DIZHI.index(month_di)

print(f"\n如果方向是逆（forward=False）:")
for i in range(5):
    tian = TIANGAN[(tian_idx - i) % 10]
    di = DIZHI[(di_idx - i) % 12]
    print(f"  第{i+1}步大运: {tian}{di}")

print(f"\n如果方向是顺（forward=True）:")
for i in range(5):
    tian = TIANGAN[(tian_idx + i) % 10]
    di = DIZHI[(di_idx + i) % 12]
    print(f"  第{i+1}步大运: {tian}{di}")

# 标准答案的大运列表
print(f"\n标准答案大运列表:")
print(f"  第1步: 丙戌")
print(f"  第2步: 乙酉")
print(f"  第3步: 甲申")
print(f"  第4步: 癸未")
print(f"  第5步: 壬午")

# 验证起运年龄
print(f"\n=== 验证起运年龄 ===")
# 如果方向是逆，应该找上一个节
prev_jie = _find_nearest_jieqi(true_time, forward=False)
print(f"上一个节（逆排）: {prev_jie}")
days_diff_prev = abs((prev_jie - true_time).days)
print(f"天数差: {days_diff_prev}")
print(f"起运年龄: {days_diff_prev / 3.0:.1f} 年")

# 如果方向是顺，应该找下一个节
next_jie = _find_nearest_jieqi(true_time, forward=True)
print(f"\n下一个节（顺排）: {next_jie}")
days_diff_next = abs((next_jie - true_time).days)
print(f"天数差: {days_diff_next}")
print(f"起运年龄: {days_diff_next / 3.0:.1f} 年")

print(f"\n标准答案起运年龄: 0.8 年")
