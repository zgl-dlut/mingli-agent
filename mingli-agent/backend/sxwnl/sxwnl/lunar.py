"""
寿星万年历 - 农历排历模块 (lunar.py)
Python版本，从lunar.js转换而来

包含：
- 公历节日数据 (oba)
- 农历基础数据 (obb)
- 实气实朔计算器 (SSQ)
- 月历计算类 (Lunar)

日对象数据结构：
  d0   - 2000.0起算儒略日,北京时12:00
  di   - 所在公历月内日序数
  y    - 所在公历年
  m    - 所在公历月
  d    - 日名称(公历)
  dn   - 所在公历月的总天数
  week0- 所在月的月首的星期
  week - 星期
  weeki- 在本月中的周序号
  weekN- 本月的总周数
  Ldi  - 距农历月首的编移量,0对应初一
  Ldc  - 日名称(农历)
  Lmc  - 月名称
  Ldn  - 月大小
  Lleap- 闰状况
  Lyear2 - 干支纪年
  Lmonth2- 干支纪月
  Lday2  - 干支纪日
  XiZ    - 星座
"""

import math
from typing import List, Dict, Any, Optional, Tuple

# 导入天文计算模块
try:
    from eph0 import (
        J2000, pi2, int2, rad, JD, DD, dt_T,
        Gan, Zhi, ShX, rad2mrad
    )
except ImportError:
    # 如果eph0不可用，定义基本常量
    J2000 = 2451545
    pi2 = math.pi * 2

    def int2(v):
        return math.floor(v)

    rad = 180 * 3600 / math.pi

    def JD(y, m, d):
        """公历转儒略日"""
        n = 0
        G = 0
        if y * 372 + m * 31 + int(d) >= 588829:
            G = 1
        if m <= 2:
            m += 12
            y -= 1
        if G:
            n = int(y / 100)
            n = 2 - n + int(n / 4)
        return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + n - 1524.5

    def DD(jd):
        """儒略日数转公历"""
        jd += 0.5
        A = int(jd)
        if A >= 2299161:
            D = int((A - 1867216.25) / 36524.25)
            A += 1 + D - int(D / 4)
        A += 1524
        y = int((A - 122.1) / 365.25)
        D = A - int(365.25 * y)
        m = int(D / 30.6001)
        d = D - int(m * 30.6001)
        y -= 4716
        m -= 1
        if m > 12:
            m -= 12
        if m <= 2:
            y += 1
        return [y, m, d]

    def dt_T(t):
        return 0

    Gan = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
    Zhi = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']
    ShX = ['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪']

    def rad2mrad(v):
        v = v % (2 * math.pi)
        if v < 0:
            return v + 2 * math.pi
        return v


# =============================
# 公历基础构件
# =============================
class Oba:
    """公历基础构件 - 节日数据"""

    def __init__(self):
        # 某月的第几个星期几节日
        self.wFtv = [
            '0150I世界麻风日',  # 一月的最后一个星期日
            '0520.国际母亲节',
            '0530I全国助残日',
            '0630.父亲节',
            '0730.被奴役国家周',
            '0932I国际和平日',
            '0940.国际聋人节 世界儿童日',
            '0950I世界海事日',
            '1011.国际住房日',
            '1013I国际减轻自然灾害日(减灾日)',
            '1144I感恩节'
        ]
        self.sFtv = []  # 假日表
        self._init()

    def _init(self):
        """初始化节日数据"""
        s = (
            '01#元旦|'  # 1月
            '02I世界湿地日,10.国际气象节,14I情人节|'  # 2月
            '01.国际海豹日,03.全国爱耳日,05.1963-9999学雷锋纪念日,08I妇女节,12I植树节,'
            '12.1925-9999孙中山逝世纪念日,14.国际警察日,'
            '15I1983-9999消费者权益日,17.中国国医节,17.国际航海日,21.世界森林日,'
            '21.消除种族歧视国际日,21.世界儿歌日,22I世界水日,'
            '23I世界气象日,24.1982-9999世界防治结核病日,25.全国中小学生安全教育日,30.巴勒斯坦国土日|'
            '01I1564-9999愚人节,01.全国爱国卫生运动月(四月),01.税收宣传月(四月),'
            '07I世界卫生日,22I世界地球日,23.世界图书和版权日,24.亚非新闻工作者日|'
            '01#1889-9999劳动节,04I青年节,05.碘缺乏病防治日,08.世界红十字日,'
            '12I国际护士节,15I国际家庭日,17.国际电信日,18.国际博物馆日,'
            '20.全国学生营养日,23.国际牛奶日,31I世界无烟日|'
            '01I1925-9999国际儿童节,05.世界环境保护日,06.全国爱眼日,'
            '17.防治荒漠化和干旱日,23.国际奥林匹克日,25.全国土地日,26I国际禁毒日|'
            '01I1997-9999香港回归纪念日,01I1921-9999中共诞辰,01.世界建筑日,'
            '02.国际体育记者日,07I1937-9999抗日战争纪念日,11I世界人口日,30.非洲妇女日|'
            '01I1927-9999建军节,08.中国男子节(爸爸节)|'
            '03I1945-9999抗日战争胜利纪念,08.1966-9999国际扫盲日,08.国际新闻工作者日,'
            '09.毛泽东逝世纪念,10I中国教师节,14.世界清洁地球日,'
            '16.国际臭氧层保护日,18I九·一八事变纪念日,20.国际爱牙日,27.世界旅游日,28I孔子诞辰|'
            '01#1949-9999国庆节,01.世界音乐日,01.国际老人节,'
            '02#1949-9999国庆节假日,02.国际和平与民主自由斗争日,03#1949-9999国庆节假日,'
            '04.世界动物日,06.老人节,08.全国高血压日,08.世界视觉日,09.世界邮政日,'
            '09.万国邮联日,10I辛亥革命纪念日,10.世界精神卫生日,'
            '13.世界保健日,13.国际教师节,14.世界标准日,15.国际盲人节(白手杖节),'
            '16.世界粮食日,17.世界消除贫困日,22.世界传统医药日,24.联合国日,31.世界勤俭日|'
            '07.1917-9999十月社会主义革命纪念日,08.中国记者日,09.全国消防安全宣传教育日,'
            '10.世界青年节,11.国际科学与和平周(本日所属的一周),12.孙中山诞辰纪念日,'
            '14.世界糖尿病日,17.国际大学生节,17.世界学生节,20.彝族年,21.彝族年,'
            '21.世界问候日,21.世界电视日,22.彝族年,29.国际声援巴勒斯坦人民国际日|'
            '01I1988-9999世界艾滋病日,03.世界残疾人日,05.国际经济和社会发展志愿人员日,'
            '08.国际儿童电视日,09.世界足球日,10.世界人权日,'
            '12I西安事变纪念日,13I南京大屠杀(1937年)纪念日,20.澳门回归纪念,'
            '21.国际篮球日,24I平安夜,25I圣诞节,26.毛泽东诞辰纪念'
        )

        self.sFtv = s.split('|')
        for i in range(len(self.sFtv)):
            self.sFtv[i] = self.sFtv[i].split(',')


    def getDayName(self, u: Dict, r: Dict) -> None:
        """
        取某日节日
        u: 日对象
        r: 返回对象
        r['A'] 重要喜庆日子名称
        r['B'] 重要日子名称
        r['C'] 各种日子名称
        r['Fjia'] 放假日子
        """
        m0 = ('0' if u['m'] < 10 else '') + str(u['m'])
        d0 = ('0' if u['d'] < 10 else '') + str(u['d'])

        if u['week'] == 0 or u['week'] == 6:
            r['Fjia'] = 1  # 星期日或星期六放假

        # 按公历日期查找
        if u['m'] - 1 < len(self.sFtv):
            for item in self.sFtv[u['m'] - 1]:
                if not item or item[:2] != d0:
                    continue
                s = item[2:]
                type_char = s[0] if s else ''

                if len(s) > 5 and s[5] == '-':  # 有年限的
                    try:
                        year_start = int(s[1:5])
                        year_end = int(s[6:10])
                        if u['y'] < year_start or u['y'] > year_end:
                            continue
                        s = s[10:]
                    except:
                        continue
                else:
                    if u['y'] < 1850:
                        continue
                    s = s[1:]

                if type_char == '#':
                    r['A'] = r.get('A', '') + s + ' '
                    r['Fjia'] = 1
                if type_char == 'I':
                    r['B'] = r.get('B', '') + s + ' '
                if type_char == '.':
                    r['C'] = r.get('C', '') + s + ' '

        # 按周查找
        w = u['weeki']
        if u['week'] >= u['week0']:
            w += 1
        w2 = w
        if u['weeki'] == u['weekN'] - 1:
            w2 = 5
        w_str = m0 + str(w) + str(u['week'])
        w2_str = m0 + str(w2) + str(u['week'])

        for item in self.wFtv:
            s2 = item[:4]
            if s2 != w_str and s2 != w2_str:
                continue
            type_char = item[4]
            s = item[5:]
            if type_char == '#':
                r['A'] = r.get('A', '') + s + ' '
                r['Fjia'] = 1
            if type_char == 'I':
                r['B'] = r.get('B', '') + s + ' '
            if type_char == '.':
                r['C'] = r.get('C', '') + s + ' '

    def getHuiLi(self, d0: int, r: Dict) -> None:
        """
        回历计算
        d0: 儒略日(J2000起算)
        r: 返回对象
        """
        d = d0 + 503105
        z = int2(d / 10631)  # 10631为一周期(30年)
        d -= z * 10631
        y = int2((d + 0.5) / 354.366)  # 加0.5的作用是保证闰年正确
        d -= int2(y * 354.366 + 0.5)
        m = int2((d + 0.11) / 29.51)  # 分子加0.11,分母加0.01的作用是第354或355天的月分保持为12月
        d -= int2(m * 29.5 + 0.5)
        r['Hyear'] = z * 30 + y + 1
        r['Hmonth'] = m + 1
        r['Hday'] = d + 1


