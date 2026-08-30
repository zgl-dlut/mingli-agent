#!/usr/bin/env python3
"""调试排盘系统输出结构"""
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
    gender="女"
)

# 输出关键字段
print("=" * 60)
print("排盘系统输出结构")
print("=" * 60)

print("\n【四柱】")
print(f"  值: {result.get('四柱')}")

print("\n【大运方向】")
print(f"  值: {result.get('大运方向')}")
print(f"  类型: {type(result.get('大运方向'))}")

print("\n【起运年龄】")
print(f"  值: {result.get('起运年龄')}")
print(f"  类型: {type(result.get('起运年龄'))}")

print("\n【大运列表】")
dayun_list = result.get('大运列表', [])
print(f"  数量: {len(dayun_list)}")
if dayun_list:
    print(f"  前3个大运:")
    for i, dy in enumerate(dayun_list[:3]):
        print(f"    [{i}] {json.dumps(dy, ensure_ascii=False, indent=6)}")

print("\n【重点流年】")
liunian_list = result.get('重点流年', [])
print(f"  数量: {len(liunian_list)}")
if liunian_list:
    print(f"  前5个流年:")
    for i, ln in enumerate(liunian_list[:5]):
        print(f"    [{i}] {json.dumps(ln, ensure_ascii=False, indent=6)}")

print("\n【完整输出JSON】")
print(json.dumps(result, ensure_ascii=False, indent=2))
