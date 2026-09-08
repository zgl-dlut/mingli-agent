"""
农历展示工具：将数据库中存储的公历日期转换为用户原始历法的展示字符串。

背景：前端在提交生辰时，会把农历日期转换为公历后存入 birth_date 字段，
calendar_type 字段记录用户原始选择的历法。因此展示时需要把公历日期
转回农历（当 calendar_type == 'lunar' 时），避免出现"公历日期 + 农历标签"
的张冠李戴。
"""
from datetime import datetime


def get_display_birth_date(birth_date: str, calendar_type: str) -> str:
    """
    根据用户原始历法，返回用于展示的生辰日期字符串。

    :param birth_date: 数据库中存储的公历日期，格式 YYYY-MM-DD
    :param calendar_type: 用户原始历法 'solar' 或 'lunar'
    :return: 展示用日期字符串。solar 直接返回原值；lunar 返回农历 YYYY-MM-DD
    """
    if calendar_type != 'lunar':
        return birth_date

    try:
        import cnlunar

        dt = datetime.strptime(birth_date, "%Y-%m-%d")
        lunar = cnlunar.Lunar(dt)
        year = lunar.lunarYear
        month = lunar.lunarMonth
        day = lunar.lunarDay
        leap = '闰' if lunar.isLunarLeapMonth else ''
        return f"{year}-{leap}{month:02d}-{day:02d}"
    except Exception:
        # 转换失败时兜底返回公历日期，避免展示崩溃
        return birth_date