# 创建全局实例
oba = Oba()


# =============================
# 农历基础构件
# =============================
class Obb:
    """农历基础构件 - 常数、通用函数等"""

    def __init__(self):
        # 中文数字
        self.numCn = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
        # 天干
        self.Gan = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
        # 地支
        self.Zhi = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']
        # 生肖
        self.ShX = ['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪']
        # 星座
        self.XiZ = ['摩羯', '水瓶', '双鱼', '白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手']
        # 月相名称表
        self.yxmc = ['朔', '上弦', '望', '下弦']
        # 节气名称表
        self.jqmc = ['冬至', '小寒', '大寒', '立春', '雨水', '惊蛰', '春分', '清明', '谷雨', '立夏',
                     '小满', '芒种', '夏至', '小暑', '大暑', '立秋', '处暑', '白露', '秋分', '寒露',
                     '霜降', '立冬', '小雪', '大雪']
        # 月名称(建寅)
        self.ymc = ['十一', '十二', '正', '二', '三', '四', '五', '六', '七', '八', '九', '十']
        # 日名称
        self.rmc = ['初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
                    '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
                    '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十', '卅一']

        # 纪年表
        self.JNB = []
        self._init()

    def _init(self):
        """初始化纪年数据"""
        # 纪年数据结构：起始公元,使用年数,已用年数,朝代,朝号,皇帝,年号
        s = (
            '-2069,45,0,夏,禹,,禹,-2024,10,0,夏,启,,启,-2014,25,0,夏,太康,,太康,'
            '-1986,14,0,夏,仲康,,仲康,-1972,28,0,夏,相,,相,-1944,2,0,夏,后羿,,后羿,'
            '-1942,38,0,夏,寒浞,,寒浞,-1904,21,0,夏,少康,,少康,-1883,17,0,夏,杼,,杼,'
            '-1866,26,0,夏,槐,,槐,-1840,18,0,夏,芒,,芒,-1822,16,0,夏,泄,,泄,'
            '-1806,59,0,夏,不降,,不降,-1747,21,0,夏,扃,,扃,-1726,21,0,夏,廑,,廑,'
            '-1705,31,0,夏,孔甲,,孔甲,-1674,11,0,夏,皋,,皋,-1663,11,0,夏,发,,发,'
            '-1652,53,0,夏,桀,,桀,'
            # 后续朝代数据省略，实际使用时需要完整数据
            '1949,9999,1948,当代,中国,,公历纪元'
        )

        parts = s.split(',')
        self.JNB = []
        for i in range(0, len(parts) - 6, 7):
            try:
                self.JNB.append(int(parts[i]))      # 起始年
                self.JNB.append(int(parts[i + 1]))  # 使用年数
                self.JNB.append(int(parts[i + 2]))  # 已用年数
                self.JNB.append(parts[i + 3])       # 朝代
                self.JNB.append(parts[i + 4])       # 朝号
                self.JNB.append(parts[i + 5])       # 皇帝
                self.JNB.append(parts[i + 6])       # 年号
            except:
                pass

    def getNH(self, y: int) -> str:
        """取年号"""
        s = ''
        ob = self.JNB
        for i in range(0, len(ob), 7):
            j = ob[i]
            if y < j or y >= j + ob[i + 1]:
                continue
            c = ob[i + 6] + str(y - j + 1 + ob[i + 2]) + '年'  # 年号及年次
            prefix = ';' if s else ''
            s += prefix + '[' + ob[i + 3] + ']' + ob[i + 4] + ' ' + ob[i + 5] + ' ' + c
        return s

    def getDayName(self, u: Dict, r: Dict) -> None:
        """计算农历节日"""
        # 按农历日期查找重要节假日
        d = u['Lmc'] + ('月' if len(u['Lmc']) < 2 else '') + u['Ldc']

        if u['Lleap'] != '闰':
            if d == '正月初一':
                r['A'] = r.get('A', '') + '春节 '
                r['Fjia'] = 1
            if d == '正月初二':
                r['B'] = r.get('B', '') + '大年初二 '
                r['Fjia'] = 1
            if d == '五月初五':
                r['A'] = r.get('A', '') + '端午节 '
                r['Fjia'] = 1
            if d == '八月十五':
                r['A'] = r.get('A', '') + '中秋节 '
                r['Fjia'] = 1
            if d == '正月十五':
                r['A'] = r.get('A', '') + '元宵节 '
                r['B'] = r.get('B', '') + '上元节 '
                r['C'] = r.get('C', '') + '壮族歌墟节 苗族踩山节 达斡尔族卡钦 '
            if d == '正月十六':
                r['C'] = r.get('C', '') + '侗族芦笙节(至正月二十) '
            if d == '正月廿五':
                r['C'] = r.get('C', '') + '填仓节 '
            if d == '正月廿九':
                r['C'] = r.get('C', '') + '送穷日 '
            if d == '二月初一':
                r['C'] = r.get('C', '') + '瑶族忌鸟节 '
            if d == '二月初二':
                r['B'] = r.get('B', '') + '春龙节(龙抬头) '
                r['C'] = r.get('C', '') + '畲族会亲节 '
            if d == '二月初八':
                r['C'] = r.get('C', '') + '傈傈族刀杆节 '
            if d == '三月初三':
                r['B'] = r.get('B', '') + '北帝诞 '
                r['C'] = r.get('C', '') + '苗族黎族歌墟节 '
            if d == '三月十五':
                r['C'] = r.get('C', '') + '白族三月街(至三月二十) '
            if d == '三月廿三':
                r['B'] = r.get('B', '') + '天后诞 妈祖诞 '
            if d == '四月初八':
                r['B'] = r.get('B', '') + '牛王诞 '
            if d == '四月十八':
                r['C'] = r.get('C', '') + '锡伯族西迁节 '
            if d == '五月十三':
                r['B'] = r.get('B', '') + '关帝诞 '
                r['C'] = r.get('C', '') + '阿昌族泼水节 '
            if d == '五月廿二':
                r['C'] = r.get('C', '') + '鄂温克族米阔鲁节 '
            if d == '五月廿九':
                r['C'] = r.get('C', '') + '瑶族达努节 '
            if d == '六月初六':
                r['B'] = r.get('B', '') + '姑姑节 天贶节 '
                r['C'] = r.get('C', '') + '壮族祭田节 瑶族尝新节 '
            if d == '六月廿四':
                r['C'] = r.get('C', '') + '火把节、星回节(彝、白、佤、阿昌、纳西、基诺族) '
            if d == '七月初七':
                r['B'] = r.get('B', '') + '七夕(中国情人节,乞巧节,女儿节) '
            if d == '七月十三':
                r['C'] = r.get('C', '') + '侗族吃新节 '
            if d == '七月十五':
                r['B'] = r.get('B', '') + '中元节 鬼节'
            if d == '九月初九':
                r['B'] = r.get('B', '') + '重阳节 '
            if d == '十月初一':
                r['B'] = r.get('B', '') + '祭祖节(十月朝) '
            if d == '十月十五':
                r['B'] = r.get('B', '') + '下元节 '
            if d == '十月十六':
                r['C'] = r.get('C', '') + '瑶族盘王节 '
            if d == '十二初八':
                r['B'] = r.get('B', '') + '腊八节 '

        # 最后一月
        if u.get('Lmc2') == '正':
            if d == '十二三十' and u['Ldn'] == 30:
                r['A'] = r.get('A', '') + '除夕 '
                r['Fjia'] = 1
            if d == '十二廿九' and u['Ldn'] == 29:
                r['A'] = r.get('A', '') + '除夕 '
                r['Fjia'] = 1
            if d == '十二廿三':
                r['B'] = r.get('B', '') + '小年 '

        # 节气
        if u.get('Ljq'):
            if u['Ljq'] == '清明':
                r['A'] = r.get('A', '') + u['Ljq'] + ' '
                r['Fjia'] = 1
            else:
                r['B'] = r.get('B', '') + u['Ljq'] + ' '

        # 农历杂节
        # 数九
        if u.get('cur_dz') is not None and 0 <= u['cur_dz'] < 81:
            w = self.numCn[int(u['cur_dz'] / 9) + 1]
            if u['cur_dz'] % 9 == 0:
                r['B'] = r.get('B', '') + '『' + w + '九』 '
            else:
                r['C'] = r.get('C', '') + w + '九第' + str(u['cur_dz'] % 9 + 1) + '天 '

        # 三伏
        w = u['Lday2'][0] if u.get('Lday2') else ''
        w2 = u['Lday2'][1] if u.get('Lday2') and len(u['Lday2']) > 1 else ''

        if u.get('cur_xz') is not None:
            if 20 <= u['cur_xz'] < 30 and w == '庚':
                r['B'] = r.get('B', '') + '初伏 '
            if 30 <= u['cur_xz'] < 40 and w == '庚':
                r['B'] = r.get('B', '') + '中伏 '
        if u.get('cur_lq') is not None:
            if 0 <= u['cur_lq'] < 10 and w == '庚':
                r['B'] = r.get('B', '') + '末伏 '
        if u.get('cur_mz') is not None:
            if 0 <= u['cur_mz'] < 10 and w == '丙':
                r['B'] = r.get('B', '') + '入梅 '
        if u.get('cur_xs') is not None:
            if 0 <= u['cur_xs'] < 12 and w2 == '未':
                r['B'] = r.get('B', '') + '出梅 '


    def qi_accurate(self, W: float) -> float:
        """精气计算"""
        try:
            from eph0 import S_aLon_t
            t = S_aLon_t(W) * 36525
            return t - dt_T(t) + 8 / 24
        except:
            # 简化计算
            return self.qi_low(W)

    def so_accurate(self, W: float) -> float:
        """精朔计算"""
        try:
            from eph0 import MS_aLon_t
            t = MS_aLon_t(W) * 36525
            return t - dt_T(t) + 8 / 24
        except:
            # 简化计算
            return self.so_low(W)

    def qi_accurate2(self, jd: float) -> float:
        """精气(根据儒略日)"""
        d = math.pi / 12
        w = int((jd + 293) / 365.2422 * 24) * d
        a = self.qi_accurate(w)
        if a - jd > 5:
            return self.qi_accurate(w - d)
        if a - jd < -5:
            return self.qi_accurate(w + d)
        return a

    def so_accurate2(self, jd: float) -> float:
        """精朔(根据儒略日)"""
        return self.so_accurate(int((jd + 8) / 29.5306) * math.pi * 2)

    def qi_low(self, W: float) -> float:
        """低精度定气计算"""
        v = 628.3319653318
        t = (W - 4.895062166) / v
        t -= (53 * t * t + 334116 * math.cos(4.67 + 628.307585 * t) +
              2061 * math.cos(2.678 + 628.3076 * t) * t) / v / 10000000
        L = (48950621.66 + 6283319653.318 * t + 53 * t * t +
             334166 * math.cos(4.669257 + 628.307585 * t) +
             3489 * math.cos(4.6261 + 1256.61517 * t) +
             2060.6 * math.cos(2.67823 + 628.307585 * t) * t -
             994 - 834 * math.sin(2.1824 - 33.75705 * t))
        t -= (L / 10000000 - W) / 628.332 + (32 * (t + 1.8) * (t + 1.8) - 20) / 86400 / 36525
        return t * 36525 + 8 / 24

    def so_low(self, W: float) -> float:
        """低精度定朔计算"""
        v = 7771.37714500204
        t = (W + 1.08472) / v
        t -= (-0.0000331 * t * t +
              0.10976 * math.cos(0.785 + 8328.6914 * t) +
              0.02224 * math.cos(0.187 + 7214.0629 * t) -
              0.03342 * math.cos(4.669 + 628.3076 * t)) / v
        t += (32 * (t + 1.8) * (t + 1.8) - 20) / 86400 / 36525
        return t * 36525 + 8 / 24


