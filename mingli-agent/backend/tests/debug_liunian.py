#!/usr/bin/env python3
"""
调试流年判断问题
对比标准数据集和排盘系统实际输出
"""
import sys
import json
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.skills.orchestrator import generate_full_analysis

# 生成命盘数据
result = generate_full_analysis(
    birth_date="1990-11-10",
    birth_time="08:00",
    longitude=112.75,
    latitude=37.65,
    gender="女",
    location="山西省晋中市"
)

print("=" * 60)
print("排盘系统实际输出的流年数据")
print("=" * 60)

# 输出2027-2030年的流年数据
liunian_list = result.get('重点流年', [])
for ln in liunian_list:
    year = ln.get('year')
    if year and 2027 <= year <= 2030:
        print(f"\n{year}年 {ln.get('ganzhi')}:")
        print(f"  天干五行: {ln.get('tian_wuxing')}")
        print(f"  地支五行: {ln.get('di_wuxing')}")
        print(f"  是否用神: {ln.get('is_yongshen')}")
        print(f"  是否忌神: {ln.get('is_jishen')}")
        print(f"  综合判断: {ln.get('overall_judge')}")
        print(f"  判断理由: {ln.get('reason')}")
        print(f"  详细描述: {ln.get('description', '')[:100]}...")

print("\n" + "=" * 60)
print("标准数据集中的流年数据")
print("=" * 60)

# 读取标准数据集
dataset_path = backend_dir / "tests" / "eval_chart_dataset.json"
with open(dataset_path, 'r', encoding='utf-8') as f:
    dataset = json.load(f)

expected_liunian = dataset[0]['expected']['流年']
for year in ['2027', '2028', '2029', '2030']:
    ln = expected_liunian[year]
    print(f"\n{year}年 {ln.get('干支')}:")
    print(f"  天干五行: {ln.get('天干五行')}")
    print(f"  地支五行: {ln.get('地支五行')}")
    print(f"  用神标记: {ln.get('用神标记')}")
    print(f"  流年判断: {ln.get('流年判断')}")
    print(f"  判断理由: {ln.get('判断理由')}")
