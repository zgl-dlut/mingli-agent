"""
万年历转换器 - Python版本
功能：阳历转农历、四柱八字、二十四节气查询

调用 sxwnl_python 文件夹中的 eph0.py 和 lunar.py
"""

import math
import sys
import os

# 添加当前目录和临时文件目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, '临时文件'))

from eph0 import (
    J2000, pi2, int2, rad, JD, DD, dt_T, timeStr,
    Gan, Zhi, ShX, S_aLon, S_aLon_t, MS_aLon_t,
    jqName, rad2mrad
)

# 导入lunar模块
from lunar import SSQ, obb, oba

# ==================== 真太阳时计算 ====================
def pty_zty2(t):
    """
    平太阳时转真太阳时的时差（与JS版本一致）
    t: 儒略世纪数（力学时）
    返回: 时差（单位：天）
    
    JS原版算法:
    var L = ( 1753470142 + 628331965331.8*t + 5296.74*t*t )/1000000000 + Math.PI;
    var E= (84381.4088 -46.836051*t)/rad;
    z[0]=XL0_calc(0,0,t,5)+Math.PI, z[1]=0; //地球位置
    z = llrConv( z, E ); //z太阳地心赤经
    L = rad2rrad(L-z[0]);
    return L/pi2;
    """
    from eph0 import E_Lon, llrConv, rad2rrad, rad
    
    # 平太阳黄经（弧度）- 与JS完全一致的公式
    L = (1753470142 + 628331965331.8 * t + 5296.74 * t * t) / 1000000000 + math.pi
    
    # 黄赤交角
    E = (84381.4088 - 46.836051 * t) / rad
    
    # 地球黄经 + π = 太阳黄经（使用E_Lon计算地球黄经）
    earth_lon = E_Lon(t, 5)  # 地球黄经
    sun_lon = earth_lon + math.pi  # 太阳黄经
    
    # 转换为赤道坐标（只需要赤经）
    # z = [sun_lon, 0, 1] 黄经、黄纬=0、距离=1
    z = llrConv([sun_lon, 0, 1], E)
    sun_ra = z[0]  # 太阳赤经
    
    # 时差 = (平太阳黄经 - 太阳赤经) / 2π
    L = rad2rrad(L - sun_ra)
    return L / pi2  # 单位是天


# ==================== 八字计算 ====================
def mingLiBaZi(jd, J, longitude=116.4):
    """
    命理八字计算
    jd: 儒略日(J2000起算), UT时间
    J: 地方经度(弧度)
    longitude: 经度(度)，默认北京116.4度
    
    返回: dict包含 bz_jn(年柱), bz_jy(月柱), bz_jr(日柱), bz_js(时柱), bz_zty(真太阳时)
    """
    result = {}
    
    jd2 = jd + dt_T(jd)  # 力学时
    w = S_aLon(jd2 / 36525, -1)  # 此刻太阳视黄经
    k = int2((w / pi2 * 360 + 45 + 15 * 360) / 30)  # 1984年立春起算的节气数
    
    # 计算真太阳时
    jd_local = jd + pty_zty2(jd2 / 36525) + J / math.pi / 2
    # timeStr需要完整儒略日，需要加上J2000
    result['bz_zty'] = timeStr(jd_local + J2000)
    
    jd_local += 13 / 24  # 转为前一日23点起算
    D = math.floor(jd_local)
    SC = int2((jd_local - D) * 12)  # 时辰序号
    
    # 年柱
    v = int2(k / 12 + 6000000)
    result['bz_jn'] = Gan[v % 10] + Zhi[v % 12]
    
    # 月柱
    v = k + 2 + 60000000
    result['bz_jy'] = Gan[v % 10] + Zhi[v % 12]
    
    # 日柱
    v = D - 6 + 9000000
    result['bz_jr'] = Gan[v % 10] + Zhi[v % 12]
    
    # 时柱
    v = (D - 1) * 12 + 90000000 + SC
    result['bz_js'] = Gan[v % 10] + Zhi[v % 12]
    
    return result