# 创建全局实例
obb = Obb()


# =============================
# 实气实朔计算器 (SSQ)
# =============================
class SSQ:
    """
    实气实朔计算器
    适用范围 -722年2月22日——1959年12月
    平气平朔计算使用古历参数进行计算
    定朔、定气计算使用开普勒椭圆轨道计算
    """

    def __init__(self):
        self.SB = ''  # 朔修正表
        self.QB = ''  # 气修正表

        # 朔直线拟合参数
        self.suoKB = [
            1457698.231017, 29.53067166,   # -721-12-17 古历·春秋
            1546082.512234, 29.53085106,   # -479-12-11 古历·战国
            1640640.735300, 29.53060000,   # -221-10-31 古历·秦汉
            1642472.151543, 29.53085439,   # -216-11-04 古历·秦汉
            1683430.509300, 29.53086148,   # -104-12-25 汉书·律历志(太初历)
            1752148.041079, 29.53085097,   #   85-02-13 后汉书·律历志(四分历)
            1807724.481520, 29.53059851,   #  237-04-12 晋书·律历志(景初历)
            1883618.114100, 29.53060000,   #  445-01-24 宋书·律历志(何承天元嘉历)
            1907360.704700, 29.53060000,   #  510-01-26 宋书·律历志(祖冲之大明历)
            1936596.224900, 29.53060000,   #  590-02-10 随书·律历志(开皇历)
            1939135.675300, 29.53060000,   #  597-01-24 随书·律历志(大业历)
            1947168.00                      #  619-01-21
        ]

        # 气直线拟合参数
        self.qiKB = [
            1640650.479938, 15.21842500,   # -221-11-09 古历·秦汉
            1642476.703182, 15.21874996,   # -216-11-09 古历·秦汉
            1683430.515601, 15.218750011,  # -104-12-25 汉书·律历志(太初历)
            1752157.640664, 15.218749978,  #   85-02-23 后汉书·律历志(四分历)
            1807675.003759, 15.218620279,  #  237-02-22 晋书·律历志(景初历)
            1883627.765182, 15.218612292,  #  445-02-03 宋书·律历志(何承天元嘉历)
            1907369.128100, 15.218449176,  #  510-02-03 宋书·律历志(祖冲之大明历)
            1936603.140413, 15.218425000,  #  590-02-17 随书·律历志(开皇历)
            1939145.524180, 15.218466998,  #  597-02-03 随书·律历志(大业历)
            1947180.798300, 15.218524844,  #  619-02-03 新唐书·历志(戊寅元历)
            1964362.041824, 15.218533526,  #  666-02-17 新唐书·历志(麟德历)
            1987372.340971, 15.218513908,  #  729-02-16 新唐书·历志(大衍历)
            1999653.819126, 15.218530782,  #  762-10-03 新唐书·历志(五纪历)
            2007445.469786, 15.218535181,  #  784-02-01 新唐书·历志(正元历)
            2021324.917146, 15.218526248,  #  822-02-01 新唐书·历志(宣明历)
            2047257.232342, 15.218519654,  #  893-01-31 新唐书·历志(崇玄历)
            2070282.898213, 15.218425000,  #  956-02-16 旧五代·历志(钦天历)
            2073204.872850, 15.218515221,  #  964-02-16 宋史·律历志(应天历)
            2080144.500926, 15.218530782,  #  983-02-16 宋史·律历志(乾元历)
            2086703.688963, 15.218523776,  # 1001-01-31 宋史·律历志(仪天历)
            2110033.182763, 15.218425000,  # 1064-12-15 宋史·律历志(明天历)
            2111190.300888, 15.218425000,  # 1068-02-15 宋史·律历志(崇天历)
            2113731.271005, 15.218515671,  # 1075-01-30 李锐补修(奉元历)
            2120670.840263, 15.218425000,  # 1094-01-30 宋史·律历志
            2123973.309063, 15.218425000,  # 1103-02-14 李锐补修(占天历)
            2125068.997336, 15.218477932,  # 1106-02-14 宋史·律历志(纪元历)
            2136026.312633, 15.218472436,  # 1136-02-14 宋史·律历志(统元历)
            2156099.495538, 15.218425000,  # 1191-01-29 宋史·律历志(会元历)
            2159021.324663, 15.218425000,  # 1199-01-29 宋史·律历志(统天历)
            2162308.575254, 15.218461742,  # 1208-01-30 宋史·律历志(开禧历)
            2178485.706538, 15.218425000,  # 1252-05-15 淳祐历
            2178759.662849, 15.218445786,  # 1253-02-13 会天历
            2185334.020800, 15.218425000,  # 1271-02-13 宋史·律历志(成天历)
            2187525.481425, 15.218425000,  # 1277-02-12 本天历
            2188621.191481, 15.218437494,  # 1280-02-13 元史·历志(郭守敬授时历)
            2322147.76                      # 1645-09-21
        ]

        # 排月序数据
        self.leap = 0           # 闰月位置
        self.ym = []            # 各月名称
        self.ZQ = []            # 中气表
        self.HS = []            # 合朔表
        self.dx = []            # 各月大小
        self.Yn = []            # 年计数

        self._init()

    def _init(self):
        """初始化修正表"""
        # 619-01-21开始16598个朔日修正表
        suoS = (
            "EqoFscDcrFpmEsF2DfFideFelFpFfFfFiaipqti1ksttikptikqckstekqttgkqttgkqteksttikptikq2fjstgjqttjkqttgkqt"
            "ekstfkptikq2tijstgjiFkirFsAeACoFsiDaDiADc1AFbBfgdfikijFifegF1FhaikgFag1E2btaieeibggiffdeigFfqDfaiBkF"
            "1kEaikhkigeidhhdiegcFfakF1ggkidbiaedksaFffckekidhhdhdikcikiakicjF1deedFhFccgicdekgiFbiaikcfi1kbFibef"
            "gEgFdcFkFeFkdcfkF1kfkcickEiFkDacFiEfbiaejcFfffkhkdgkaiei1ehigikhdFikfckF1dhhdikcfgjikhfjicjicgiehdik"
        )
        suoS += (
            "cikggcifgiejF1jkieFhegikggcikFegiegkfjebhigikggcikdgkaFkijcfkcikfkcifikiggkaeeigefkcdfcfkhkdgkegieid"
            "hijcFfakhfgeidieidiegikhfkfckfcjbdehdikggikgkfkicjicjF1dbidikFiggcifgiejkiegkigcdiegfggcikdbgfgefjF1"
            "kfegikggcikdgFkeeijcfkcikfkekcikdgkabhkFikaffcfkhkdgkegbiaekfkiakicjhfgqdq2fkiakgkfkhfkfcjiekgFebicg"
            "gbedF1jikejbbbiakgbgkacgiejkijjgigfiakggfggcibFifjefjF1kfekdgjcibFeFkijcfkfhkfkeaieigekgbhkfikidfcje"
        )
        suoS += (
            "aibgekgdkiffiffkiakF1jhbakgdki1dj1ikfkicjicjieeFkgdkicggkighdF1jfgkgfgbdkicggfggkidFkiekgijkeigfiski"
            "ggfaidheigF1jekijcikickiggkidhhdbgcfkFikikhkigeidieFikggikhkffaffijhidhhakgdkhkijF1kiakF1kfheakgdkif"
            "iggkigicjiejkieedikgdfcggkigieeiejfgkgkigbgikicggkiaideeijkefjeijikhkiggkiaidheigcikaikffikijgkiahi1"
            "hhdikgjfifaakekighie1hiaikggikhkffakicjhiahaikggikhkijF1kfejfeFhidikggiffiggkigicjiekgieeigikggiffig"
        )
        suoS += (
            "gkidheigkgfjkeigiegikifiggkidhedeijcfkFikikhkiggkidhh1ehigcikaffkhkiggkidhh1hhigikekfiFkFikcidhh1hit"
            "cikggikhkfkicjicghiediaikggikhkijbjfejfeFhaikggifikiggkigiejkikgkgieeigikggiffiggkigieeigekijcijikgg"
            "ifikiggkideedeijkefkfckikhkiggkidhh1ehijcikaffkhkiggkidhh1hhigikhkikFikfckcidhh1hiaikgjikhfjicjicgie"
            "hdikcikggifikigiejfejkieFhegikggifikiggfghigkfjeijkhigikggifikiggkigieeijcijcikfksikifikiggkidehdeij"
        )
        suoS += (
            "cfdckikhkiggkhghh1ehijikifffffkhsFngErD1pAfBoDd1BlEtFqA2AqoEpDqElAEsEeB2BmADlDkqBtC1FnEpDqnEmFsFsAFn"
            "llBbFmDsDiCtDmAB2BmtCgpEplCpAEiBiEoFqFtEqsDcCnFtADnFlEgdkEgmEtEsCtDmADqFtAFrAtEcCqAE1BoFqC1F1DrFtBmF"
            "tAC2ACnFaoCgADcADcCcFfoFtDlAFgmFqBq2bpEoAEmkqnEeCtAE1bAEqgDfFfCrgEcBrACfAAABqAAB1AAClEnFeCtCgAADqDoB"
            "mtAAACbFiAAADsEtBqAB2FsDqpFqEmFsCeDtFlCeDtoEpClEqAAFrAFoCgFmFsFqEnAEcCqFeCtFtEnAEeFtAAEkFnErAABbFkAD"
        )
        suoS += "nAAeCtFeAfBoAEpFtAABtFqAApDcCGJ"

        # 1645-09-23开始7567个节气修正表
        qiS = (
            "FrcFs22AFsckF2tsDtFqEtF1posFdFgiFseFtmelpsEfhkF2anmelpFlF1ikrotcnEqEq2FfqmcDsrFor22FgFrcgDscFs22FgEe"
            "FtE2sfFs22sCoEsaF2tsD1FpeE2eFsssEciFsFnmelpFcFhkF2tcnEqEpFgkrotcnEqrEtFermcDsrE222FgBmcmr22DaEfnaF22"
            "2sD1FpeForeF2tssEfiFpEoeFssD1iFstEqFppDgFstcnEqEpFg11FscnEqrAoAF2ClAEsDmDtCtBaDlAFbAEpAAAAAD2FgBiBqo"
            "BbnBaBoAAAAAAAEgDqAdBqAFrBaBoACdAAf1AACgAAAeBbCamDgEifAE2AABa1C1BgFdiAAACoCeE1ADiEifDaAEqAAFe1AcFbcA"
        )
        qiS += "AAAAF1iFaAAACpACmFmAAAAAAAACrDaAAADG0"

        self.SB = self._jieya(suoS)
        self.QB = self._jieya(qiS)

    def _jieya(self, s: str) -> str:
        """气朔解压缩"""
        o = "0000000000"
        o2 = o + o

        s = s.replace('J', '00')
        s = s.replace('I', '000')
        s = s.replace('H', '0000')
        s = s.replace('G', '00000')
        s = s.replace('t', '02')
        s = s.replace('s', '002')
        s = s.replace('r', '0002')
        s = s.replace('q', '00002')
        s = s.replace('p', '000002')
        s = s.replace('o', '0000002')
        s = s.replace('n', '00000002')
        s = s.replace('m', '000000002')
        s = s.replace('l', '0000000002')
        s = s.replace('k', '01')
        s = s.replace('j', '0101')
        s = s.replace('i', '001')
        s = s.replace('h', '001001')
        s = s.replace('g', '0001')
        s = s.replace('f', '00001')
        s = s.replace('e', '000001')
        s = s.replace('d', '0000001')
        s = s.replace('c', '00000001')
        s = s.replace('b', '000000001')
        s = s.replace('a', '0000000001')
        s = s.replace('A', o2 + o2 + o2)
        s = s.replace('B', o2 + o2 + o)
        s = s.replace('C', o2 + o2)
        s = s.replace('D', o2 + o)
        s = s.replace('E', o2)
        s = s.replace('F', o)
        return s

    def so_low(self, W: float) -> float:
        """低精度定朔计算"""
        v = 7771.37714500204
        t = (W + 1.08472) / v
        t -= (-0.0000331 * t * t +
              0.10976 * math.cos(0.785 + 8328.6914 * t) +
              0.02224 * math.cos(0.187 + 7214.0629 * t) -
              0.03342 * math.cos(4.669 + 628.3076 * t)) / v
        t += (32 * (t + 1.8) * (t + 1.8) - 20) / 86400 / 36525
        return t * 36525 + 8 / 24

    def qi_low(self, W: float) -> float:
        """低精度定气计算"""
        v = 628.3319653318
        t = (W - 4.895062166) / v
        t -= (53 * t * t + 334116 * math.cos(4.67 + 628.307585 * t) +
              2061 * math.cos(2.678 + 628.3076 * t) * t) / v / 10000000
        L = (48950621.66 + 6283319653.318 * t + 53 * t * t +
             334166 * math.cos(4.669257 + 628.307585 * t) +
             3489 * math.cos(4.6261 + 1256.61517 * t) +
             2060.6 * math.cos(2.67823 + 628.307585 * t) * t -
             994 - 834 * math.sin(2.1824 - 33.75705 * t))
        t -= (L / 10000000 - W) / 628.332 + (32 * (t + 1.8) * (t + 1.8) - 20) / 86400 / 36525
        return t * 36525 + 8 / 24

    def qi_high(self, W: float) -> float:
        """较高精度气"""
        try:
            from eph0 import S_aLon_t, S_aLon_t2
            t = S_aLon_t2(W) * 36525
            t = t - dt_T(t) + 8 / 24
            v = ((t + 0.5) % 1) * 86400
            if v < 1200 or v > 86400 - 1200:
                t = S_aLon_t(W) * 36525 - dt_T(t) + 8 / 24
            return t
        except:
            return self.qi_low(W)

    def so_high(self, W: float) -> float:
        """较高精度朔"""
        try:
            from eph0 import MS_aLon_t2
            t = MS_aLon_t2(W) * 36525
            t = t - dt_T(t) + 8 / 24
            # 注意：暂时不使用MS_aLon_t进行边界精确化，因为该函数有精度问题
            # 使用MS_aLon_t2已经足够满足农历计算需求（误差约10分钟以内）
            return t
        except:
            return self.so_low(W)

    def calc(self, jd: float, qs: str = '') -> int:
        """
        计算气或朔
        jd: 应靠近所要取得的气朔日
        qs: '气'时算节气的儒略日，否则算朔
        """
        jd += J2000

        B = self.suoKB
        pc = 14
        if qs == '气':
            B = self.qiKB
            pc = 7

        f1 = B[0] - pc
        f2 = B[len(B) - 1] - pc
        f3 = 2436935

        # 平气朔表中首个之前或1960.1.1以后，使用现代天文算法
        if jd < f1 or jd >= f3:
            if qs == '气':
                return int(self.qi_high(int((jd + pc - 2451259) / 365.2422 * 24) * math.pi / 12) + 0.5)
            else:
                return int(self.so_high(int((jd + pc - 2451551) / 29.5306) * math.pi * 2) + 0.5)

        # 平气或平朔
        if f1 <= jd < f2:
            i = 0
            while i < len(B) - 2:
                if jd + pc < B[i + 2]:
                    break
                i += 2
            D = B[i] + B[i + 1] * int((jd + pc - B[i]) / B[i + 1])
            D = int(D + 0.5)
            if D == 1683460:
                D += 1  # 修正-103年1月24日的朔日
            return D - J2000

        # 定气或定朔
        if f2 <= jd < f3:
            if qs == '气':
                D = int(self.qi_low(int((jd + pc - 2451259) / 365.2422 * 24) * math.pi / 12) + 0.5)
                idx = int((jd - f2) / 365.2422 * 24)
                if idx < len(self.QB):
                    n = self.QB[idx]
                else:
                    n = '0'
            else:
                D = int(self.so_low(int((jd + pc - 2451551) / 29.5306) * math.pi * 2) + 0.5)
                idx = int((jd - f2) / 29.5306)
                if idx < len(self.SB):
                    n = self.SB[idx]
                else:
                    n = '0'

            if n == '1':
                return D + 1
            if n == '2':
                return D - 1
            return D

        return 0

    def calcY(self, jd: float) -> None:
        """
        农历排月序计算
        可定出农历,有效范围：两个冬至之间(冬至一 <= d < 冬至二)
        """
        A = self.ZQ  # 中气表
        B = self.HS  # 合朔表

        # 该年的气
        W = int2((jd - 355 + 183) / 365.2422) * 365.2422 + 355  # 355是2000.12冬至
        if self.calc(W, '气') > jd:
            W -= 365.2422

        # 25个节气时刻(北京时间),从冬至开始到下一个冬至以后
        self.ZQ = [0] * 26
        for i in range(25):
            self.ZQ[i] = self.calc(W + 15.2184 * i, '气')

        # 补算二气,确保一年中所有月份的"气"全部被计算在内
        self.ZQ_pe1 = self.calc(W - 15.2, '气')
        self.ZQ_pe2 = self.calc(W - 30.4, '气')

        # 今年"首朔"的日月黄经差
        w = self.calc(self.ZQ[0], '朔')  # 求较靠近冬至的朔日
        if w > self.ZQ[0]:
            w -= 29.53

        # 该年所有朔,包含14个月的始末
        self.HS = [0] * 16
        for i in range(15):
            self.HS[i] = self.calc(w + 29.5306 * i, '朔')

        # 月大小
        self.leap = 0
        self.dx = [0] * 15
        self.ym = [0] * 15
        for i in range(14):
            self.dx[i] = self.HS[i + 1] - self.HS[i]  # 月大小
            self.ym[i] = i  # 月序初始化

        # -721年至-104年的后九月及月建问题
        YY = int2((self.ZQ[0] + 10 + 180) / 365.2422) + 2000  # 确定年份
        if -721 <= YY <= -104:
            ns = [0] * 9
            for i in range(3):
                yy = YY + i - 1
                # 颁行历年首, 闰月名称, 月建
                if yy >= -721:
                    ns[i] = self.calc(1457698 - J2000 + int2(0.342 + (yy + 721) * 12.368422) * 29.5306, '朔')
                    ns[i + 3] = '十三'
                    ns[i + 6] = 2  # 春秋历
                if yy >= -479:
                    ns[i] = self.calc(1546083 - J2000 + int2(0.500 + (yy + 479) * 12.368422) * 29.5306, '朔')
                    ns[i + 3] = '十三'
                    ns[i + 6] = 2  # 战国历
                if yy >= -220:
                    ns[i] = self.calc(1640641 - J2000 + int2(0.866 + (yy + 220) * 12.369000) * 29.5306, '朔')
                    ns[i + 3] = '后九'
                    ns[i + 6] = 11  # 秦汉历

            for i in range(14):
                nn = 2
                while nn >= 0:
                    if self.HS[i] >= ns[nn]:
                        break
                    nn -= 1
                f1 = int2((self.HS[i] - ns[nn] + 15) / 29.5306)  # 该月积数
                if f1 < 12:
                    self.ym[i] = obb.ymc[(f1 + ns[nn + 6]) % 12]
                else:
                    self.ym[i] = ns[nn + 3]
            return

        # 无中气置闰法确定闰月
        if self.HS[13] <= self.ZQ[24]:  # 第13月的月末没有超过冬至
            i = 1
            while i < 13:
                if self.HS[i + 1] <= self.ZQ[2 * i]:
                    break
                i += 1
            self.leap = i
            for j in range(i, 14):
                self.ym[j] -= 1

        # 名称转换(月建别名)
        for i in range(14):
            Dm = self.HS[i] + J2000  # 初一的儒略日
            v2 = self.ym[i]  # 月建序号
            mc = obb.ymc[v2 % 12]  # 月建对应的默认月名称

            if 1724360 <= Dm <= 1729794:
                mc = obb.ymc[(v2 + 1) % 12]  # 8.01.15至23.12.02
            elif 1807724 <= Dm <= 1808699:
                mc = obb.ymc[(v2 + 1) % 12]  # 237.04.12至239.12.13
            elif 1999349 <= Dm <= 1999467:
                mc = obb.ymc[(v2 + 2) % 12]  # 761.12.02至762.03.30
            elif 1973067 <= Dm <= 1977052:
                if v2 % 12 == 0:
                    mc = '正'
                if v2 == 2:
                    mc = '一'  # 689.12.18至700.11.15

            if Dm == 1729794 or Dm == 1808699:
                mc = '拾贰'  # 避免两个连续十二月

            self.ym[i] = mc


