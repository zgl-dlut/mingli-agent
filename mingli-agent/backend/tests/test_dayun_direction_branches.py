#!/usr/bin/env python3
"""
大运方向四分支覆盖测试

覆盖四种大运方向规则：
1. 阳年男命 → 顺排  (甲子年男)
2. 阴年女命 → 顺排  (乙丑年女)
3. 阴年男命 → 逆排  (乙丑年男)
4. 阳年女命 → 逆排  (庚午年女，已有chart_001)

极端案例：
- 紧贴节气出生（起运年龄极小）
- 远离节气出生（起运年龄较大）
- 节气当天出生
"""
import sys
import json
from pathlib import Path
from datetime import datetime

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.bazi_service import (
    calculate_dayun,
    PRECALCULATED_JIEQI,
    TIANGAN, DIZHI, TIANGAN_WUXING,
)

# ============================================================
# 辅助函数
# ============================================================
def get_month_pillar(year, month, day):
    """根据出生日期获取月柱（简化版，用于测试）"""
    # 已知：1984甲子年立春后=丙寅月
    # 月干公式：年干*2+月数 对应天干索引
    year_tg_idx = (year - 4) % 10
    # 月柱天干 = (年干索引 * 2 + 月份) % 10（从寅月起）
    # 简化：直接根据年干推算正月天干
    year_tg = TIANGAN[year_tg_idx]
    # 年干起月表：甲己年起丙寅，乙庚年起戊寅，丙辛年起庚寅，丁壬年起壬寅，戊癸年起甲寅
    base_map = {"甲": 2, "己": 2, "乙": 4, "庚": 4, "丙": 6, "辛": 6, "丁": 8, "壬": 8, "戊": 0, "癸": 0}
    month_tg_idx = (base_map[year_tg] + (month - 1)) % 10
    month_di_idx = (month + 1) % 12  # 正月=寅(2)
    return TIANGAN[month_tg_idx], DIZHI[month_di_idx]


def get_year_tg(year):
    return TIANGAN[(year - 4) % 10]


def is_yang(year):
    return (year - 4) % 2 == 0


# ============================================================
# 测试用例定义
# ============================================================
test_cases = [
    {
        "id": "branch_01",
        "description": "阳年男命-顺排-甲子年(1984)-立春后",
        "year": 1984, "month": 2, "day": 10, "hour": 8, "minute": 0,
        "gender": "male",
        "expected_direction": "顺",
        "expected_rule": "阳年男命→顺排",
        "year_tg": "甲",  # 阳干
        "edge_case": "立春后3天，起运年龄应较小",
    },
    {
        "id": "branch_02",
        "description": "阴年女命-顺排-乙丑年(1985)-清明后",
        "year": 1985, "month": 4, "day": 10, "hour": 12, "minute": 0,
        "gender": "female",
        "expected_direction": "顺",
        "expected_rule": "阴年女命→顺排",
        "year_tg": "乙",  # 阴干
        "edge_case": "清明后5天",
    },
    {
        "id": "branch_03",
        "description": "阴年男命-逆排-乙丑年(1985)-芒种后",
        "year": 1985, "month": 6, "day": 10, "hour": 6, "minute": 0,
        "gender": "male",
        "expected_direction": "逆",
        "expected_rule": "阴年男命→逆排",
        "year_tg": "乙",  # 阴干
        "edge_case": "芒种后4天",
    },
    {
        "id": "branch_04",
        "description": "阳年女命-逆排-庚午年(1990)-立冬后(已有chart_001)",
        "year": 1990, "month": 11, "day": 10, "hour": 8, "minute": 0,
        "gender": "female",
        "expected_direction": "逆",
        "expected_rule": "阳年女命→逆排",
        "year_tg": "庚",  # 阳干
        "edge_case": "立冬后约0.8年（标准数据集验证）",
    },
    {
        "id": "branch_05",
        "description": "极端-紧贴节气-壬申年(1992)男-清明前1天",
        "year": 1992, "month": 4, "day": 3, "hour": 20, "minute": 0,
        "gender": "male",
        "expected_direction": "顺",
        "expected_rule": "阳年男命→顺排",
        "year_tg": "壬",  # 阳干
        "edge_case": "清明(4月4日20:19)前1天，顺排距下一节仅约1天，起运年龄应极小",
    },
    {
        "id": "branch_06",
        "description": "极端-远离节气-癸酉年(1993)女-大雪后20天",
        "year": 1993, "month": 12, "day": 27, "hour": 10, "minute": 0,
        "gender": "female",
        "expected_direction": "顺",
        "expected_rule": "阴年女命→顺排",
        "year_tg": "癸",  # 阴干
        "edge_case": "远离节气，起运年龄应较大",
    },
]