# ==================== 节气计算 ====================
def calc_year_jieqi(year):
    """
    计算某年的24节气
    返回: list of (节气名, 儒略日, 日期时间字符串)
    
    算法与HTML版本（万年历转换器.html）保持一致
    """
    result = []

    # 节气名称（从冬至开始，与HTML版本一致）
    # 索引0=冬至（太阳黄经270°）, 索引1=小寒（285°）, ...
    jqmc = ['冬至', '小寒', '大寒', '立春', '雨水', '惊蛰',
            '春分', '清明', '谷雨', '立夏', '小满', '芒种',
            '夏至', '小暑', '大暑', '立秋', '处暑', '白露',
            '秋分', '寒露', '霜降', '立冬', '小雪', '大雪']

    # 使用HTML版本的算法计算节气
    # 从该年1月1日附近的节气开始计算24个节气
    jd0 = JD(year, 1, 1) - J2000  # 儒略日（J2000起算）
    
    # 计算当前太阳黄经，确定起始节气
    from eph0 import S_aLon_t
    w_current = S_aLon((jd0 + dt_T(jd0) - 8/24) / 36525, 3)
    w_start = int2((w_current - 0.13) / pi2 * 24) * pi2 / 24

    for i in range(24):
        w = w_start + i * pi2 / 24  # 每个节气间隔π/12弧度（15度）
        
        # 使用HTML版本的qi_accurate算法
        t = S_aLon_t(w) * 36525
        jd_exact = t - dt_T(t) + 8 / 24
        
        # 使用HTML版本的索引公式计算节气名称索引
        idx = int2(w / pi2 * 24 + 24000006.01) % 24
        
        # 转换为日期时间
        r = DD(jd_exact + J2000)
        date_str = f"{int(r[0])}-{int(r[1]):02d}-{int(r[2]):02d}"
        # 提取时间部分（时:分:秒）
        jd_frac = jd_exact + J2000
        h = (jd_frac + 0.5 - int(jd_frac + 0.5)) * 24
        m = (h - int(h)) * 60
        s = (m - int(m)) * 60
        time_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

        result.append({
            'name': jqmc[idx],
            'jd': jd_exact,
            'date': date_str,
            'time': time_str
        })

    return result


def qi_accurate_with_ssq_refinement(target_lon_rad, target_year, jq_index, ssq):
    """
    使用SSQ对象的计算结果作为参考，进行高精度迭代计算
    w: 太阳黄经(弧度)
    target_year: 目标年份
    jq_index: 节气索引（0-23）
    ssq: 已计算的SSQ对象
    返回: 节气时刻(儒略日, J2000起算, 北京时间)
    """
    from eph0 import S_aLon, dt_T, pi2
    import math

    # 使用SSQ对象中的ZQ数组作为初始估计（如果可用）
    if hasattr(ssq, 'ZQ') and len(ssq.ZQ) > jq_index:
        est_jd = ssq.ZQ[jq_index] - J2000  # SSQ中的ZQ是包含J2000的
    else:
        # 估算目标年份的节气时间
        est_day_offset = jq_index * 15.2
        est_jd = JD(target_year, 1, 1) - J2000 + est_day_offset

    # 使用牛顿迭代法进行精确计算
    for _ in range(100):
        # 计算当前儒略日对应的力学时
        jd_utc = est_jd
        T = (jd_utc + J2000) / 36525.0
        
        try:
            # 计算当前太阳黄经
            current_lon = S_aLon(T, 10)
            
            # 计算差值
            diff = target_lon_rad - current_lon
            
            # 处理跨越0度的情况
            if diff > math.pi:
                diff -= 2 * math.pi
            elif diff < -math.pi:
                diff += 2 * math.pi
                
            # 如果差值很小，认为已经收敛
            if abs(diff) < 1e-10:
                break
                
            # 计算导数（太阳平均运动速度）
            dlon_dt = 2 * math.pi / 365.25  # 弧度/天
            
            # 牛顿迭代：x_{n+1} = x_n + Δt
            # Δt = diff / dlon_dt
            delta_t = diff / dlon_dt
            
            # 更新估计值
            est_jd += delta_t
            
            # 防止发散
            if abs(delta_t) > 5:
                est_jd -= delta_t  # 回退
                est_jd += delta_t * 0.1  # 使用较小步长
                
        except Exception as e:
            # 如果计算出错，使用简单二分法后备方案
            print(f"高精度计算失败，使用后备方案: {e}")
            est_jd = backup_jieqi_calculation(target_lon_rad, target_year)
            break
    
    # 确保结果在合理范围内
    min_jd = JD(target_year, 1, 1) - J2000 - 20
    max_jd = JD(target_year + 1, 1, 1) - J2000 + 20
    est_jd = max(min_jd, min(max_jd, est_jd))
    
    # 转换为北京时间
    jd_beijing = est_jd + dt_T(est_jd + J2000) + 8 / 24
    
    return jd_beijing


# 备用的节气计算函数已不再需要，因为新的直接计算方法更可靠
# 如果需要，可以在未来重新实现


# 以下旧的节气计算方法已由新的二分法实现替代
# qi_accurate_html_version, qi_accurate_by_lon, estimate_jieqi_time,
# qi_accurate_for_year, qi_low 等函数不再需要，已被移除

# ==================== 农历计算 ====================
# 农历月份名称
ymc = ['十一', '十二', '正', '二', '三', '四', '五', '六', '七', '八', '九', '十']
rmc = ['初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
       '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
       '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十', '卅一']