# 创建全局SSQ实例
ssq = SSQ()



# =============================
# 月历计算类
# =============================
class Lunar:
    """
    月历计算类
    用于计算公历某月的农历信息
    """

    def __init__(self):
        self.lun = []  # 日对象列表
        for i in range(31):
            self.lun.append({})

        self.w0 = 0    # 本月第一天的星期
        self.y = 0     # 公历年份
        self.m = 0     # 公历月分
        self.d0 = 0    # 月首儒略日数
        self.dn = 0    # 本月天数
        self.Ly = ''   # 干支纪年
        self.ShX = ''  # 生肖
        self.nianhao = ''  # 年号

    def yueLiCalc(self, By: int, Bm: int) -> None:
        """
        计算某月的日历信息
        By: 公历年
        Bm: 公历月
        """
        # 计算月首和月天数
        Bd0 = int(JD(By, Bm, 1)) - J2000  # 公历月首,中午

        # 计算下月首
        next_m = Bm + 1
        next_y = By
        if next_m > 12:
            next_y += 1
            next_m = 1
        Bdn = int(JD(next_y, next_m, 1)) - J2000 - Bd0  # 本月天数

        self.w0 = (Bd0 + J2000 + 1 + 7000000) % 7  # 本月第一天的星期
        self.y = By
        self.m = Bm
        self.d0 = Bd0
        self.dn = Bdn

        # 所属公历年对应的农历干支纪年
        c = By - 1984 + 12000
        self.Ly = obb.Gan[c % 10] + obb.Zhi[c % 12]
        self.ShX = obb.ShX[c % 12]
        self.nianhao = obb.getNH(By)

        # 提取各日信息
        for i in range(Bdn):
            ob = self.lun[i]
            ob['d0'] = Bd0 + i      # 儒略日,北京时12:00
            ob['di'] = i            # 公历月内日序数
            ob['y'] = By            # 公历年
            ob['m'] = Bm            # 公历月
            ob['dn'] = Bdn          # 公历月天数
            ob['week0'] = self.w0   # 月首的星期
            ob['week'] = (self.w0 + i) % 7  # 当前日的星期
            ob['weeki'] = int2((self.w0 + i) / 7)  # 本日所在的周序号
            ob['weekN'] = int2((self.w0 + Bdn - 1) / 7) + 1  # 本月的总周数

            # 公历日名称
            d_info = DD(ob['d0'] + J2000)
            ob['d'] = d_info[2]

            # 农历月历
            if not ssq.ZQ or len(ssq.ZQ) < 25 or ob['d0'] < ssq.ZQ[0] or ob['d0'] >= ssq.ZQ[24]:
                ssq.calcY(ob['d0'])

            mk = int2((ob['d0'] - ssq.HS[0]) / 30)
            if mk < 0:
                mk = 0
            if mk > 13:
                mk = 13
            if mk < 13 and mk + 1 < len(ssq.HS) and ssq.HS[mk + 1] <= ob['d0']:
                mk += 1

            ob['Ldi'] = ob['d0'] - ssq.HS[mk]  # 距农历月首的编移量
            if ob['Ldi'] < 0:
                ob['Ldi'] = 0
            if ob['Ldi'] >= len(obb.rmc):
                ob['Ldi'] = len(obb.rmc) - 1
            ob['Ldc'] = obb.rmc[ob['Ldi']]     # 农历日名称
            ob['cur_dz'] = ob['d0'] - ssq.ZQ[0]   # 距冬至的天数
            ob['cur_xz'] = ob['d0'] - ssq.ZQ[12]  # 距夏至的天数
            ob['cur_lq'] = ob['d0'] - ssq.ZQ[15]  # 距立秋的天数
            ob['cur_mz'] = ob['d0'] - ssq.ZQ[11]  # 距芒种的天数
            ob['cur_xs'] = ob['d0'] - ssq.ZQ[13]  # 距小暑的天数

            # 月的信息
            if ob['d0'] == ssq.HS[mk] or ob['d0'] == Bd0:
                ob['Lmc'] = ssq.ym[mk]  # 月名称
                ob['Ldn'] = ssq.dx[mk]  # 月大小
                ob['Lleap'] = '闰' if ssq.leap and ssq.leap == mk else ''
                ob['Lmc2'] = ssq.ym[mk + 1] if mk < 13 else '未知'
            else:
                ob2 = self.lun[i - 1]
                ob['Lmc'] = ob2['Lmc']
                ob['Ldn'] = ob2['Ldn']
                ob['Lleap'] = ob2['Lleap']
                ob['Lmc2'] = ob2['Lmc2']

            # 节气
            qk = int2((ob['d0'] - ssq.ZQ[0] - 7) / 15.2184)
            if qk < 23 and ob['d0'] >= ssq.ZQ[qk + 1]:
                qk += 1
            if ob['d0'] == ssq.ZQ[qk]:
                ob['Ljq'] = obb.jqmc[qk]
            else:
                ob['Ljq'] = ''

            # 月相和节气时刻初始化
            ob['yxmc'] = ob['yxjd'] = ob['yxsj'] = ''
            ob['jqmc'] = ob['jqjd'] = ob['jqsj'] = ''

            # 干支纪年处理(以立春为界)
            D = ssq.ZQ[3] + (-365 if ob['d0'] < ssq.ZQ[3] else 0) + 365.25 * 16 - 35
            ob['Lyear'] = int(D / 365.2422 + 0.5)

            # 以正月初一定年首
            D = ssq.HS[2]  # 一般第3个月为春节
            for j in range(14):
                if ssq.ym[j] != '正' or (ssq.leap == j and j):
                    continue
                D = ssq.HS[j]
                if ob['d0'] < D:
                    D -= 365
                    break
            D = D + 5810
            ob['Lyear0'] = int(D / 365.2422 + 0.5)

            D = ob['Lyear'] + 12000
            ob['Lyear2'] = obb.Gan[D % 10] + obb.Zhi[D % 12]  # 干支纪年(立春)
            D = ob['Lyear0'] + 12000
            ob['Lyear3'] = obb.Gan[D % 10] + obb.Zhi[D % 12]  # 干支纪年(正月)
            ob['Lyear4'] = ob['Lyear0'] + 1984 + 2698  # 黄帝纪年

            # 纪月处理
            mk2 = int2((ob['d0'] - ssq.ZQ[0]) / 30.43685)
            if mk2 < 12 and ob['d0'] >= ssq.ZQ[2 * mk2 + 1]:
                mk2 += 1
            D = mk2 + int2((ssq.ZQ[12] + 390) / 365.2422) * 12 + 900000
            ob['Lmonth'] = D % 12
            ob['Lmonth2'] = obb.Gan[D % 10] + obb.Zhi[D % 12]

            # 纪日
            D = ob['d0'] - 6 + 9000000
            ob['Lday2'] = obb.Gan[D % 10] + obb.Zhi[D % 12]

            # 星座
            mk3 = int2((ob['d0'] - ssq.ZQ[0] - 15) / 30.43685)
            if mk3 < 11 and ob['d0'] >= ssq.ZQ[2 * mk3 + 2]:
                mk3 += 1
            ob['XiZ'] = obb.XiZ[(mk3 + 12) % 12] + '座'

            # 回历
            oba.getHuiLi(ob['d0'], ob)

            # 节日
            ob['A'] = ob['B'] = ob['C'] = ''
            ob['Fjia'] = 0
            oba.getDayName(ob, ob)  # 公历节日
            obb.getDayName(ob, ob)  # 农历节日

    def getDayInfo(self, day_index: int) -> Dict:
        """获取某日的详细信息"""
        if 0 <= day_index < self.dn:
            return self.lun[day_index]
        return {}

    def getLunarDate(self, day_index: int) -> str:
        """获取农历日期字符串"""
        if 0 <= day_index < self.dn:
            ob = self.lun[day_index]
            return ob.get('Lleap', '') + ob.get('Lmc', '') + '月' + ob.get('Ldc', '')
        return ''

    def getGanZhi(self, day_index: int) -> Dict:
        """获取干支信息"""
        if 0 <= day_index < self.dn:
            ob = self.lun[day_index]
            return {
                'year': ob.get('Lyear2', ''),
                'month': ob.get('Lmonth2', ''),
                'day': ob.get('Lday2', '')
            }
        return {}


