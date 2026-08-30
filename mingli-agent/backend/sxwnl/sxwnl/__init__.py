# sxwl/__init__.py
from .lunar import Lunar
from .eph0 import toJD, fromJD

class Calendar:
    def __init__(self):
        self._lunar = Lunar()

    def get_day(self, year, month, day):
        # 封装一个返回对象，让用户直接用 day.lunar_month 访问
        month_data = self._lunar.yueLiCalc(year, month)
        return month_data[day - 1]

# 实例化一个快捷对象
calendar = Calendar()