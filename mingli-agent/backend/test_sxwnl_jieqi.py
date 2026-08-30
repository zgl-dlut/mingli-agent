"""测试 sxwnl 库节气计算准确性"""
import sys
sys.path.insert(0, '.')

print("=== 1. 探索 sxwnl API ===")
try:
    from sxwnl import calendar
    from sxwnl.eph0 import fromJD
    print("导入成功")
except ImportError as e:
    print(f"导入失败: {e}")
    # 尝试其他导入方式
    try:
        import sxwnl
        print(f"sxwnl 模块: {dir(sxwnl)}")
        from sxwnl.calendar import SSQ
        print("calendar.SSQ 导入成功")
    except Exception as e2:
        print(f"备选导入也失败: {e2}")
        sys.exit(1)

# 2. 查看 get_all_jq 的返回格式
print("\n=== 2. 测试 get_all_jq(2024) ===")
try:
    jq_list = calendar.SSQ.get_all_jq(2024)
    print(f"返回类型: {type(jq_list)}")
    print(f"数量: {len(jq_list)}")
    for name, jd in jq_list[:5]:
        dt = fromJD(jd + 2451545)
        print(f"  {name}: jd={jd}, datetime={dt}")
except Exception as e:
    print(f"get_all_jq 失败: {e}")
    print(dir(calendar.SSQ))

# 3. 对比权威数据
print("\n=== 3. 对比权威数据 ===")
# 2024年立春权威时间: 2024-02-04 16:26:00 (北京时间)
# 2024年冬至权威时间: 2024-12-21 17:20:00 (北京时间)
try:
    jq_list = calendar.SSQ.get_all_jq(2024)
    for name, jd in jq_list:
        if name in ["立春", "冬至"]:
            dt = fromJD(jd + 2451545)
            print(f"  2024年{name}: {dt}")
except Exception as e:
    print(f"  对比失败: {e}")

# 4. 测试缺失年份 1994-2022
print("\n=== 4. 测试缺失年份 2000, 2010, 2020 ===")
for year in [2000, 2010, 2020]:
    try:
        jq_list = calendar.SSQ.get_all_jq(year)
        for name, jd in jq_list:
            if name == "立春":
                dt = fromJD(jd + 2451545)
                print(f"  {year}年立春: {dt}")
                break
    except Exception as e:
        print(f"  {year}年失败: {e}")

# 5. 测试极端年份
print("\n=== 5. 测试极端年份 1950, 2050 ===")
for year in [1950, 2050]:
    try:
        jq_list = calendar.SSQ.get_all_jq(year)
        for name, jd in jq_list:
            if name == "立春":
                dt = fromJD(jd + 2451545)
                print(f"  {year}年立春: {dt}")
                break
    except Exception as e:
        print(f"  {year}年失败: {e}")

# 6. 测试 1993 年小寒（之前缺失的）
print("\n=== 6. 测试 1993 年小寒 ===")
try:
    jq_list = calendar.SSQ.get_all_jq(1993)
    for name, jd in jq_list:
        if name == "小寒":
            dt = fromJD(jd + 2451545)
            print(f"  1993年小寒: {dt}")
            print(f"  权威时间: 1993-01-05 15:56:31")
            break
except Exception as e:
    print(f"  失败: {e}")
