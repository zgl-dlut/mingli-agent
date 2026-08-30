"""
寿星万年历 - 星历基础模块 (eph0.py)
Python版本，从eph0.js转换而来

包含：
- 天文常数
- 三角函数和数学工具
- 角度格式化
- 儒略日计算
- 岁差和章动计算
- 星历数据表
- 日月坐标计算

注意：本模块是万年历的核心计算模块
"""

import math
import json
import os
import pickle
from typing import List, Tuple, Optional, Any, Union

# 解决资源定位问题
def load_coefficients():
    # 获取当前 eph0.py 所在的文件夹绝对路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    earth_path = os.path.join(base_dir, 'coefficients_earth.json')
    moon_path = os.path.join(base_dir, 'coefficients_moon.json')

# 确保系数在整个程序中只加载一次
_coeffs_cache = None

def get_coeffs():
    global _coeffs_cache
    if _coeffs_cache is None:
        _coeffs_cache = load_coefficients()
    return _coeffs_cache

# ==================== 加载系数文件 ====================
def load_coefficients():
    """加载系数文件，使用pickle缓存以提高性能（使用包内路径）"""
    # 使用当前文件所在目录作为基准路径，避免依赖工作目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 尝试加载拆分后的系数文件
    earth_json_path = os.path.join(base_dir, 'coefficients_earth.json')
    moon_json_path = os.path.join(base_dir, 'coefficients_moon.json')
    
    # 检查是否存在拆分后的文件
    if os.path.exists(earth_json_path) and os.path.exists(moon_json_path):
        # 加载地球相关系数
        try:
            with open(earth_json_path, 'r', encoding='utf-8') as f:
                earth_data = json.load(f)
        except json.JSONDecodeError as e:
            # 如果UTF-8编码失败，尝试其他编码或修复
            print(f"警告: coefficients_earth.json 文件编码有问题: {e}")
            # 尝试修复文件
            with open(earth_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # 尝试修复一些常见的编码错误
                content = content.replace('璺濈', '?')
                # 创建临时文件
                temp_path = earth_json_path + '.tmp'
                with open(temp_path, 'w', encoding='utf-8') as tmp_f:
                    tmp_f.write(content)
                # 重新加载修复后的文件
                with open(temp_path, 'r', encoding='utf-8') as f:
                    earth_data = json.load(f)
                # 删除临时文件
                os.remove(temp_path)
        except UnicodeDecodeError as e:
            # 如果遇到编码错误，尝试使用其他编码
            print(f"警告: coefficients_earth.json 文件编码有问题，尝试使用GBK编码: {e}")
            with open(earth_json_path, 'r', encoding='gbk') as f:
                earth_data = json.load(f)
        
        # 加载月球相关系数
        try:
            with open(moon_json_path, 'r', encoding='utf-8') as f:
                moon_data = json.load(f)
        except json.JSONDecodeError as e:
            # 如果UTF-8编码失败，尝试其他编码或修复
            print(f"警告: coefficients_moon.json 文件编码有问题: {e}")
            # 尝试修复文件
            with open(moon_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # 尝试修复一些常见的编码错误
                content = content.replace('璺濈', '?')
                # 创建临时文件
                temp_path = moon_json_path + '.tmp'
                with open(temp_path, 'w', encoding='utf-8') as tmp_f:
                    tmp_f.write(content)
                # 重新加载修复后的文件
                with open(temp_path, 'r', encoding='utf-8') as f:
                    moon_data = json.load(f)
                # 删除临时文件
                os.remove(temp_path)
        except UnicodeDecodeError as e:
            # 如果遇到编码错误，尝试使用其他编码
            print(f"警告: coefficients_moon.json 文件编码有问题，尝试使用GBK编码: {e}")
            with open(moon_json_path, 'r', encoding='gbk') as f:
                moon_data = json.load(f)
        
        # 合并数据
        combined_data = {
            'vsop87': earth_data.get('vsop87', {}),
            'elp2000': moon_data.get('elp2000', {})
        }
        
        # 尝试加载缓存
        cache_path = os.path.join(base_dir, 'coefficients.pkl')
        if os.path.exists(cache_path):
            earth_mtime = os.path.getmtime(earth_json_path)
            moon_mtime = os.path.getmtime(moon_json_path)
            cache_mtime = os.path.getmtime(cache_path)
            
            if cache_mtime >= earth_mtime and cache_mtime >= moon_mtime:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
        
        # 缓存合并后的数据
        with open(cache_path, 'wb') as f:
            pickle.dump(combined_data, f)
        
        return combined_data
    else:
        # 如果拆分文件不存在，尝试加载原始文件
        json_path = os.path.join(base_dir, 'coefficients.json')
        cache_path = os.path.join(base_dir, 'coefficients.pkl')
        
        if os.path.exists(cache_path) and os.path.exists(json_path):
            if os.path.getmtime(cache_path) >= os.path.getmtime(json_path):
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        with open(cache_path, 'wb') as f:
            pickle.dump(data, f)
            
        return data

# 加载系数数据
coefficients = load_coefficients()

# ==================== 天文常数 ====================
cs_rEar = 6378.1366  # 地球赤道半径(千米)
cs_rEarA = 0.99834 * cs_rEar  # 平均半径
cs_ba = 0.99664719  # 地球极赤半径比
cs_ba2 = cs_ba * cs_ba  # 地球极赤半径比的平方
cs_AU = 1.49597870691e8  # 天文单位长度(千米)
cs_sinP = cs_rEar / cs_AU  # sin(太阳视差)
cs_PI = math.asin(cs_sinP)  # 太阳视差
cs_GS = 299792.458  # 光速(千米/秒)
cs_Agx = cs_AU / cs_GS / 86400 / 36525  # 每天文单位的光行时间(儒略世纪)
cs_xxHH = [116, 584, 780, 399, 378, 370, 367, 367]  # 行星会合周期
xxName = ['地球', '水星', '金星', '火星', '木星', '土星', '天王星', '海王星', '冥王星']

rad = 180 * 3600 / math.pi  # 每弧度的角秒数
radd = 180 / math.pi  # 每弧度的度数
pi2 = math.pi * 2
pi_2 = math.pi / 2
J2000 = 2451545

cs_k = 0.2725076  # 月亮与地球的半径比(用于半影计算)
cs_k2 = 0.2722810  # 月亮与地球的半径比(用于本影计算)
cs_k0 = 109.1222  # 太阳与地球的半径比(对应959.64)
cs_sMoon = cs_k * cs_rEar * 1.0000036 * rad  # 用于月亮视半径计算
cs_sMoon2 = cs_k2 * cs_rEar * 1.0000036 * rad  # 用于月亮视半径计算
cs_sSun = 959.64  # 用于太阳视半径计算

# ==================== 三角函数别名 ====================
def int2(v: float) -> int:
    """取整数部分"""
    return math.floor(v)

def mod2(v: float, n: float) -> float:
    """求余"""
    return (v % n + n) % n

sqrt = math.sqrt
floor = math.floor
abs = abs  # Python内置
sin = math.sin
cos = math.cos
tan = math.tan
asin = math.asin
acos = math.acos
atan = math.atan
atan2 = math.atan2

# ==================== 角度格式化 ====================
def rad2strE(d: float, tim: int, ext: int) -> str:
    """
    将弧度转为字串
    tim=0输出格式示例: -23°59' 48.23"
    tim=1输出格式示例:  18h 29m 44.52s
    ext为小数保留位数
    """
    s = " "
    w1, w2, w3 = "°", "'", '"'
    if d < 0:
        d = -d
        s = '-'
    if tim:
        d *= 12 / math.pi
        w1, w2, w3 = "h ", "m", "s"
    else:
        d *= 180 / math.pi

    a = math.floor(d)
    d = (d - a) * 60
    b = math.floor(d)
    d = (d - b) * 60
    c = math.floor(d)

    Q = 10 ** ext
    d = math.floor((d - c) * Q + 0.5)
    if d >= Q:
        d -= Q
        c += 1
    if c >= 60:
        c -= 60
        b += 1
    if b >= 60:
        b -= 60
        a += 1

    a_str = f"{a:3d}"
    b_str = f"{b:02d}"
    c_str = f"{c:02d}"
    d_str = f"{int(d):0{ext}d}" if ext else ""

    result = s + a_str + w1 + b_str + w2 + c_str
    if ext:
        result += "." + d_str + w3
    return result

def rad2str(d: float, tim: int) -> str:
    """将弧度转为字串,保留2位"""
    return rad2strE(d, tim, 2)

def rad2str2(d: float) -> str:
    """将弧度转为字串,精确到分"""
    s = "+"
    w1, w2 = "°", "'"
    if d < 0:
        d = -d
        s = '-'
    d *= 180 / math.pi
    a = math.floor(d)
    b = math.floor((d - a) * 60 + 0.5)
    if b >= 60:
        b -= 60
        a += 1
    return f"{s}{a:3d}{w1}{b:02d}{w2}"

def m2fm(v: float, fx: int, fs: int) -> str:
    """秒转为分秒,fx为小数点位数,fs为1转为"分秒"格式否则转为"角度分秒"格式"""
    gn = ''
    if v < 0:
        v = -v
        gn = '-'
    f = math.floor(v / 60)
    m = v - f * 60
    if not fs:
        return gn + str(f) + "'" + f"{m:.{fx}f}" + '"'
    if fs == 1:
        return gn + str(f) + '分' + f"{m:.{fx}f}" + '秒'
    if fs == 2:
        return gn + str(f) + 'm' + f"{m:.{fx}f}" + 's'
    return ''

def str2rad(s: str, f: int = 0) -> float:
    """串转弧度, f=1表示输入的s为时分秒"""
    import re
    fh = 1
    f_mult = 15 if f else 1
    if '-' in s:
        fh = -1
    s = re.sub(r'h|m|s|(-)|(°)|\'|\"', ' ', s)
    s = re.sub(r' +', ' ', s)
    s = s.strip()
    parts = s.split(' ')
    while len(parts) < 3:
        parts.append('0')
    return fh * (float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])) / rad * f_mult


