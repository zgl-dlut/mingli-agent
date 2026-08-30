#!/usr/bin/env python3
"""验证起运年龄计算 - 对比标准数据集"""
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

# 计算到各个节气的天数
print("=== 从出生时间到各节气（节）的天数 ===")
jieqi_names = ["小寒", "立春", "惊蛰", "清明", "立夏", "芒种",
              "小暑", "立秋", "白露", "寒露", "立冬", "大雪"]

for y in [1990, 1991]:
    for idx in [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]:  # 12节
        t = solar_term_time(y, idx)
        if t >= true_time:
            days = (t - true_time).days
            start_age = days / 3.0
            name = jieqi_names[idx // 2]
            marker = " <-- 标准数据集的起运日期附近" if abs(t.date().month - 8) <= 1 and t.year == 1991 else ""
            print(f"  到{y}年{name}({t.date()}): {days}天, 起运年龄={start_age:.1f}年{marker}")
            if days > 300:  # 只显示到292天附近
                break

print()
print(f"代码计算的起运年龄: {_calculate_start_age(true_time, forward=True)}")
print(f"代码找到的节气: {_find_nearest_jieqi(true_time, forward=True)}")
