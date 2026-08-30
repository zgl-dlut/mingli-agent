"""验证1990年用户的排盘数据"""
import sys
sys.path.insert(0, '/Users/zhangguangling/Downloads/命理推算/mingli-agent/backend')

from app.services.bazi_service import calculate_bazi
import json

# 1990年11月10日 8:00 女 山西晋中（经度约112.75）
result = calculate_bazi(
    birth_date="1990-11-10",
    birth_time="08:00",
    longitude=112.75,
    gender="女"
)

# 转为字典
data = result.dict() if hasattr(result, 'dict') else result.__dict__

print("=== 四柱 ===")
print(f"年柱: {data.get('年柱', data.get('year_pillar', 'N/A'))}")
print(f"月柱: {data.get('月柱', data.get('month_pillar', 'N/A'))}")
print(f"日柱: {data.get('日柱', data.get('day_pillar', 'N/A'))}")
print(f"时柱: {data.get('时柱', data.get('hour_pillar', 'N/A'))}")

print("\n=== 日主 ===")
print(f"日主: {data.get('日主', data.get('day_master', 'N/A'))}")

print("\n=== 十神 ===")
shishen = data.get('十神', data.get('ten_gods', {}))
print(json.dumps(shishen, ensure_ascii=False, indent=2))

print("\n=== 大运 ===")
dayun = data.get('大运', data.get('major_periods', []))
for d in dayun:
    if isinstance(d, dict):
        print(f"{d.get('干支', d.get('ganzhi', ''))} ({d.get('起始年龄', d.get('start_age', ''))}-{d.get('结束年龄', d.get('end_age', ''))}岁, {d.get('起始年份', d.get('start_year', ''))}-{d.get('结束年份', d.get('end_year', ''))})")
    else:
        print(d)

print("\n=== 2027年流年 ===")
print("2027流年干支: 丁未")

print("\n=== 2027年流月 ===")
liuyue_2027 = {
    "正月": "庚寅",
    "二月": "辛卯",
    "三月": "壬辰",
    "四月": "癸巳",
    "五月": "甲午",
    "六月": "乙未",
    "七月": "丙申",
    "八月": "丁酉",
    "九月": "戊戌",
    "十月": "己亥",
    "十一月": "庚子",
    "十二月": "辛丑"
}
for month, gz in liuyue_2027.items():
    print(f"{month}: {gz}")

print("\n=== 旺衰判断 ===")
wangshuai = data.get('旺衰', data.get('strength', {}))
print(json.dumps(wangshuai, ensure_ascii=False, indent=2))

print("\n=== 用神忌神 ===")
print(f"用神: {data.get('用神', data.get('useful_god', 'N/A'))}")
print(f"忌神: {data.get('忌神', data.get('harmful_god', 'N/A'))}")

print("\n=== 空亡 ===")
kongwang = data.get('空亡', data.get('void_branches', {}))
print(json.dumps(kongwang, ensure_ascii=False, indent=2))

print("\n=== 长生十二宫 ===")
changsheng = data.get('长生十二宫', data.get('twelve_stages', {}))
print(json.dumps(changsheng, ensure_ascii=False, indent=2))

print("\n=== 神煞 ===")
shensha = data.get('神煞', data.get('spiritual_stars', {}))
print(json.dumps(shensha, ensure_ascii=False, indent=2)[:500])

print("\n=== 天干五合 ===")
tianganhe = data.get('天干五合', data.get('heavenly_stems_combination', {}))
print(json.dumps(tianganhe, ensure_ascii=False, indent=2))

print("\n=== 完整数据结构 ===")
print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
