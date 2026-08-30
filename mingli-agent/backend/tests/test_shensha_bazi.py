"""
神煞 & 天干五合 & 排盘完整性测试

直接测试神煞/天干五合/空亡/长生十二宫函数，不依赖 sxwnl 模块。
对比测测App排盘数据，验证系统排盘结果的准确性。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.skills.divination.shensha_skill import calculate_shensha, calculate_tiangan_he
from app.services.bazi_service import calculate_kongwang, calculate_changsheng


def test_case_1():
    """13019223923 用户：甲戌 甲戌 壬申 己酉"""
    print("=" * 60)
    print("测试用例1：13019223923 用户")
    print("四柱：甲戌 甲戌 壬申 己酉")
    print("=" * 60)

    pillars = {
        "年": {"tian": "甲", "di": "戌"},
        "月": {"tian": "甲", "di": "戌"},
        "日": {"tian": "壬", "di": "申"},
        "时": {"tian": "己", "di": "酉"},
    }
    day_tian = "壬"
    day_di = "申"
    month_di = "戌"
    year_di = "戌"
    year_tian = "甲"
    year_nayin = "山头火"

    passed = 0
    total = 0

    # 1. 空亡验证
    print("\n【空亡验证】")
    expected_kongwang = ["戌", "亥"]
    actual_kongwang = calculate_kongwang(day_tian, day_di)
    total += 1
    match = actual_kongwang == expected_kongwang
    status = "✅" if match else ""
    print(f"  {status} 空亡: {actual_kongwang} (期望: {expected_kongwang})")
    if match:
        passed += 1

    # 2. 长生十二宫验证
    print("\n【长生十二宫验证】")
    expected_changsheng = {"年": "冠带", "月": "冠带", "日": "长生", "时": "沐浴"}
    actual_changsheng = calculate_changsheng(day_tian, pillars)
    for pos, expected in expected_changsheng.items():
        total += 1
        actual = actual_changsheng.get(pos, "")
        match = actual == expected
        status = "✅" if match else "❌"
        print(f"  {status} {pos}: {actual} (期望: {expected})")
        if match:
            passed += 1

    # 3. 神煞验证
    print("\n【神煞验证】")
    actual_shensha = calculate_shensha(
        pillars, day_tian, day_di, month_di, year_di, year_tian, year_nayin, actual_kongwang
    )

    expected_shensha = {
        "年": ["华盖", "国印", "太极贵人", "空亡"],
        "月": ["华盖", "国印", "太极贵人", "空亡"],
        "日": ["驿马", "十恶大败", "金舆", "学堂"],
        "时": ["桃花", "天医", "六厄", "童子"],
    }

    for pos in ["年", "月", "日", "时"]:
        total += 1
        actual = actual_shensha.get(pos, [])
        expected = expected_shensha.get(pos, [])
        missing = [s for s in expected if s not in actual]
        extra = [s for s in actual if s not in expected]
        if not missing and not extra:
            status = "✅"
            passed += 1
            print(f"  {status} {pos}: {actual} (完全匹配)")
        else:
            status = "⚠️"
            print(f"  {status} {pos}: {actual}")
            if missing:
                print(f"      缺少: {missing}")
            if extra:
                print(f"      多出: {extra}")

    # 4. 天干五合验证
    print("\n【天干五合验证】")
    actual_tiangan_he = calculate_tiangan_he(pillars)
    total += 1
    has_jiaji = any("甲" in h and "己" in h for h in actual_tiangan_he)
    status = "✅" if has_jiaji else "❌"
    print(f"  {status} 天干五合: {actual_tiangan_he} (期望包含: 甲己合化土)")
    if has_jiaji:
        passed += 1

    print(f"\n用例1 结果: {passed}/{total} 通过")
    return passed, total


def test_case_2():
    """丙午日主：丙寅 庚寅 丙午 癸巳"""
    print("\n" + "=" * 60)
    print("测试用例2：丙午日主")
    print("四柱：丙寅 庚寅 丙午 癸巳")
    print("=" * 60)

    pillars = {
        "年": {"tian": "丙", "di": "寅"},
        "月": {"tian": "庚", "di": "寅"},
        "日": {"tian": "丙", "di": "午"},
        "时": {"tian": "癸", "di": "巳"},
    }
    day_tian = "丙"
    day_di = "午"
    month_di = "寅"
    year_di = "寅"
    year_tian = "丙"
    year_nayin = "炉中火"

    passed = 0
    total = 0

    # 1. 空亡验证
    print("\n【空亡验证】")
    expected_kongwang = ["寅", "卯"]
    actual_kongwang = calculate_kongwang(day_tian, day_di)
    total += 1
    match = actual_kongwang == expected_kongwang
    status = "✅" if match else "❌"
    print(f"  {status} 空亡: {actual_kongwang} (期望: {expected_kongwang})")
    if match:
        passed += 1

    # 2. 长生十二宫验证
    print("\n【长生十二宫验证】")
    expected_changsheng = {"年": "长生", "月": "长生", "日": "帝旺", "时": "临官"}
    actual_changsheng = calculate_changsheng(day_tian, pillars)
    for pos, expected in expected_changsheng.items():
        total += 1
        actual = actual_changsheng.get(pos, "")
        match = actual == expected
        status = "✅" if match else "❌"
        print(f"  {status} {pos}: {actual} (期望: {expected})")
        if match:
            passed += 1

    # 3. 神煞验证
    print("\n【神煞验证】")
    actual_shensha = calculate_shensha(
        pillars, day_tian, day_di, month_di, year_di, year_tian, year_nayin, actual_kongwang
    )
    for pos in ["年", "月", "日", "时"]:
        actual = actual_shensha.get(pos, [])
        print(f"  {pos}: {actual}")

    # 4. 天干五合验证
    print("\n【天干五合验证】")
    actual_tiangan_he = calculate_tiangan_he(pillars)
    total += 1
    has_no_he = len(actual_tiangan_he) == 0
    status = "✅" if has_no_he else "❌"
    print(f"  {status} 天干五合: {actual_tiangan_he} (期望: 无)")
    if has_no_he:
        passed += 1

    print(f"\n用例2 结果: {passed}/{total} 通过")
    return passed, total


def test_case_3():
    """甲子日主：甲子 丙寅 甲子 丁卯"""
    print("\n" + "=" * 60)
    print("测试用例3：甲子日主")
    print("四柱：甲子 丙寅 甲子 丁卯")
    print("=" * 60)

    pillars = {
        "年": {"tian": "甲", "di": "子"},
        "月": {"tian": "丙", "di": "寅"},
        "日": {"tian": "甲", "di": "子"},
        "时": {"tian": "丁", "di": "卯"},
    }
    day_tian = "甲"
    day_di = "子"
    month_di = "寅"
    year_di = "子"
    year_tian = "甲"
    year_nayin = "海中金"

    passed = 0
    total = 0

    # 1. 空亡验证
    print("\n【空亡验证】")
    expected_kongwang = ["戌", "亥"]
    actual_kongwang = calculate_kongwang(day_tian, day_di)
    total += 1
    match = actual_kongwang == expected_kongwang
    status = "✅" if match else ""
    print(f"  {status} 空亡: {actual_kongwang} (期望: {expected_kongwang})")
    if match:
        passed += 1

    # 2. 长生十二宫验证
    print("\n【长生十二宫验证】")
    expected_changsheng = {"年": "沐浴", "月": "临官", "日": "沐浴", "时": "帝旺"}
    actual_changsheng = calculate_changsheng(day_tian, pillars)
    for pos, expected in expected_changsheng.items():
        total += 1
        actual = actual_changsheng.get(pos, "")
        match = actual == expected
        status = "✅" if match else "❌"
        print(f"  {status} {pos}: {actual} (期望: {expected})")
        if match:
            passed += 1

    # 3. 神煞验证
    print("\n【神煞验证】")
    actual_shensha = calculate_shensha(
        pillars, day_tian, day_di, month_di, year_di, year_tian, year_nayin, actual_kongwang
    )
    for pos in ["年", "月", "日", "时"]:
        actual = actual_shensha.get(pos, [])
        print(f"  {pos}: {actual}")

    # 4. 天干五合验证
    print("\n【天干五合验证】")
    actual_tiangan_he = calculate_tiangan_he(pillars)
    total += 1
    has_no_he = len(actual_tiangan_he) == 0
    status = "✅" if has_no_he else "❌"
    print(f"  {status} 天干五合: {actual_tiangan_he} (期望: 无)")
    if has_no_he:
        passed += 1

    print(f"\n用例3 结果: {passed}/{total} 通过")
    return passed, total


if __name__ == "__main__":
    p1, t1 = test_case_1()
    p2, t2 = test_case_2()
    p3, t3 = test_case_3()

    total_passed = p1 + p2 + p3
    total_tests = t1 + t2 + t3
    print("\n" + "=" * 60)
    print(f"总计: {total_passed}/{total_tests} 通过")
    print("=" * 60)