# =============================
# 辅助函数
# =============================
def timeStr(jd: float) -> str:
    """儒略日转时间字符串"""
    d = DD(jd + J2000)
    h = (jd + 0.5 - int(jd + 0.5)) * 24
    m = (h - int(h)) * 60
    s = (m - int(m)) * 60
    return f"{d[0]}-{d[1]:02d}-{d[2]:02d} {int(h):02d}:{int(m):02d}:{int(s):02d}"


def JD2str(jd: float) -> str:
    """儒略日转日期字符串"""
    d = DD(jd)
    return f"{d[0]}-{d[1]:02d}-{d[2]:02d}"


def nianLiCalc(y: int) -> List[Dict]:
    """
    年历计算
    返回该年所有农历月的信息
    """
    ssq.calcY(int2((y - 2000) * 365.2422 + 180))
    result = []

    for i in range(14):
        if ssq.HS[i + 1] > ssq.ZQ[24]:
            break  # 已包含下一年的冬至

        month_info = {
            'leap': '闰' if ssq.leap and i == ssq.leap else '',
            'name': ssq.ym[i],
            'days': ssq.dx[i],
            'start_jd': ssq.HS[i],
            'start_date': JD2str(ssq.HS[i] + J2000)
        }
        result.append(month_info)

    return result


