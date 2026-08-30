#!/usr/bin/env python3
"""深入调试流年判断的核心逻辑"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.skills.divination.dayun_liunian_skill import (
    _wuxing_judge,
    WUXING_SHENG,
    WUXING_KE,
    _he_hua_relation,
)

print("=" * 60)
print("【调试 _wuxing_judge 基础五行判断】")
print("=" * 60)

yongshen = "火"
jishen = "水"

print(f"用神: {yongshen}, 忌神: {jishen}")
print(f"\n五行生: {WUXING_SHENG}")
print(f"五行克: {WUXING_KE}")

# 生用神=喜神：谁生用神火？木生火 → 木是喜神
# 生忌神=仇神：谁生忌神水？金生水 → 金是仇神
for wx in ["金", "木", "水", "火", "土"]:
    result = _wuxing_judge(wx, yongshen, jishen)
    print(f"  {wx}: {result}")
    sheng_of = WUXING_SHENG.get(wx)
    ke_of = WUXING_KE.get(wx)
    print(f"    {wx}生: {sheng_of}, {wx}克: {ke_of}")
    if sheng_of == yongshen:
        print(f"    → {wx}生用神{yongshen}，应为吉")
    if sheng_of == jishen:
        print(f"    → {wx}生忌神{jishen}，应为凶")
    if wx == yongshen:
        print(f"    → {wx}是用神，应为吉")
    if wx == jishen:
        print(f"    → {wx}是忌神，应为凶")

# 测试金（2021天干是辛金）
print("\n【特别验证：辛金（2021年天干）】")
print(f"金生水: WUXING_SHENG['金'] = {WUXING_SHENG.get('金')}")
print(f"所以金生忌神水吗？ {WUXING_SHENG.get('金') == jishen}")
print(f"_wuxing_judge('金', '火', '水') = {_wuxing_judge('金', '火', '水')}")

# 测试土（2021地支是丑土）
print("\n【特别验证：丑土（2021年地支）】")
print(f"土克水: WUXING_KE['土'] = {WUXING_KE.get('土')}")
print(f"土生金: WUXING_SHENG['土'] = {WUXING_SHENG.get('土')}")
print(f"所以土生用神火吗？ 不，土生金")
print(f"所以土生忌神水吗？ 不，土克水")
print(f"_wuxing_judge('土', '火', '水') = {_wuxing_judge('土', '火', '水')}")

# ========== 调试合化五行 ==========
print("\n" + "=" * 60)
print("【调试 _he_hua_relation 合化关系判断】")
print("=" * 60)

day_tian = "己"
day_wx = "土"

print(f"日主天干: {day_tian}, 五行: {day_wx}")
print(f"克日主(土)的是: 木克土 → {WUXING_KE.get('木') == '土'}")
print(f"生日主(土)的是: 火生土 → {WUXING_SHENG.get('火') == '土'}")

# 测试三会木局（2022年问题）
he_wx = "木"
result = _he_hua_relation(he_wx, day_tian, yongshen, jishen)
print(f"\n合化木局:")
print(f"  合化五行={he_wx}, 是忌神吗？ {he_wx == jishen} (忌神是{jishen})")
print(f"  {he_wx}克日主{day_wx}吗？ WUXING_KE['{he_wx}']={WUXING_KE.get(he_wx)} == {day_wx}? {WUXING_KE.get(he_wx) == day_wx}")
print(f"  {he_wx}生日主{day_wx}吗？ WUXING_SHENG['{he_wx}']={WUXING_SHENG.get(he_wx)} == {day_wx}? {WUXING_SHENG.get(he_wx) == day_wx}")
print(f"  {he_wx}是用神吗？ {he_wx == yongshen} (用神是{yongshen})")
print(f"  结果: {result} (忌/用/平)")

# 测试三合木局（2027年问题）
he_wx = "木"
result = _he_hua_relation(he_wx, day_tian, yongshen, jishen)
print(f"\n三合木局:")
print(f"  合化五行={he_wx}")
print(f"  结果: {result}")

# 问题分析：
# 己土日主，木克土是对的
# 但是！三合/三会化木局虽然理论上是木克土，但：
# 1. 如果命局本身就有木的元素，合化木局是否真的这么强？
# 2. 流年2027丁未，天干丁火是用神（火生土帮身），怎么会是大凶？
# 3. 卯未半合木局：亥卯未三合木，但原局有亥+卯，流年再来未才是完整三合
#    - 但这个三合局真的能"克身"吗？原局有午火可以化木生火

print("\n" + "=" * 60)
print("【核心问题分析】")
print("=" * 60)
print("""
发现的问题：
1. 起运年龄：标准是0.8年≈2.4天，但当前算到25天=8.3年
   → 可能是节气表缺少1990年的数据，导致找到的节气不准

2. _wuxing_judge把金和土都判为"凶"，因为金生忌神水
   → 这太严格了！金生忌神水只是间接作用，不应该直接判凶
   → 标准数据集里2021辛丑(金土)是"吉"，2028戊申(土金)是"平"

3. 三会/三合木局直接判"克身"扣分太多
   → 三会木局(亥卯辰？不对，寅卯辰才是三会木)
   → 2022壬寅年，原局有亥、卯、辰，流年再来寅→寅卯辰三会木
   → 但木虽然克土，命局有午火可以通关(木生火、火生土)
   → 不应该直接扣xiong+3这么重！

4. 六合绊用神扣分太重
   → 2027年未土和午火六合绊用神(午火是火=用神)
   → 合绊只是减力，不是凶，不应该直接扣xiong+1

5. 中性"相冲，主变动"扣分太重
   → 2028年申寅相冲，直接扣xiong+1然后就大凶了
   → 相冲主变动，但变动不一定是坏事，不能直接当凶算！
""")