# ==================== 数学工具 ====================
def rad2mrad(v: float) -> float:
    """对超过0-2PI的角度转为0-2PI"""
    v = v % (2 * math.pi)
    if v < 0:
        return v + 2 * math.pi
    return v

def rad2rrad(v: float) -> float:
    """对超过-PI到PI的角度转为-PI到PI"""
    v = v % (2 * math.pi)
    if v <= -math.pi:
        return v + 2 * math.pi
    if v > math.pi:
        return v - 2 * math.pi
    return v

def llr2xyz(JW: List[float]) -> List[float]:
    """球面转直角坐标"""
    J, W, R = JW[0], JW[1], JW[2]
    return [
        R * cos(W) * cos(J),
        R * cos(W) * sin(J),
        R * sin(W)
    ]

def xyz2llr(xyz: List[float]) -> List[float]:
    """直角坐标转球"""
    x, y, z = xyz[0], xyz[1], xyz[2]
    r2 = sqrt(x * x + y * y + z * z)
    return [
        rad2mrad(atan2(y, x)),
        asin(z / r2),
        r2
    ]

def llrConv(JW: List[float], E: float) -> List[float]:
    """球面坐标旋转 - 黄道赤道坐标变换,赤到黄E取负"""
    J, W = JW[0], JW[1]
    r0 = atan2(sin(J) * cos(E) - tan(W) * sin(E), cos(J))
    r1 = asin(cos(E) * sin(W) + sin(E) * cos(W) * sin(J))
    return [rad2mrad(r0), r1, JW[2]]

def CD2DP(z: List[float], L: float, fa: float, gst: float) -> List[float]:
    """赤道坐标转为地平坐标"""
    a = [z[0] + math.pi / 2 - gst - L, z[1], z[2]]
    a = llrConv(a, math.pi / 2 - fa)
    a[0] = rad2mrad(math.pi / 2 - a[0])
    return a

def j1_j2(J1: float, W1: float, J2: float, W2: float) -> float:
    """求角度差"""
    dJ = rad2rrad(J1 - J2)
    dW = W1 - W2
    if abs(dJ) < 1 / 1000 and abs(dW) < 1 / 1000:
        dJ *= math.cos((W1 + W2) / 2)
        return math.sqrt(dJ * dJ + dW * dW)
    return math.acos(math.sin(W1) * math.sin(W2) + math.cos(W1) * math.cos(W2) * math.cos(dJ))

def h2g(z: List[float], a: List[float]) -> List[float]:
    """日心球面转地心球面,Z星体球面坐标,A地球球面坐标"""
    a = llr2xyz(a)  # 地球
    z = llr2xyz(z)  # 星体
    z[0] -= a[0]
    z[1] -= a[1]
    z[2] -= a[2]
    return xyz2llr(z)

def shiChaJ(gst: float, L: float, fa: float, J: float, W: float) -> float:
    """视差角(不是视差)"""
    H = gst + L - J  # 天体的时角
    return rad2mrad(atan2(sin(H), tan(fa) * cos(W) - sin(W) * cos(H)))


