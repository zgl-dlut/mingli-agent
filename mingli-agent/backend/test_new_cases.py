"""测试新增用例的实际排盘结果"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.skills.orchestrator import generate_full_analysis

# 用例1: 1995-06-15 08:30 女 上海
result1 = generate_full_analysis(
    birth_date="1995-06-15",
    birth_time="08:30",
    longitude=121.47,
    latitude=31.23,
    gender="女",
    location="上海市"
)

print("=" * 80)
print("用例1: 1995-06-15 08:30 女 上海")
print("=" * 80)
print(f"四柱: {result1.get('四柱', '')}")
print(f"日主: {result1.get('日主', '')}")
print(f"旺衰结论: {result1.get('旺衰结论', '')}")
print(f"用神: {result1.get('用神', '')}")
print(f"忌神: {result1.get('忌神', '')}")

# 用例2: 2000-02-04 12:00 男 北京
result2 = generate_full_analysis(
    birth_date="2000-02-04",
    birth_time="12:00",
    longitude=116.40,
    latitude=39.90,
    gender="男",
    location="北京市"
)

print("\n" + "=" * 80)
print("用例2: 2000-02-04 12:00 男 北京")
print("=" * 80)
print(f"四柱: {result2.get('四柱', '')}")
print(f"日主: {result2.get('日主', '')}")
print(f"旺衰结论: {result2.get('旺衰结论', '')}")
print(f"用神: {result2.get('用神', '')}")
print(f"忌神: {result2.get('忌神', '')}")
