"""
日主旺衰判定模块

通过三个维度判断日主旺衰：得令、得地、得势
综合评分判定身旺/身偏旺/身偏弱/身弱
"""

from typing import Dict

# ==================== 五行常量 ====================

WUXING_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}  # 我生
WUXING_SHENG_BY = {"木": "水", "火": "木", "土": "火", "金": "土", "水": "金"}  # 生我
WUXING_KE = {"木": "土", "火": "金", "土": "水", "金": "木", "水": "火"}  # 我克
WUXING_KE_BY = {"木": "金", "火": "水", "土": "木", "金": "火", "水": "土"}  # 克我

TIANGAN_WUXING = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"
}

DIZHI_WUXING = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土",
    "巳": "火", "午": "火", "未": "土", "申": "金", "酉": "金",
    "戌": "土", "亥": "水"
}

SHISHEN_CATEGORY = {
    "比肩": "生扶", "劫财": "生扶",
    "正印": "生扶", "偏印": "生扶",
    "正财": "克泄耗", "偏财": "克泄耗",
    "食神": "克泄耗", "伤官": "克泄耗",
    "正官": "克泄耗", "七杀": "克泄耗"
}


# ==================== 得令判断 ====================

def _calc_de_ling(day_tian: str, month_di: str) -> Dict:
    """
    得令：月令地支的五行与日主五行的生克关系

    - 月令五行 == 日主五行 或 月令五行生日主五行 → 得令（+3分）
    - 月令五行被日主五行所克 → 中平（+1分）
    - 其他 → 失令（-1分）
    """
    day_wuxing = TIANGAN_WUXING[day_tian]
    month_wuxing = DIZHI_WUXING[month_di]

    if month_wuxing == day_wuxing:
        # 月令五行与日主五行相同
        score = 3
        detail = "得令"
        description = f"月令{month_di}{month_wuxing}，与日主{day_tian}{day_wuxing}同类，日主得令"
    elif WUXING_SHENG[month_wuxing] == day_wuxing:
        # 月令五行生日主五行
        score = 3
        detail = "得令"
        description = f"月令{month_di}{month_wuxing}，{month_wuxing}生{day_wuxing}，日主{day_tian}{day_wuxing}得令"
    elif WUXING_KE[day_wuxing] == month_wuxing:
        # 月令五行被日主五行所克
        score = 1
        detail = "中平"
        description = f"月令{month_di}{month_wuxing}，被日主{day_tian}{day_wuxing}所克，中平"
    else:
        # 其他情况：月令克日主或日主生月令
        score = -1
        detail = "失令"
        if WUXING_KE_BY[day_wuxing] == month_wuxing:
            description = f"月令{month_di}{month_wuxing}克日主{day_tian}{day_wuxing}，日主失令"
        elif WUXING_SHENG[day_wuxing] == month_wuxing:
            description = f"月令{month_di}{month_wuxing}为日主{day_tian}{day_wuxing}所生，日主失令"
        else:
            description = f"月令{month_di}{month_wuxing}，日主{day_tian}{day_wuxing}失令"

    return {"score": score, "detail": detail, "description": description}


# ==================== 得地判断 ====================

def _calc_de_di(day_tian: str, day_di: str, canggan: Dict) -> Dict:
    """
    得地：日支藏干中是否有日主同类五行（比肩/劫财）

    - 日支本气藏干 == 日主天干 → 得地（+2分）
    - 日支中气/余气藏干 == 日主天干 → 半得地（+1分）
    - 日支五行生日主五行 → 有根（+1分）
    - 其他 → 失地（-1分）
    """
    day_wuxing = TIANGAN_WUXING[day_tian]
    day_di_wuxing = DIZHI_WUXING[day_di]

    canggan_list = canggan.get(day_di, [])

    # 检查本气藏干是否与日主天干相同
    if len(canggan_list) > 0 and canggan_list[0] == day_tian:
        score = 2
        detail = "得地"
        description = f"日支{day_di}本气藏干{canggan_list[0]}与日主{day_tian}相同，日主得地"
        return {"score": score, "detail": detail, "description": description}

    # 检查中气/余气藏干是否与日主天干相同
    if len(canggan_list) > 1 and day_tian in canggan_list[1:]:
        score = 1
        detail = "半得地"
        idx = canggan_list.index(day_tian)
        position = "中气" if idx == 1 else "余气"
        description = f"日支{day_di}{position}藏干{day_tian}与日主相同，日主半得地"
        return {"score": score, "detail": detail, "description": description}

    # 检查日支五行是否生日主五行
    if WUXING_SHENG[day_di_wuxing] == day_wuxing:
        score = 1
        detail = "有根"
        description = f"日支{day_di}{day_di_wuxing}生日主{day_tian}{day_wuxing}，日主有根"
        return {"score": score, "detail": detail, "description": description}

    # 其他情况
    score = -1
    detail = "失地"
    canggan_str = "、".join(canggan_list) if canggan_list else "无"
    description = f"日支{day_di}藏干{canggan_str}，无日主{day_tian}同类，日主失地"
    return {"score": score, "detail": detail, "description": description}


# ==================== 得势判断 ====================