# ==================== deltat T计算 ====================
# TD - UT1 计算表
dt_at = [
    -4000, 108371.7, -13036.80, 392.000, 0.0000,
    -500, 17201.0, -627.82, 16.170, -0.3413,
    -150, 12200.6, -346.41, 5.403, -0.1593,
    150, 9113.8, -328.13, -1.647, 0.0377,
    500, 5707.5, -391.41, 0.915, 0.3145,
    900, 2203.4, -283.45, 13.034, -0.1778,
    1300, 490.1, -57.35, 2.085, -0.0072,
    1600, 120.0, -9.81, -1.532, 0.1403,
    1700, 10.2, -0.91, 0.510, -0.0370,
    1800, 13.4, -0.72, 0.202, -0.0193,
    1830, 7.8, -1.81, 0.416, -0.0247,
    1860, 8.3, -0.13, -0.406, 0.0292,
    1880, -5.4, 0.32, -0.183, 0.0173,
    1900, -2.3, 2.06, 0.169, -0.0135,
    1920, 21.2, 1.69, -0.304, 0.0167,
    1940, 24.2, 1.22, -0.064, 0.0031,
    1960, 33.2, 0.51, 0.231, -0.0109,
    1980, 51.0, 1.29, -0.026, 0.0032,
    2000, 63.87, 0.1, 0, 0,
    2005, 64.7, 0.21, 0, 0,
    2012, 66.8, 0.22, 0, 0,
    2018, 69.0, 0.36, 0, 0,
    2028, 72.6
]

def dt_ext(y: float, jsd: float) -> float:
    """二次曲线外推"""
    dy = (y - 1820) / 100
    return -20 + jsd * dy * dy

def dt_calc(y: float) -> float:
    """计算世界时与原子时之差,传入年"""
    y0 = dt_at[len(dt_at) - 2]  # 表中最后一年
    t0 = dt_at[len(dt_at) - 1]  # 表中最后一年的deltatT

    if y >= y0:
        jsd = 31  # jsd是y1年之后的加速度估计
        if y > y0 + 100:
            return dt_ext(y, jsd)
        v = dt_ext(y, jsd)  # 二次曲线外推
        dv = dt_ext(y0, jsd) - t0  # ye年的二次外推与te的差
        return v - dv * (y0 + 100 - y) / 100

    d = dt_at
    i = 0
    while i < len(d) - 5:
        if y < d[i + 5]:
            break
        i += 5

    t1 = (y - d[i]) / (d[i + 5] - d[i]) * 10
    t2 = t1 * t1
    t3 = t2 * t1
    return d[i + 1] + d[i + 2] * t1 + d[i + 3] * t2 + d[i + 4] * t3

def dt_T(t: float) -> float:
    """传入儒略日(J2000起算),计算TD-UT(单位:日)"""
    return dt_calc(t / 365.2425 + 2000) / 86400.0


# ==================== 儒略日计算 ====================
def JD(y: int, m: int, d: float) -> float:
    """公历转儒略日,y为年,m为月,d为日(可含小数)"""
    n = 0
    G = 0
    if y * 372 + m * 31 + int(d) >= 588829:
        G = 1  # 判断是否为格里高利历日1582*372+10*31+15
    if m <= 2:
        m += 12
        y -= 1
    if G:
        n = int(y / 100)
        n = 2 - n + int(n / 4)  # 加百年闰
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + n - 1524.5

def DD(jd: float) -> List[int]:
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

def DD0(y: int) -> float:
    """返回y年1月1日的儒略日数"""
    return int(365.25 * (y + 4715)) - int(y / 100) + int(y / 400) + 1.5

def Y_M(jd: float) -> str:
    """儒略日转年月"""
    r = DD(jd)
    return f"{r[0]}-{r[1]}"

def toJD(r: List[int]) -> float:
    """日期数组转儒略日"""
    return JD(r[0], r[1], r[2])


def fromJD(jd: float) -> List[int]:
    """儒略日转回日期数组（兼容旧接口名）"""
    return DD(jd)


# ==================== 岁差计算 ====================
def prece(t: float) -> float:
    """黄道岁差(角秒)"""
    t2 = t * t
    t3 = t2 * t
    return 50287.92262 * t + 111.24406 * t2 + 0.07699 * t3 - 0.23479 * t2 * t2

def hcjj(t: float) -> float:
    """黄赤交角(弧度)"""
    t2 = t * t
    t3 = t2 * t
    return (84381.4060 - 46.836769 * t - 0.0001831 * t2 + 0.00200340 * t3) / rad

def hcjj1(t: float) -> float:
    """黄赤交角(弧度),t是儒略世纪数,返回Date黄赤交角"""
    t2 = t * t
    t3 = t2 * t
    return (84381.448 - 46.8150 * t - 0.00059 * t2 + 0.001813 * t3) / rad


# ==================== 章动计算 ====================
# 章动表
nutB = [
    2.1824391966, -33.757045954, 0.0000362262, 3.7340E-08, -2.8793E-10,
    -171996, -1742, 92025, 89,
    3.5069406862, 1256.663930738, 0.0000105845, 6.9813E-10, -2.2815E-10,
    -13187, -16, 5736, -31,
    1.3375032491, 16799.418221925, -0.0000511866, 6.4626E-08, -5.3543E-10,
    -2274, -2, 977, -5,
    4.3648783932, -67.514091907, 0.0000724525, 7.4681E-08, -5.7586E-10,
    2062, 2, -895, 5,
    0.0431251803, -628.301955171, 0.0000026820, 6.5935E-10, 5.5705E-11,
    -1426, 34, 54, -1,
    2.3555557435, 8328.691425719, 0.0001545547, 2.5033E-07, -1.1863E-09,
    712, 1, -7, 0,
    3.4638155059, 1884.965885909, 0.0000116217, 6.9573E-10, -2.2972E-10,
    -517, 12, 224, -6,
    5.4382493597, 16833.175267879, -0.0000501819, 6.4417E-08, -5.3686E-10,
    -386, -4, 200, 0,
    3.6930589926, 25128.109647645, 0.0001033681, 3.1496E-07, -1.7218E-09,
    -301, 0, 129, -1,
    3.5500658664, 628.361975567, 0.0000132664, 1.3575E-09, -1.7245E-10,
    217, -5, -95, 3
]

def nutation(t: float) -> List[float]:
    """章动计算,t是J2000起算的儒略世纪数"""
    t2 = t * t
    t3 = t2 * t
    t4 = t3 * t
    B = nutB
    dL = 0
    dE = 0
    for i in range(0, len(B), 9):
        c = B[i] + B[i + 1] * t + B[i + 2] * t2 + B[i + 3] * t3 + B[i + 4] * t4
        dL += (B[i + 5] + B[i + 6] * t / 10) * sin(c)
        dE += (B[i + 7] + B[i + 8] * t / 10) * cos(c)
    return [dL / 10000 / rad, dE / 10000 / rad]  # 黄经章动,交角章动

def nutationLon(t: float) -> float:
    """只计算黄经章动"""
    t2 = t * t
    B = nutB
    dL = 0
    for i in range(0, len(B), 9):
        c = B[i] + B[i + 1] * t + B[i + 2] * t2
        dL += B[i + 5] * sin(c)
    return dL / 10000 / rad