def getLunarDateByJD(jd: float) -> Dict:
    """
    根据儒略日获取农历日期
    jd: J2000起算的儒略日
    """
    # 确保农历数据已计算
    if not ssq.ZQ or len(ssq.ZQ) < 25 or jd < ssq.ZQ[0] or jd >= ssq.ZQ[24]:
        ssq.calcY(jd)

    # 找到所在月
    mk = int2((jd - ssq.HS[0]) / 30)
    if mk < 0:
        mk = 0
    if mk > 13:
        mk = 13
    if mk < 13 and mk + 1 < len(ssq.HS) and ssq.HS[mk + 1] <= jd:
        mk += 1

    day_in_month = int(jd - ssq.HS[mk])
    if day_in_month < 0:
        day_in_month = 0
    if day_in_month >= len(obb.rmc):
        day_in_month = len(obb.rmc) - 1

    return {
        'month': ssq.ym[mk] if mk < len(ssq.ym) else '未知',
        'day': obb.rmc[day_in_month],
        'day_num': day_in_month + 1,
        'leap': '闰' if ssq.leap and ssq.leap == mk else '',
        'month_days': ssq.dx[mk] if mk < len(ssq.dx) else 30
    }


def getGanZhiByJD(jd: float) -> Dict:
    """
    根据儒略日获取干支
    jd: J2000起算的儒略日
    """
    # 确保农历数据已计算
    if not ssq.ZQ or jd < ssq.ZQ[0] or jd >= ssq.ZQ[24]:
        ssq.calcY(jd)

    # 纪年(以立春为界)
    D = ssq.ZQ[3] + (-365 if jd < ssq.ZQ[3] else 0) + 365.25 * 16 - 35
    year_num = int(D / 365.2422 + 0.5) + 12000
    year_gz = obb.Gan[year_num % 10] + obb.Zhi[year_num % 12]

    # 纪月
    mk = int2((jd - ssq.ZQ[0]) / 30.43685)
    if mk < 12 and jd >= ssq.ZQ[2 * mk + 1]:
        mk += 1
    D = mk + int2((ssq.ZQ[12] + 390) / 365.2422) * 12 + 900000
    month_gz = obb.Gan[D % 10] + obb.Zhi[D % 12]

    # 纪日
    D = int(jd) - 6 + 9000000
    day_gz = obb.Gan[D % 10] + obb.Zhi[D % 12]

    return {
        'year': year_gz,
        'month': month_gz,
        'day': day_gz
    }