def _calc_de_shi(day_tian: str, pillars: Dict, shishen: Dict) -> Dict:
    """
    得势：全局五行力量对比

    统计四柱天干+地支本气藏干中，生扶日主的五行数量 vs 克泄耗日主的五行数量：
    - 生扶多 → 得势（+2分）
    - 克泄耗多 → 失势（-2分）
    - 相当 → 中平（0分）
    """
    shengfu_count = 0
    kexie_count = 0

    # 遍历四柱
    for pillar_key in ["year", "month", "day", "hour"]:
        pillar = pillars.get(pillar_key, {})
        tian_gan = pillar.get("tian", "")
        di_zhi = pillar.get("di", "")

        # 天干的十神
        if tian_gan:
            ss = shishen.get(tian_gan, "")
            if ss in SHISHEN_CATEGORY:
                if SHISHEN_CATEGORY[ss] == "生扶":
                    shengfu_count += 1
                else:
                    kexie_count += 1

        # 地支本气藏干的十神（取第一个藏干即本气）
        if di_zhi:
            # 从shishen中查找地支藏干的十神
            # shishen的key是天干，需要通过藏干来查找
            # 这里需要从外部获取藏干信息，但为了接口一致性，
            # 我们通过shishen字典中是否包含藏干天干来判断
            # 实际上shishen可能只包含天干的十神关系
            # 我们需要用另一种方式：通过cangan获取藏干，再计算十神
            pass

    # 由于shishen字典的key是天干，我们需要另外处理地支藏干
    # 这里我们通过直接计算五行生克关系来补充地支本气的判断
    day_wuxing = TIANGAN_WUXING[day_tian]

    for pillar_key in ["year", "month", "day", "hour"]:
        pillar = pillars.get(pillar_key, {})
        di_zhi = pillar.get("di", "")
        if di_zhi:
            di_wuxing = DIZHI_WUXING[di_zhi]
            # 判断地支五行与日主五行的关系
            if di_wuxing == day_wuxing:
                # 同类 → 比肩 → 生扶
                shengfu_count += 1
            elif WUXING_SHENG_BY[day_wuxing] == di_wuxing:
                # 生我 → 印星 → 生扶
                shengfu_count += 1
            elif WUXING_KE_BY[day_wuxing] == di_wuxing:
                # 克我 → 官杀 → 克泄耗
                kexie_count += 1
            elif WUXING_SHENG[day_wuxing] == di_wuxing:
                # 我生 → 食伤 → 克泄耗
                kexie_count += 1
            elif WUXING_KE[day_wuxing] == di_wuxing:
                # 我克 → 财星 → 克泄耗
                kexie_count += 1

    # 判断得势
    if shengfu_count > kexie_count:
        score = 2
        detail = "得势"
        description = f"全局生扶{shengfu_count}个、克泄耗{kexie_count}个，生扶日主之力较强"
    elif shengfu_count < kexie_count:
        score = -2
        detail = "失势"
        description = f"全局生扶{shengfu_count}个、克泄耗{kexie_count}个，克泄耗日主之力较强"
    else:
        score = 0
        detail = "中平"
        description = f"全局生扶{shengfu_count}个、克泄耗{kexie_count}个，力量相当"

    return {"score": score, "detail": detail, "description": description}


# ==================== 综合旺衰判定 ====================

def calculate_wangshuai(day_tian: str, month_di: str, day_di: str,
                        pillars: Dict, canggan: Dict, shishen: Dict) -> Dict:
    """
    日主旺衰综合判定

    参数:
        day_tian: 日主天干（如 "甲"）
        month_di: 月令地支（如 "寅"）
        day_di: 日支地支（如 "子"）
        pillars: 四柱数据，格式如 {"year": {"tian": "甲", "di": "子"}, ...}
        canggan: 地支藏干数据，格式如 {"子": ["癸"], "丑": ["己", "辛", "癸"], ...}
        shishen: 十神数据，格式如 {"甲": "比肩", "丙": "正官", ...}

    返回:
        {
            "de_ling": {"score": 3, "detail": "得令", "description": "..."},
            "de_di": {"score": 1, "detail": "半得地", "description": "..."},
            "de_shi": {"score": 2, "detail": "得势", "description": "..."},
            "total_score": 6,
            "conclusion": "身旺",
            "description": "日主乙木得令得势，综合判定为身旺"
        }
    """
    # 计算三个维度
    de_ling = _calc_de_ling(day_tian, month_di)
    de_di = _calc_de_di(day_tian, day_di, canggan)
    de_shi = _calc_de_shi(day_tian, pillars, shishen)

    # 综合评分
    total_score = de_ling["score"] + de_di["score"] + de_shi["score"]

    # 判定结论
    day_wuxing = TIANGAN_WUXING[day_tian]
    if total_score >= 4:
        conclusion = "身旺"
    elif total_score >= 1:
        conclusion = "身偏旺"
    elif total_score >= -1:
        conclusion = "身偏弱"
    else:
        conclusion = "身弱"

    # 生成综合描述
    parts = []
    if de_ling["score"] > 0:
        parts.append(f"{de_ling['detail']}")
    if de_di["score"] > 0:
        parts.append(f"{de_di['detail']}")
    if de_shi["score"] > 0:
        parts.append(f"{de_shi['detail']}")

    if parts:
        advantage = "、".join(parts)
        description = f"日主{day_tian}{day_wuxing}{advantage}，综合判定为{conclusion}"
    else:
        description = f"日主{day_tian}{day_wuxing}不得令不得地不得势，综合判定为{conclusion}"

    return {
        "de_ling": de_ling,
        "de_di": de_di,
        "de_shi": de_shi,
        "total_score": total_score,
        "conclusion": conclusion,
        "description": description
    }