# 简化版章动表（用于nutationLon2，与JS版本一致，每5个元素一组）
# 格式：[角度参数0, 角度参数1, 角度参数2, 黄经章动系数, 交角章动系数]
nutB2 = [
    2.1824,  -33.75705, 36e-6, -1720, 920,
    3.5069, 1256.66393, 11e-6,  -132,  57,
    1.3375, 16799.4182, -51e-6,  -23,  10,
    4.3649,   -67.5141, 72e-6,   21,   -9,
    0.04,    -628.302,  0,      -14,    0,
    2.36,    8328.691,  0,        7,    0,
    3.46,    1884.966,  0,       -5,    2,
    5.44,   16833.175,  0,       -4,    2,
    3.69,   25128.110,  0,       -3,    0,
    3.55,     628.362,  0,        2,    0
]

def nutationLon2(t: float) -> float:
    """只计算黄经章动(与原始JS一致，使用简化版章动表)"""
    t2 = t * t
    dL = 0
    B = nutB2
    # nutB2每5个元素为一组: [角度参数3个, 黄经章动系数, 交角章动系数]
    for i in range(0, len(B), 5):
        if i == 0:
            a = -1.742 * t
        else:
            a = 0
        dL += (B[i + 3] + a) * sin(B[i] + B[i + 1] * t + B[i + 2] * t2)
    return dL / 100 / rad

def gxc_sunLon(t: float) -> float:
    """太阳光行差,t是儒略世纪数"""
    v = -0.043126 + 628.301955 * t - 0.000002732 * t * t  # 太阳黄经
    e = 0.016708634 - 0.000042037 * t - 0.0000001267 * t * t
    return (-20.49552 * (1 + e * cos(v))) / rad

def gxc_moonLon(t: float) -> float:
    """月球光行差,t是儒略世纪数"""
    return -3.4E-6

def addPrece(t: float, zb: List[float]) -> None:
    """补岁差"""
    zb[0] = rad2mrad(zb[0] + (t * 50.29 + t * t * 0.0111) / rad)



# ==================== 恒星时计算 ====================
def pGST(T: float, dt: float) -> float:
    """格林尼治平恒星时(不含赤经章动及非多项式部分),T是力学时,dt是deltatT"""
    t = (T + dt) / 36525
    t2 = t * t
    t3 = t2 * t
    t4 = t3 * t
    return (0.7790572732640 + 1.00273781191135448 * (T + dt) +
            (0.014506 + 4612.15739966 * t + 1.39667721 * t2 - 0.00009344 * t3 + 0.00001882 * t4) / rad)

def pGST2(jd: float) -> float:
    """格林尼治真恒星时(含赤经章动)"""
    T = jd - J2000
    dt = dt_T(T)
    t = (T + dt) / 36525
    E = hcjj(t)
    nut = nutation(t)
    return rad2mrad(pGST(T, dt) + nut[0] * cos(E + nut[1]))


# ==================== 太阳坐标计算 ====================
# 太阳运动表
E10 = [
    1.75347045673, 0, 0,
    0.03341656456, 4.66925680417, 6283.0758499914,
    0.00034894275, 4.62610241759, 12566.1516999828,
    0.00003417571, 2.82886579606, 3.5231183490,
    0.00003497056, 2.74411800971, 5753.3848848968,
    0.00003135896, 3.62767041758, 77713.7714681205,
    0.00002676218, 4.41808351397, 7860.4193924392,
    0.00002342687, 6.13516237631, 3930.2096962196,
    0.00001273166, 2.03709655772, 529.6909650946,
    0.00001324292, 0.74246356352, 11506.7697697936,
    0.00000901855, 2.04505443513, 26.2983197998,
    0.00001199167, 1.10962944315, 1577.3435424478,
    0.00000857223, 3.50849156957, 398.1490034082,
    0.00000779786, 1.17882652114, 5223.6939198022,
    0.00000990250, 5.23268129594, 5884.9268465832,
    0.00000753141, 2.53339053818, 5507.5532386674,
    0.00000505264, 4.58292563052, 18849.2275499742,
    0.00000492379, 4.20506639861, 775.5226113240,
    0.00000356655, 2.91954116867, 0.0673103028,
    0.00000284125, 1.89869034186, 796.2980068164,
    0.00000242810, 0.34481140906, 5486.7778431750,
    0.00000317087, 5.84901952218, 11790.6290886588,
    0.00000271039, 0.31488607649, 10977.0788046990,
    0.00000206160, 4.80646606059, 2544.3144198834,
    0.00000205385, 1.86947813692, 5573.1428014331,
    0.00000202261, 2.45767795458, 6069.7767545534,
    0.00000126184, 1.08302630210, 20.7753954924,
    0.00000155516, 0.83306073807, 213.2990954380,
    0.00000115132, 0.64544911683, 0.9803210682,
    0.00000102851, 0.63599846727, 4694.0029547076,
    0.00000101724, 4.26679821365, 7.1135470008,
    0.00000099206, 6.20992940258, 2146.1654164752,
    0.00000132212, 3.41118275555, 2942.4634232916,
    0.00000097607, 0.68101272270, 155.4203994342,
    0.00000085128, 1.29870743025, 6275.9623029906,
    0.00000074651, 1.75508916159, 5088.6288397668,
    0.00000101895, 0.97569221824, 15720.8387848784,
    0.00000084711, 3.67080093025, 71430.6956181291,
    0.00000073547, 4.67926565481, 801.8209311238,
    0.00000073874, 3.50319443167, 3154.6870848956,
    0.00000078756, 3.03698313141, 12036.4607348882,
    0.00000079637, 1.80791330700, 17260.1546546904,
    0.00000085803, 5.98322631256, 161000.6857376741,
    0.00000056963, 2.78430398043, 6286.5989683404,
    0.00000061148, 1.81839811024, 7084.8967811152,
    0.00000069627, 0.83297596966, 9437.7629348870,
    0.00000056116, 4.38694880779, 14143.4952424306,
    0.00000062449, 3.97763880587, 8827.3902698748,
    0.00000051145, 0.28306864501, 5856.4776591154,
    0.00000055577, 3.47006009062, 6279.5527316424,
    0.00000041036, 5.36817351402, 8429.2412664666,
    0.00000051605, 1.33282746983, 1748.0164130670,
    0.00000051992, 0.18914945834, 12139.5535091068,
    0.00000049000, 0.48735065033, 1194.4470102246,
    0.00000039200, 6.16832995016, 10447.3878396044,
    0.00000035566, 1.77597314691, 6812.7668150860,
    0.00000036770, 6.04133859347, 10213.2855462110,
    0.00000036596, 2.56955238628, 1059.3819301892,
    0.00000033291, 0.59309499459, 17789.8456197850,
    0.00000035954, 1.70876111898, 2352.8661537718
]

