"""
排盘算法正确性诊断测试（阶段2.1）

目的：确认 project_memory 记录的"已知 bug"是否仍存在。
现有 test_bazi_paipan.py 已覆盖阴干日主乙/丁、立春交接、流月12个月。
本文件补充未覆盖的边界：
1. 阴干日主 己/辛/癸 的十神正偏（财/官/印/食伤/比劫全覆盖）
2. 多个节气交接日（立春/惊蛰/立夏/立秋/大雪）当天月柱地支切换
3. 小寒前后年柱（1月未立春，年柱应属上一年）

诊断结论：若全部通过，说明 project_memory 记录的算法 bug 已不存在/已修复，
阶段2.2 无需改动排盘算法代码。
"""
import sys
import os
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.bazi_service import (
    calculate_shishen, calculate_year_pillar, calculate_month_pillar,
    solar_term_time,
)


# ============================================================
# 1. 阴干日主十神正偏（己土/辛金/癸水，现有测试只覆盖了乙/丁）
# ============================================================

# (日主, 天干, 期望十神) —— 手动按五行生克+阴阳正偏推导
_SHISHEN_CASES = [
    # 己土（阴土）日主
    ("己", "己", "比肩"), ("己", "戊", "劫财"),
    ("己", "丙", "正印"), ("己", "丁", "偏印"),
    ("己", "癸", "偏财"), ("己", "壬", "正财"),
    ("己", "乙", "七杀"), ("己", "甲", "正官"),
    ("己", "辛", "食神"), ("己", "庚", "伤官"),
    # 辛金（阴金）日主
    ("辛", "辛", "比肩"), ("辛", "庚", "劫财"),
    ("辛", "戊", "正印"), ("辛", "己", "偏印"),
    ("辛", "乙", "偏财"), ("辛", "甲", "正财"),
    ("辛", "丁", "七杀"), ("辛", "丙", "正官"),
    ("辛", "癸", "食神"), ("辛", "壬", "伤官"),
    # 癸水（阴水）日主
    ("癸", "癸", "比肩"), ("癸", "壬", "劫财"),
    ("癸", "庚", "正印"), ("癸", "辛", "偏印"),
    ("癸", "丁", "偏财"), ("癸", "丙", "正财"),
    ("癸", "己", "七杀"), ("癸", "戊", "正官"),
    ("癸", "乙", "食神"), ("癸", "甲", "伤官"),
]


@pytest.mark.parametrize("day_tian,tian,expected", _SHISHEN_CASES)
def test_shishen_yin_day_master_full(day_tian, tian, expected):
    """阴干日主（己/辛/癸）十神正偏正确，财/官/印/食伤/比劫全覆盖"""
    result = calculate_shishen(day_tian, tian)
    assert result == expected, f"日主{day_tian}对天干{tian}: 期望{expected}, 实际{result}"


# ============================================================
# 2. 节气交接日当天月柱地支切换
# ============================================================

# (年份, 节气term_index, 节气后应有的月支)
# 节气顺序：小寒=0,立春=2,惊蛰=4,清明=6,立夏=8,芒种=10,小暑=12,立秋=14,白露=16,寒露=18,立冬=20,大雪=22
_JIEQI_BOUNDARY_CASES = [
    (2023, 2, "寅"),   # 立春后=寅月
    (2023, 4, "卯"),   # 惊蛰后=卯月
    (2023, 8, "巳"),   # 立夏后=巳月
    (2023, 14, "申"),  # 立秋后=申月
    (2023, 22, "子"),  # 大雪后=子月
]


@pytest.mark.parametrize("year,term_idx,expected_month_di", _JIEQI_BOUNDARY_CASES)
def test_jieqi_boundary_month_pillar_switch(year, term_idx, expected_month_di):
    """节气交接日：节气时刻后1秒月支应切换为新月，前1秒为上月"""
    jieqi_dt = solar_term_time(year, term_idx)
    year_tian, _ = calculate_year_pillar(jieqi_dt + timedelta(seconds=2))

    # 节气后2秒 → 新月支
    after = calculate_month_pillar(jieqi_dt + timedelta(seconds=2), year_tian)
    assert after[1] == expected_month_di, \
        f"{year}年节气{term_idx}后: 期望月支{expected_month_di}, 实际{after[1]}"

    # 节气前2秒 → 上一个月支（前一个节气对应的月支）
    before = calculate_month_pillar(jieqi_dt - timedelta(seconds=2), year_tian)
    prev_term_di = _prev_month_di(expected_month_di)
    assert before[1] == prev_term_di, \
        f"{year}年节气{term_idx}前: 期望月支{prev_month_di}(上月), 实际{before[1]}"


def _prev_month_di(month_di: str) -> str:
    """月支序列 寅卯辰巳午未申酉戌亥子丑 的前一个"""
    order = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]
    idx = order.index(month_di)
    return order[(idx - 1) % 12]


# ============================================================
# 3. 小寒前后年柱（1月未立春，年柱应属上一年）
# ============================================================

def test_year_pillar_before_lichun_in_january():
    """1月小寒前后（立春前）年柱应属上一年：2023年1月 → 壬寅年（2022）"""
    # 2023年1月15日（立春前），年柱应为壬寅
    dt = datetime(2023, 1, 15, 12, 0, 0)
    tian, di = calculate_year_pillar(dt)
    assert (tian, di) == ("壬", "寅"), f"2023立春前年柱期望壬寅, 实际{tian}{di}"


def test_year_pillar_after_lichun_in_february():
    """2月立春后年柱应属当年：2023年2月10日 → 癸卯年（2023）"""
    dt = datetime(2023, 2, 10, 12, 0, 0)
    tian, di = calculate_year_pillar(dt)
    assert (tian, di) == ("癸", "卯"), f"2023立春后年柱期望癸卯, 实际{tian}{di}"


if __name__ == "__main__":
    # 手动跑参数化测试的代表性用例
    print("阴干日主十神抽检:")
    for day_tian in ("己", "辛", "癸"):
        for tian in ("甲", "丙", "戊", "庚", "壬"):
            r = calculate_shishen(day_tian, tian)
            print(f"  {day_tian}→{tian}: {r}")
    print("\n节气交接抽检:")
    for year, idx, exp in _JIEQI_BOUNDARY_CASES:
        jieqi = solar_term_time(year, idx)
        yt, _ = calculate_year_pillar(jieqi + timedelta(seconds=2))
        after = calculate_month_pillar(jieqi + timedelta(seconds=2), yt)
        print(f"  {year}节气{idx}后月支: {after[1]} (期望{exp})")
    print("\n年柱抽检:")
    for dt, exp in [(datetime(2023,1,15),("壬","寅")), (datetime(2023,2,10),("癸","卯"))]:
        r = calculate_year_pillar(dt)
        print(f"  {dt.date()}: {r[0]}{r[1]} (期望{''.join(exp)})")
