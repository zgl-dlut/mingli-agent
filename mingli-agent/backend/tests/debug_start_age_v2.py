#!/usr/bin/env python3
"""调试起运年龄计算 - 详细版"""
import sys
from pathlib import Path
from datetime import datetime

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.bazi_service import (
    solar_term_time, _find_nearest_jieqi, _calculate_start_age,
    calculate_true_solar_time
)

# 出生信息
birth_date = "1990-11-10"
birth_time = "08:00"
longitude = 112.7

birth_datetime = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
true_time = calculate_true_solar_time(birth_datetime, longitude)

print(f"出生时间: {birth_datetime}")
print(f"真太阳时: {true_time}")
print(f"标准数据集起运年龄: 0.8")
print(f"标准数据集起运日期: 1991年08月20日")
print()

# 检查1990年和1991年的所有节气
print("=== 1990年11月-12月 节气 ===")
for idx in range(24):
    t = solar_term_time(1990, idx)
    if t.month >= 11:
        print(f"  索引{idx:2d}: {t}")

print("\n=== 1991年1月-9月 节气 ===")
for idx in range(24):
    t = solar_term_time(1991, idx)
    if t.month <= 9:
        print(f"  索引{idx:2d}: {t}")

print()

# 检查"节"的索引
JIE_INDICES = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
JIE_NAMES = ["小寒", "立春", "惊蛰", "清明", "立夏", "芒种", 
             "小暑", "立秋", "白露", "寒露", "立冬", "大雪"]

print("=== 1990年11月-1991年9月 的12节 ===")
for y in [1990, 1991]:
    for i, idx in enumerate(JIE_INDICES):
        t = solar_term_time(y, idx)
        if (y == 1990 and t.month >= 11) or (y == 1991 and t.month <= 9):
            print(f"  {y}年{JIE_NAMES[i]}(索引{idx:2d}): {t}")

print()

# 检查顺排找到的下一个节
next_jie = _find_nearest_jieqi(true_time, forward=True)
print(f"顺排找到的下一个节: {next_jie}")
days_diff = abs((next_jie - true_time).days)
print(f"天数差: {days_diff}")
print(f"起运年龄: {days_diff / 3.0:.1f} 年")
print(f"代码计算的起运年龄: {_calculate_start_age(true_time, forward=True)}")

print()
print("=== 验证标准数据集的起运日期 ===")
# 标准数据集说起运日期是1991-08-20
# 从1990-11-10到1991-08-20的天数
start_date = datetime(1990, 11, 10)
target_date = datetime(1991, 8, 20)
days_to_target = (target_date - start_date).days
print(f"从1990-11-10到1991-08-20的天数: {days_to_target}")
print(f"如果起运年龄是0.8年，天数应该是: {0.8 * 365:.0f}")
print(f"如果天数/3=0.8，天数应该是: {0.8 * 3:.1f}")