E11 = [
    6283.31966747491, 0, 0,
    0.00206058863, 2.67823455584, 6283.0758499914,
    0.00004303430, 2.63512650414, 12566.1516999828,
    0.00000425264, 1.59046980729, 3.5231183490,
    0.00000108977, 2.96618001993, 1577.3435424478,
    0.00000093478, 2.59212835365, 18849.2275499742,
    0.00000119261, 5.79557487799, 26.2983197998,
    0.00000072122, 1.13846158196, 529.6909650946,
    0.00000067768, 1.87472304791, 398.1490034082,
    0.00000067327, 4.40918235168, 5507.5532386674,
    0.00000059027, 2.88797038460, 5223.6939198022,
    0.00000055976, 2.17471680261, 155.4203994342,
    0.00000045407, 0.39803079805, 796.2980068164,
    0.00000036369, 0.46624739835, 775.5226113240,
    0.00000028958, 2.64707383882, 7.1135470008,
    0.00000019097, 1.84628332577, 5486.7778431750,
    0.00000020844, 5.34138275149, 0.9803210682,
    0.00000018508, 4.96855124577, 213.2990954380,
    0.00000016233, 0.03216483047, 2544.3144198834,
    0.00000017293, 2.99116864949, 6275.9623029906
]

E12 = [
    0.00052918870, 0, 0,
    0.00008719837, 1.07209665242, 6283.0758499914,
    0.00000309125, 0.86728818832, 12566.1516999828,
    0.00000027339, 0.05297871691, 3.5231183490,
    0.00000016334, 5.18826691036, 26.2983197998,
    0.00000015752, 3.68457889430, 155.4203994342,
    0.00000009541, 0.75742297675, 18849.2275499742,
    0.00000008937, 2.05705419118, 77713.7714681205,
    0.00000006952, 0.82673305410, 775.5226113240,
    0.00000005064, 4.66284525271, 1577.3435424478
]

E13 = [
    0.00000289226, 5.84384198723, 6283.0758499914,
    0.00000034955, 0, 0,
    0.00000016819, 5.48766912348, 12566.1516999828
]

E14 = [
    0.00000114084, 3.14159265359, 0,
    0.00000007717, 4.13446589358, 6283.0758499914,
    0.00000000765, 3.83803776214, 12566.1516999828
]

E15 = [
    0.00000000878, 3.14159265359, 0
]


E20 = [
    0.00000279620, 3.19870156017, 84334.6615813083,
    0.00000101643, 5.42248619256, 5507.5532386674,
    0.00000080445, 3.88013204458, 5223.6939198022,
    0.00000043806, 3.70444689758, 8827.3902698748,
    0.00000031933, 4.00026369781, 5884.9268465832,
    0.00000022724, 3.98473831560, 1047.7473117547,
    0.00000016392, 3.56456119782, 5507.5532386674,
    0.00000018141, 4.98367470263, 6283.0758499914,
    0.00000014443, 3.70275614914, 9437.7629348870,
    0.00000014304, 3.41117857525, 10213.2855462110
]

E21 = [
    -0.00000227778, 3.41376620530, 6283.0758499914,
    0.00000003806, 3.37063423795, 12566.1516999828
]

def XL0_calc(planet_data, t, scaling_factor=10000000000):
    """
    计算行星坐标（与原始JS的XL0_calc一致）
    planet_data: JSON中对应行星的"parts"字典
    t: 儒略世纪 (JD-2451545)/36525
    scaling_factor: 缩放因子
    
    返回: [黄经(弧度), 黄纬(弧度), 距离(AU)]
    """
    t = t / 10  # 转为儒略千年数（与JS一致）
    results = [0.0, 0.0, 0.0]  # 对应 L, B, R
    dimensions = ['L', 'B', 'R']

    for i, dim in enumerate(dimensions):
        val = 0
        tn = 1  # t的幂次
        # 遍历 T^0 到 T^5
        for p in range(6):
            key = f"{dim}{p}"
            if key not in planet_data:
                tn *= t
                continue

            coeffs = planet_data[key]
            # 每 3 个数一组: A, B, C
            # 项值 = A * cos(B + C * t)
            term_sum = 0
            for j in range(0, len(coeffs), 3):
                A, B, C = coeffs[j], coeffs[j+1], coeffs[j+2]
                term_sum += A * math.cos(B + C * t)

            val += term_sum * tn
            tn *= t
        
        # 除以缩放因子，结果直接是弧度
        results[i] = val / scaling_factor
    
    return results


def earth_lon_lat_dist(t: float):
    """获取地球的黄经、黄纬和距离（使用完整VSOP87数据）"""
    coeffs = get_coeffs()
    vsop87_earth = coeffs['vsop87']['planets'][0]['data']['parts']
    scaling_factor = coeffs['vsop87']['planets'][0]['data'].get('scalingFactor', 10000000000)
    result = XL0_calc(vsop87_earth, t, scaling_factor)
    
    # 添加地球修正项（与JS版本一致）
    t_mill = t / 10  # 儒略千年
    t2 = t_mill * t_mill
    t3 = t2 * t_mill
    
    # 黄经修正
    result[0] += (-0.0728 - 2.7702 * t_mill - 1.1019 * t2 - 0.0996 * t3) / rad
    # 黄纬修正
    result[1] += (0.0000 + 0.0004 * t_mill + 0.0004 * t2 - 0.0026 * t3) / rad
    # 距离修正
    result[2] += (-0.0020 + 0.0044 * t_mill + 0.0213 * t2 - 0.0250 * t3) / 1000000
    
    return result


def E_Lon(t: float, n: int) -> float:
    """
    地球黄经计算（使用完整VSOP87数据）
    t: 儒略世纪数
    n: 精度控制（保留参数，目前使用全部精度）
    返回: 归一化到0-2π的黄经值
    """
    result = earth_lon_lat_dist(t)
    # 归一化到0-2π范围，与M_Lon保持一致
    return rad2mrad(result[0])


def S_aLon(t: float, n: int) -> float:
    """
    太阳视黄经计算（与JS版本一致，不归一化）
    t: 儒略世纪数
    n: 精度控制
    
    注意：返回值不归一化到0-2π，以与JS版本保持一致
    JS版本：return this.E_Lon(t,n) + nutationLon2(t) + gxc_sunLon(t) + Math.PI;
    JS的E_Lon也不归一化
    """
    # 获取地球黄经（不归一化）
    result = earth_lon_lat_dist(t)
    earth_lon = result[0]  # 不进行rad2mrad归一化
    
    # 太阳视黄经 = 地球黄经 + π + 章动 + 光行差
    return earth_lon + nutationLon2(t) + gxc_sunLon(t) + math.pi