# ============================================================
# 运行测试
# ============================================================
print("=" * 70)
print("大运方向四分支覆盖测试")
print("=" * 70)

results = []
for tc in test_cases:
    print(f"\n{'─' * 60}")
    print(f"【{tc['id']}】{tc['description']}")
    print(f"规则: {tc['expected_rule']}")
    print(f"边界: {tc['edge_case']}")

    birth_dt = datetime(tc["year"], tc["month"], tc["day"], tc["hour"], tc["minute"])
    year_tg = get_year_tg(tc["year"])
    yang = is_yang(tc["year"])

    # 获取月柱
    month_tg, month_di = get_month_pillar(tc["year"], tc["month"], tc["day"])

    # 日干简化计算（测试用，仅验证方向）
    # 使用已知日干或默认
    day_tg = "甲"  # 方向判断只依赖年干+性别，与日干无关

    print(f"出生: {birth_dt}, 年干={year_tg}({'阳' if yang else '阴'}), 性别={tc['gender']}")
    print(f"月柱: {month_tg}{month_di}")

    try:
        dayun_list, direction, start_age = calculate_dayun(
            birth_dt, day_tg, tc["gender"], month_tg, month_di, year_tg
        )

        dir_ok = direction == tc["expected_direction"]
        age_ok = start_age > 0 and start_age < 10  # 合理范围

        # 验证大运序列方向
        month_tg_idx = TIANGAN.index(month_tg)
        month_di_idx = DIZHI.index(month_di)
        first_dayun = dayun_list[0]["ganzhi"] if dayun_list else ""

        if tc["expected_direction"] == "顺":
            expected_first_tg = TIANGAN[(month_tg_idx + 1) % 10]
            expected_first_di = DIZHI[(month_di_idx + 1) % 12]
        else:
            expected_first_tg = TIANGAN[(month_tg_idx - 1) % 10]
            expected_first_di = DIZHI[(month_di_idx - 1) % 12]
        expected_first = expected_first_tg + expected_first_di

        seq_ok = first_dayun == expected_first

        print(f"方向: {direction} {'✓' if dir_ok else '✗ 期望=' + tc['expected_direction']}")
        print(f"起运年龄: {start_age}年 {'✓' if age_ok else '✗ 超出合理范围'}")
        print(f"首步大运: {first_dayun} (期望={expected_first}) {'✓' if seq_ok else '✗'}")
        print(f"大运序列: {[d['ganzhi'] for d in dayun_list[:5]]}")

        results.append({
            "id": tc["id"],
            "direction_ok": dir_ok,
            "age_ok": age_ok,
            "seq_ok": seq_ok,
            "direction": direction,
            "start_age": start_age,
        })

    except Exception as e:
        print(f"✗ 计算异常: {e}")
        results.append({
            "id": tc["id"],
            "direction_ok": False,
            "age_ok": False,
            "seq_ok": False,
            "error": str(e),
        })


# ============================================================
# 汇总
# ============================================================
print(f"\n{'=' * 70}")
print("测试汇总")
print(f"{'=' * 70}")

all_pass = True
for r in results:
    status = "✓ PASS" if (r["direction_ok"] and r["age_ok"] and r["seq_ok"]) else "✗ FAIL"
    if status == "✗ FAIL":
        all_pass = False
    print(f"  {status} {r['id']}: 方向={r.get('direction', 'N/A')}, 起运={r.get('start_age', 'N/A')}")

# 四分支覆盖检查
covered = set()
for tc in test_cases:
    key = (tc["expected_direction"], tc["expected_rule"])
    covered.add(key)

print(f"\n分支覆盖:")
print(f"  {'✓' if any('阳年男命' in r for r in [tc['expected_rule'] for tc in test_cases]) else '✗'} 阳年男命→顺排")
print(f"  {'✓' if any('阴年女命' in r for r in [tc['expected_rule'] for tc in test_cases]) else '✗'} 阴年女命→顺排")
print(f"  {'✓' if any('阴年男命' in r for r in [tc['expected_rule'] for tc in test_cases]) else '✗'} 阴年男命→逆排")
print(f"  {'✓' if any('阳年女命' in r for r in [tc['expected_rule'] for tc in test_cases]) else '✗'} 阳年女命→逆排")

print(f"\n★ 总体结果: {'全部通过！' if all_pass else '有失败项，请检查'}")
print(f"{'=' * 70}")