# =============================
# 模块导出
# =============================
__all__ = [
    'oba', 'obb', 'ssq', 'Lunar',
    'Oba', 'Obb', 'SSQ',
    'timeStr', 'JD2str', 'nianLiCalc',
    'getLunarDateByJD', 'getGanZhiByJD',
    'J2000', 'JD', 'DD', 'int2'
]


# =============================
# 测试代码
# =============================
if __name__ == '__main__':
    print("=" * 50)
    print("寿星万年历 - 农历模块测试")
    print("=" * 50)

    # 测试月历计算
    lunar = Lunar()
    lunar.yueLiCalc(2024, 1)

    print(f"\n2024年1月:")
    print(f"干支纪年: {lunar.Ly}")
    print(f"生肖: {lunar.ShX}")
    print(f"本月天数: {lunar.dn}")

    # 打印前几天的信息
    print("\n前5天的农历信息:")
    for i in range(min(5, lunar.dn)):
        ob = lunar.lun[i]
        print(f"  {ob['d']}日: {ob.get('Lleap', '')}{ob['Lmc']}月{ob['Ldc']} "
              f"干支:{ob['Lyear2']}年{ob['Lmonth2']}月{ob['Lday2']}日 "
              f"星座:{ob['XiZ']}")

    # 测试儒略日转农历
    print("\n测试儒略日转农历:")
    test_jd = int(JD(2024, 2, 10)) - J2000
    lunar_date = getLunarDateByJD(test_jd)
    print(f"2024-02-10 农历: {lunar_date['leap']}{lunar_date['month']}月{lunar_date['day']}")

    # 测试干支
    gz = getGanZhiByJD(test_jd)
    print(f"干支: {gz['year']}年 {gz['month']}月 {gz['day']}日")

    print("\n" + "=" * 50)
    print("lunar.py 模块测试完成!")
    print("=" * 50)