def moon_lon_lat_dist(t: float):
    """
    使用ELP2000计算月球的黄经、黄纬和距离
    t: 儒略世纪 (JD-2451545)/36525
    """
    # Delaunay基础角参数（单位：弧度）
    # L' (月球经度)
    Lp = (2.355555727153 + 8328.691424623 * t) % (2 * math.pi)
    # D (月距角)
    D = (5.159794934986 + 7771.377146812 * t) % (2 * math.pi)
    # M (太阳偏近点角)
    M = (2.957564914689 + 628.3019551709 * t) % (2 * math.pi)
    # M' (月球偏近点角)
    Mp = (2.558530098485 + 8433.466158135 * t) % (2 * math.pi)
    # F (月球纬度参数)
    F = (1.282420720113 + 8399.684733870 * t) % (2 * math.pi)
    
    # 获取ELP2000系数数据
    elp2000_data = coefficients['elp2000']['data']
    longitude_coeffs = elp2000_data['longitude']
    latitude_coeffs = elp2000_data['latitude']
    distance_coeffs = elp2000_data['distance']
    
    # 计算月球黄经
    lon_sum = 0.0
    for term in longitude_coeffs:
        amplitude = term[0]
        phase = term[1]
        arg_l = term[2]  # L'系数
        arg_d = term[3]  # D系数
        arg_m = term[4]  # M系数
        arg_mp = term[5]  # M'系数
        arg_f = term[6]  # F系数
        
        # 计算角度参数
        arg = phase + arg_l*Lp + arg_d*D + arg_m*M + arg_mp*Mp + arg_f*F
        lon_sum += amplitude * math.sin(arg)
    
    # 计算月球黄纬
    lat_sum = 0.0
    for term in latitude_coeffs:
        amplitude = term[0]
        phase = term[1]
        arg_l = term[2]
        arg_d = term[3]
        arg_m = term[4]
        arg_mp = term[5]
        arg_f = term[6]
        
        arg = phase + arg_l*Lp + arg_d*D + arg_m*M + arg_mp*Mp + arg_f*F
        lat_sum += amplitude * math.sin(arg)
    
    # 计算月球距离（地心距离，单位：地球赤道半径）
    dist_sum = 0.0
    for term in distance_coeffs:
        amplitude = term[0]
        phase = term[1]
        arg_l = term[2]
        arg_d = term[3]
        arg_m = term[4]
        arg_mp = term[5]
        arg_f = term[6]
        
        arg = phase + arg_l*Lp + arg_d*D + arg_m*M + arg_mp*Mp + arg_f*F
        dist_sum += amplitude * math.cos(arg)
    
    # 转换为弧度（除以弧秒到弧度的转换因子）
    # 1弧度 = 206264.8062470964 角秒
    # 即 1角秒 = 1/206264.8062470964 弧度
    arcsec_to_rad = 206264.8062470964  # 180*3600/pi
    
    return [
        lon_sum / arcsec_to_rad,  # 月球黄经（弧度）
        lat_sum / arcsec_to_rad,  # 月球黄纬（弧度）
        dist_sum / arcsec_to_rad # 月球距离（弧度单位，后续可能需要转换为实际距离）
    ]

def M_Lon(t: float, n: int) -> float:
    """月球黄经 (使用ELP2000系数)"""
    moon_coords = moon_lon_lat_dist(t)
    return moon_coords[0]  # 返回黄经部分


# ==================== 坐标计算函数 ====================

def m_coord(t: float, n1: int, n2: int, n3: int) -> List[float]:
    """
    月亮坐标计算
    t: 儒略世纪 (JD-2451545)/36525
    n1, n2, n3: 精度控制参数（在ELP2000中暂时忽略，但保留接口兼容性）
    返回: [黄经, 黄纬, 距离]
    """
    # 使用ELP2000计算月球坐标
    coords = moon_lon_lat_dist(t)
    return [coords[0], coords[1], coords[2]]


def e_coord(t: float, n1: int, n2: int, n3: int) -> List[float]:
    """
    地球坐标计算
    t: 儒略世纪 (JD-2451545)/36525
    n1, n2, n3: 精度控制参数（在VSOP87中暂时忽略，但保留接口兼容性）
    返回: [黄经, 黄纬, 距离]
    """
    # 获取地球的黄经、黄纬和距离
    coords = earth_lon_lat_dist(t)
    # 返回地球轨道坐标
    return [coords[0], coords[1], coords[2]]


def p_coord(xt: int, t: float, n1: int, n2: int, n3: int) -> List[float]:
    """
    行星坐标计算
    xt: 行星编号 (0=地球, 1=水星, 2=金星, 3=火星, 4=木星, 5=土星, 6=天王星, 7=海王星, 8=冥王星)
    t: 儒略世纪 (JD-2451545)/36525
    n1, n2, n3: 精度控制参数
    返回: [黄经, 黄纬, 距离]
    """
    planets_data = coefficients['vsop87']['planets']
    
    if xt == 0:
        # 地球坐标（相对于太阳）
        coords = earth_lon_lat_dist(t)
        return [coords[0], coords[1], coords[2]]
    else:
        # 其他行星坐标
        # xt=1 是水星，对应 planets[0]；xt=8 是冥王星，对应 planets[7]
        planet_idx = xt - 1  # xt=1 对应 planets[0]（水星）
        
        # 确保索引在有效范围内
        if planet_idx >= len(planets_data):
            planet_idx = len(planets_data) - 1
        
        if planet_idx < 0:
            # 如果编号小于0，返回地球坐标
            coords = earth_lon_lat_dist(t)
            return [coords[0], coords[1], coords[2]]
        
        planet_data = planets_data[planet_idx]['data']['parts']
        coords = XL0_calc(planet_data, t)
        return [coords[0], coords[1], coords[2]]


# ==================== 太阳坐标类 ====================
class SunCoord:
    """太阳坐标计算类"""

    def __init__(self):
        self.Lon = 0  # 黄经
        self.Lat = 0  # 黄纬
        self.R = 0    # 距离
        self.rA = 0   # 赤经
        self.Dec = 0  # 赤纬

    def calc(self, jd: float) -> None:
        """计算太阳坐标,jd为儒略日"""


# ==================== XL类定义 ====================
class XL:
    """
    星历对象，提供统一的访问接口
    """
    @staticmethod
    def E_Lon(t: float, n: int) -> float:
        """
        地球黄经计算
        t: 儒略世纪数
        n: 精度控制
        """
        return E_Lon(t, n)
    
    @staticmethod
    def M_Lon(t: float, n: int) -> float:
        """
        月亮黄经计算
        t: 儒略世纪数
        n: 精度控制
        """
        return M_Lon(t, n)

# ==================== 太阳坐标类 ====================
class SunCoord:
    """太阳坐标计算类"""

    def __init__(self):
        self.Lon = 0  # 黄经
        self.Lat = 0  # 黄纬
        self.R = 0    # 距离
        self.rA = 0   # 赤经
        self.Dec = 0  # 赤纬

    def calc(self, jd: float) -> None:
        """计算太阳坐标,jd为儒略日"""
        T = (jd - J2000) / 36525

        # 计算黄经
        self.Lon = XL0_calc(0, 0, T, 50) + math.pi
        self.Lon += gxc_sunLon(T)  # 光行差
        self.Lon += nutationLon(T)  # 章动
        self.Lon = rad2mrad(self.Lon)

        # 黄纬
        self.Lat = -XL0_calc(0, 1, T, 50)

        # 距离(AU)
        self.R = 1.0  # 简化,实际需要计算

        # 转换为赤道坐标
        E = hcjj(T)
        z = llrConv([self.Lon, self.Lat, self.R], E)
        self.rA = z[0]
        self.Dec = z[1]