Weeks = ['日', '一', '二', '三', '四', '五', '六']


def calc_lunar(year, month, day):
    """
    计算农历信息
    返回: dict包含农历年月日、干支等信息
    """
    result = {}
    # 使用中午12点作为基准（与JS一致）
    # JS: Bd0 = int2(JD.toJD()) - J2000，其中JD设置为h=12
    # Python: JD(y,m,d)返回d日0点，需要+0.5变成中午12点，然后取整
    jd = int(JD(year, month, day) + 0.5) - J2000

    # 初始化SSQ
    ssq = SSQ()
    ssq.calcY(jd)

    # 计算农历月
    mk = int2((jd - ssq.HS[0]) / 30)
    if mk < 13 and ssq.HS[mk + 1] <= jd:
        mk += 1

    # 农历日期 - JS中 Ldi = d0 - SSQ.HS[mk]，索引0对应"初一"
    Ldi = jd - ssq.HS[mk]  # 不需要加1，因为rmc[0]='初一'
    # 确保Ldi在合理范围内
    if Ldi < 0:
        Ldi = 0
    if Ldi >= len(rmc):
        Ldi = len(rmc) - 1
    result['Ldc'] = rmc[Ldi]  # 农历日名

    # 获取月名
    v2 = ssq.ym[mk]
    if isinstance(v2, int):
        result['Lmc'] = obb.ymc[v2 % 12]
    else:
        result['Lmc'] = v2

    # 正确判断闰月
    result['Lleap'] = '闰' if ssq.leap and ssq.leap == mk else ''

    # 农历年干支（简单计算：基于公历年，与JS的Lunar.Ly一致）
    c = year - 1984 + 12000
    result['Lyear2'] = Gan[c % 10] + Zhi[c % 12]  # 干支年
    result['ShX'] = ShX[c % 12]  # 生肖

    # 星期
    week = int(jd + J2000 + 1.5 + 7000000) % 7
    result['week'] = Weeks[week]

    return result


# ==================== 主程序 ====================
def convert(year, month, day, hour=12, minute=0, longitude=116.4):
    """
    万年历转换主函数

    参数:
        year: 公历年
        month: 公历月
        day: 公历日
        hour: 时(北京时间)
        minute: 分
        longitude: 经度(默认北京116.4度)

    返回: dict包含农历、八字、节气等信息
    """
    result = {
        'input': {
            'year': year, 'month': month, 'day': day,
            'hour': hour, 'minute': minute, 'longitude': longitude
        }
    }

    # 计算儒略日 (输入是北京时间，转换为UT)
    jd = JD(year, month, day + (hour + minute/60 - 8)/24) - J2000

    # 1. 农历信息
    try:
        result['lunar'] = calc_lunar(year, month, day)
    except Exception as e:
        result['lunar'] = {'error': str(e)}

    # 2. 八字信息
    J = longitude / 180 * math.pi  # 经度转弧度
    result['bazi'] = mingLiBaZi(jd, J, longitude)

    # 3. 该年节气
    result['jieqi'] = calc_year_jieqi(year)

    return result


def print_result(result):
    """打印转换结果"""
    inp = result['input']
    print(f"\n{'='*60}")
    print(f"万年历转换结果")
    print(f"{'='*60}")
    print(f"公历: {inp['year']}年{inp['month']}月{inp['day']}日 {inp['hour']:02d}:{inp['minute']:02d}")
    print(f"经度: {inp['longitude']}°")

    # 农历
    if 'lunar' in result and 'error' not in result['lunar']:
        lunar = result['lunar']
        print(f"\n【农历信息】")
        print(f"  农历: {lunar['Lyear2']}年 【{lunar['ShX']}年】")
        print(f"  日期: {lunar['Lleap']}{lunar['Lmc']}月{lunar['Ldc']}")
        print(f"  星期: 星期{lunar['week']}")

    # 八字
    bazi = result['bazi']
    print(f"\n【四柱八字】")
    print(f"  年柱: {bazi['bz_jn']}")
    print(f"  月柱: {bazi['bz_jy']}")
    print(f"  日柱: {bazi['bz_jr']}")
    print(f"  时柱: {bazi['bz_js']}")
    print(f"  真太阳时: {bazi['bz_zty']}")

    # 节气
    print(f"\n【{inp['year']}年二十四节气】")
    jieqi = result['jieqi']
    for i, jq in enumerate(jieqi):
        print(f"  {jq['name']:4s} {jq['date']} {jq['time']}", end='')
        if (i + 1) % 2 == 0:
            print()
        else:
            print("    ", end='')
    print(f"\n{'='*60}")


if __name__ == '__main__':
    # 测试: 2026年1月16日 19:39
    result = convert(2026, 1, 16, 19, 39)
    print_result(result)