# ==================== 节气计算 ====================
def qi_accurate(W: float) -> float:
    """精确节气计算,W是节气编号(0=春分,1=清明...)"""
    t = S_aLon_t((W * 15 + 180) * math.pi / 180)
    return t * 36525 + J2000

def qi_accurate2(jd: float) -> float:
    """精确节气计算,返回jd附近的节气时刻"""
    T = (jd - J2000) / 36525
    lon = S_aLon(T, 10)
    lon = int(lon * 180 / math.pi / 15) * 15
    return qi_accurate(lon / 15)

def S_aLon_t(W: float) -> float:
    """已知太阳视黄经求时间"""
    v = 628.3319653318
    t = (W - 1.75347 - math.pi) / v
    # 使用E_v更新速度
    v = E_v(t)
    t += (W - S_aLon(t, 10)) / v
    v = E_v(t)
    t += (W - S_aLon(t, -1)) / v
    return t

def E_v(t: float) -> float:
    """地球速度,t是儒略世纪,误差小于万分之3"""
    f = 628.307585 * t
    return (628.332 + 21 * math.sin(1.527 + f) + 0.44 * math.sin(1.48 + f * 2)
            + 0.129 * math.sin(5.82 + f) * t + 0.00055 * math.sin(4.21 + f) * t * t)


def M_v(t: float) -> float:
    """月球速度计算,误差小于万分之5"""
    v = 8399.71 - 914 * math.sin(0.7848 + 8328.691425 * t + 0.0001523 * t * t)
    v -= (179 * math.sin(2.543 + 15542.7543 * t) +
          160 * math.sin(0.1874 + 7214.0629 * t) +
          62 * math.sin(3.14 + 16657.3828 * t) +
          34 * math.sin(4.827 + 16866.9323 * t) +
          22 * math.sin(4.9 + 23871.4457 * t) +
          12 * math.sin(2.59 + 14914.4523 * t) +
          7 * math.sin(0.23 + 6585.7609 * t) +
          5 * math.sin(0.9 + 25195.624 * t) +
          5 * math.sin(2.32 - 7700.3895 * t) +
          5 * math.sin(3.88 + 8956.9934 * t) +
          5 * math.sin(0.49 + 7771.3771 * t))
    return v

def S_aLon_t2(W: float) -> float:
    """已知太阳视黄经求时间(低精度)"""
    t = (W - 1.75347 - math.pi) / 628.3319653318
    return t

def qi_low(y: int, n: int) -> float:
    """低精度节气计算,y是年,n是节气序号(0=小寒)"""
    # 简化计算
    jd = JD(y, 1, 1)
    return jd + n * 15.2184


# ==================== 月相计算 ====================
def MS_aLon(t: float, Mn: int, Sn: int = None) -> float:
    """
    月日视黄经差的差值
    t: 儒略世纪数
    Mn: 月球精度
    Sn: 太阳精度(可选，默认与Mn相同)
    """
    if Sn is None:
        Sn = Mn
    return M_Lon(t, Mn) + gxc_moonLon(t) - (E_Lon(t, Sn) + gxc_sunLon(t) + math.pi)


def MS_aLon_t(W: float) -> float:
    """已知月日视黄经差求时间"""
    v = 7771.37714500204
    t = (W + 1.08472) / v
    # 将W归一化到与MS_aLon返回值相同的范围
    W_norm = rad2mrad(W)
    
    ms = MS_aLon(t, 3, 3)
    diff = W_norm - ms
    # 处理周期边界
    if diff > math.pi:
        diff -= 2 * math.pi
    elif diff < -math.pi:
        diff += 2 * math.pi
    t += diff / v
    
    v = M_v(t) - E_v(t)  # 更新速度
    
    ms = MS_aLon(t, 20, 10)
    diff = W_norm - ms
    if diff > math.pi:
        diff -= 2 * math.pi
    elif diff < -math.pi:
        diff += 2 * math.pi
    t += diff / v
    
    ms = MS_aLon(t, -1, 60)
    diff = W_norm - ms
    if diff > math.pi:
        diff -= 2 * math.pi
    elif diff < -math.pi:
        diff += 2 * math.pi
    t += diff / v
    
    return t


def MS_aLon_t2(W: float) -> float:
    """已知月日视黄经差求时间(低精度,误差约10分钟)"""
    v = 7771.37714500204
    t = (W + 1.08472) / v
    t2 = t * t
    
    # 修正项（简化版本，不依赖M_Lon）
    t -= (-0.00003309 * t2 +
          0.10976 * math.cos(0.784758 + 8328.6914246 * t + 0.000152292 * t2) +
          0.02224 * math.cos(0.18740 + 7214.0628654 * t - 0.00021848 * t2) -
          0.03342 * math.cos(4.669257 + 628.307585 * t)) / v
    
    return t

def so_accurate(W: float) -> float:
    """精确朔望计算,W是月相(0=朔,1=上弦,2=望,3=下弦)"""
    t = MS_aLon_t(W * math.pi / 2)
    return t * 36525 + J2000

def so_accurate2(jd: float) -> float:
    """精确朔望计算,返回jd附近的朔望时刻"""
    T = (jd - J2000) / 36525
    v = MS_aLon(T, 10)
    v = int(v * 2 / math.pi + 0.5) * math.pi / 2
    return so_accurate(v * 2 / math.pi)

def so_low(y: int, m: int) -> float:
    """低精度朔日计算"""
    # 简化计算
    jd = JD(y, m, 1)
    return jd


# ==================== 日出日落计算 ====================
def sunRise(jd: float, L: float, fa: float, sj: int) -> float:
    """
    日出日落计算
    jd: 儒略日
    L: 经度(弧度,东正西负)
    fa: 纬度(弧度,北正南负)
    sj: 0=日出,1=日落
    """
    T = (jd - J2000) / 36525

    # 太阳赤纬
    sun = SunCoord()
    sun.calc(jd)
    dec = sun.Dec

    # 时角
    h0 = -0.8333 * math.pi / 180  # 日出日落时太阳高度角
    cosH = (sin(h0) - sin(fa) * sin(dec)) / (cos(fa) * cos(dec))

    if cosH > 1:
        return -1  # 极夜
    if cosH < -1:
        return -2  # 极昼

    H = acos(cosH)
    if sj == 0:
        H = -H  # 日出

    # 计算时刻
    gst = pGST2(jd)
    t = (H + sun.rA - gst - L) / (2 * math.pi)
    t = t - floor(t)
    if t > 0.5:
        t -= 1

    return jd + t

def sunRiseSet(jd: float, L: float, fa: float) -> List[float]:
    """计算日出日落时刻,返回[日出,日落]"""
    rise = sunRise(jd, L, fa, 0)
    set_time = sunRise(jd, L, fa, 1)
    return [rise, set_time]


# ==================== 月出月落计算 ====================
def moonRise(jd: float, L: float, fa: float, sj: int) -> float:
    """
    月出月落计算(简化版)
    jd: 儒略日
    L: 经度(弧度)
    fa: 纬度(弧度)
    sj: 0=月出,1=月落
    """
    # 简化计算,实际需要迭代
    T = (jd - J2000) / 36525

    # 月球赤纬(简化)
    dec = 0.4 * sin(M_Lon(T, 10))  # 简化

    h0 = 0.125 * math.pi / 180  # 月出月落时月球高度角
    cosH = (sin(h0) - sin(fa) * sin(dec)) / (cos(fa) * cos(dec))

    if abs(cosH) > 1:
        return -1

    H = acos(cosH)
    if sj == 0:
        H = -H

    return jd + H / (2 * math.pi)



# ==================== 工具函数 ====================
def timeStr(jd: float) -> str:
    """儒略日转时间字符串"""
    d = DD(jd)
    h = (jd + 0.5 - int(jd + 0.5)) * 24
    m = (h - int(h)) * 60
    s = (m - int(m)) * 60
    return f"{d[0]}-{d[1]:02d}-{d[2]:02d} {int(h):02d}:{int(m):02d}:{int(s):02d}"

def JD2str(jd: float, tz: float = 8) -> str:
    """儒略日转字符串(带时区)"""
    jd += tz / 24
    return timeStr(jd)

def jdOfNow() -> float:
    """当前时刻的儒略日"""
    import datetime
    now = datetime.datetime.now()
    return JD(now.year, now.month, now.day + now.hour / 24 + now.minute / 1440 + now.second / 86400)


# ==================== 星座计算 ====================
xzName = ['白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手', '摩羯', '水瓶', '双鱼']

def getXZ(jd: float) -> str:
    """根据儒略日获取星座"""
    T = (jd - J2000) / 36525
    lon = S_aLon(T, 10)
    idx = int(lon * 180 / math.pi / 30) % 12
    return xzName[idx]


# ==================== 二十八宿 ====================
xiu28Name = ['角', '亢', '氐', '房', '心', '尾', '箕', '斗', '牛', '女', '虚', '危', '室', '壁',
             '奎', '娄', '胃', '昴', '毕', '觜', '参', '井', '鬼', '柳', '星', '张', '翼', '轸']

def getXiu28(jd: float) -> str:
    """根据儒略日获取二十八宿"""
    # 简化计算
    idx = int(jd + 0.5) % 28
    return xiu28Name[idx]


# ==================== 节气名称 ====================
jqName = ['春分', '清明', '谷雨', '立夏', '小满', '芒种',
          '夏至', '小暑', '大暑', '立秋', '处暑', '白露',
          '秋分', '寒露', '霜降', '立冬', '小雪', '大雪',
          '冬至', '小寒', '大寒', '立春', '雨水', '惊蛰']

jqName2 = ['小寒', '大寒', '立春', '雨水', '惊蛰', '春分',
           '清明', '谷雨', '立夏', '小满', '芒种', '夏至',
           '小暑', '大暑', '立秋', '处暑', '白露', '秋分',
           '寒露', '霜降', '立冬', '小雪', '大雪', '冬至']


# ==================== 干支计算 ====================
Gan = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
Zhi = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']
ShX = ['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪']

def getGZ(n: int) -> str:
    """获取干支"""
    return Gan[n % 10] + Zhi[n % 12]

def getShX(n: int) -> str:
    """获取生肖"""
    return ShX[n % 12]


# ==================== 模块导出 ====================
__all__ = [
    # 常数
    'cs_rEar', 'cs_rEarA', 'cs_ba', 'cs_ba2', 'cs_AU', 'cs_sinP', 'cs_PI',
    'cs_GS', 'cs_Agx', 'cs_xxHH', 'xxName',
    'rad', 'radd', 'pi2', 'pi_2', 'J2000',
    'cs_k', 'cs_k2', 'cs_k0', 'cs_sMoon', 'cs_sMoon2', 'cs_sSun',

    # 数学函数
    'int2', 'mod2', 'sqrt', 'floor', 'sin', 'cos', 'tan',
    'asin', 'acos', 'atan', 'atan2',

    # 角度转换
    'rad2strE', 'rad2str', 'rad2str2', 'm2fm', 'str2rad',
    'rad2mrad', 'rad2rrad',

    # 坐标转换
    'llr2xyz', 'xyz2llr', 'llrConv', 'CD2DP', 'j1_j2', 'h2g', 'shiChaJ',

    # 时间计算
    'dt_calc', 'dt_T', 'JD', 'DD', 'DD0', 'Y_M', 'toJD',

    # 岁差章动
    'prece', 'hcjj', 'hcjj1', 'nutation', 'nutationLon', 'nutationLon2',
    'gxc_sunLon', 'gxc_moonLon', 'addPrece',

    # 恒星时
    'pGST', 'pGST2',

    # 太阳计算
    'XL0_calc', 'sunLon', 'sunLon2', 'S_aLon', 'E_Lon', 'M_Lon', 'SunCoord',

    # 节气月相
    'qi_accurate', 'qi_accurate2', 'S_aLon_t', 'S_aLon_t2', 'qi_low',
    'MS_aLon', 'MS_aLon_t', 'MS_aLon_t2', 'so_accurate', 'so_accurate2', 'so_low',

    # 日出日落
    'sunRise', 'sunRiseSet', 'moonRise',

    # 工具函数
    'timeStr', 'JD2str', 'jdOfNow',

    # 星座二十八宿
    'xzName', 'getXZ', 'xiu28Name', 'getXiu28',

    # 节气名称
    'jqName', 'jqName2',

    # 干支
    'Gan', 'Zhi', 'ShX', 'getGZ', 'getShX',
]


# ==================== 测试代码 ====================
if __name__ == '__main__':
    # 测试儒略日计算
    jd = JD(2024, 1, 1)
    print(f"2024-1-1 的儒略日: {jd}")

    # 测试日期转换
    d = DD(jd)
    print(f"儒略日 {jd} 对应日期: {d}")

    # 测试太阳黄经
    T = (jd - J2000) / 36525
    lon = S_aLon(T, 10)
    print(f"太阳黄经: {lon * 180 / math.pi:.2f}°")

    # 测试干支
    print(f"干支: {getGZ(0)} {getGZ(1)} {getGZ(60)}")

    print("eph0.py 模块测试完成!")