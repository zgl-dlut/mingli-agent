"""
日主旺衰判定模块

通过四个维度判断日主旺衰：得令、得地、得势、得局
- 得令：月令对日主的影响
- 得地：日支藏干对日主的支撑
- 得势：全局五行力量对比
- 得局：地支合局（三会/三合/六合）对日主的影响（新增）

综合评分判定身旺/身偏旺/身偏弱/身弱
"""

from typing import Dict, List, Set, Tuple

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

# ==================== 合局常量 ====================

# 三会局：力量最强，必须三支齐全，无半会
SAN_HUI: Dict[str, Set[str]] = {
    "木": {"寅", "卯", "辰"},
    "火": {"巳", "午", "未"},
    "金": {"申", "酉", "戌"},
    "水": {"亥", "子", "丑"},
}

# 三合局：长生+帝旺+墓库
SAN_HE: Dict[str, Set[str]] = {
    "水": {"申", "子", "辰"},
    "火": {"寅", "午", "戌"},
    "金": {"巳", "酉", "丑"},
    "木": {"亥", "卯", "未"},
}

# 三合中神（帝旺位）
SAN_HE_ZHONG_SHEN: Set[str] = {"子", "午", "卯", "酉"}

# 六合
LIU_HE: Set[frozenset] = {
    frozenset(["子", "丑"]), frozenset(["寅", "亥"]), frozenset(["卯", "戌"]),
    frozenset(["辰", "酉"]), frozenset(["巳", "申"]), frozenset(["午", "未"]),
}

# 六合化气
LIU_HE_HUA: Dict[str, str] = {
    "子丑": "土", "寅亥": "木", "卯戌": "火",
    "辰酉": "金", "巳申": "水", "午未": "火",
}

# 六冲
LIU_CHONG: Set[frozenset] = {
    frozenset(["子", "午"]), frozenset(["丑", "未"]), frozenset(["寅", "申"]),
    frozenset(["卯", "酉"]), frozenset(["辰", "戌"]), frozenset(["巳", "亥"]),
}

# 三刑
SAN_XING: List[Set[str]] = [
    {"寅", "巳", "申"},  # 无恩之刑
    {"丑", "戌", "未"},  # 恃势之刑
]
# 二支刑（含自刑）
ER_ZHI_XING: Set[frozenset] = {
    frozenset(["子", "卯"]),  # 无礼之刑
}
ZI_XING: Set[str] = {"辰", "午", "酉", "亥"}  # 自刑

# 六害
LIU_HAI: Set[frozenset] = {
    frozenset(["子", "未"]), frozenset(["丑", "午"]), frozenset(["寅", "巳"]),
    frozenset(["卯", "辰"]), frozenset(["申", "亥"]), frozenset(["酉", "戌"]),
}

# 六破
LIU_PO: Set[frozenset] = {
    frozenset(["子", "酉"]), frozenset(["丑", "辰"]), frozenset(["寅", "亥"]),
    frozenset(["卯", "午"]), frozenset(["巳", "申"]), frozenset(["未", "戌"]),
}

# 合局权重
JU_WEIGHT = {
    "三会": 5,   # 最强
    "三合": 4,   # 强
    "半三合": 2,  # 中
    "六合": 2,   # 中
}

# 刑冲削弱权重
XINGCHONG_WEIGHT = {
    "六冲": -2,
    "三刑": -2,
    "二支刑": -1,
    "自刑": -1,
    "六害": -1,
    "六破": -1,
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
        score = 3
        detail = "得令"
        description = f"月令{month_di}{month_wuxing}，与日主{day_tian}{day_wuxing}同类，日主得令"
    elif WUXING_SHENG[month_wuxing] == day_wuxing:
        score = 3
        detail = "得令"
        description = f"月令{month_di}{month_wuxing}，{month_wuxing}生{day_wuxing}，日主{day_tian}{day_wuxing}得令"
    elif WUXING_KE[day_wuxing] == month_wuxing:
        score = 1
        detail = "中平"
        description = f"月令{month_di}{month_wuxing}，被日主{day_tian}{day_wuxing}所克，中平"
    else:
        score = -1
        detail = "失令"
        if WUXING_KE_BY[day_wuxing] == month_wuxing:
            description = f"月令{month_di}{month_wuxing}克日主{day_tian}{day_wuxing}，日主失令"
        elif WUXING_SHENG[day_wuxing] == month_wuxing:
            description = f"月令{month_di}{month_wuxing}为日主{day_tian}{day_wuxing}所生，日主失令"
        else:
            description = f"月令{month_di}{month_wuxing}，日主{day_tian}{day_wuxing}失令"

    return {"score": score, "detail": detail, "description": description}


# ==================== 长生十二宫常量 ====================

# 阳干顺行，阴干逆行
CHANGSHENG_MAP: Dict[str, Dict[str, str]] = {
    # 阳干
    "甲": {"亥": "长生", "子": "沐浴", "丑": "冠带", "寅": "临官", "卯": "帝旺",
           "辰": "衰", "巳": "病", "午": "死", "未": "墓", "申": "绝", "酉": "胎", "戌": "养"},
    "丙": {"寅": "长生", "卯": "沐浴", "辰": "冠带", "巳": "临官", "午": "帝旺",
           "未": "衰", "申": "病", "酉": "死", "戌": "墓", "亥": "绝", "子": "胎", "丑": "养"},
    "戊": {"寅": "长生", "卯": "沐浴", "辰": "冠带", "巳": "临官", "午": "帝旺",
           "未": "衰", "申": "病", "酉": "死", "戌": "墓", "亥": "绝", "子": "胎", "丑": "养"},
    "庚": {"巳": "长生", "午": "沐浴", "未": "冠带", "申": "临官", "酉": "帝旺",
           "戌": "衰", "亥": "病", "子": "死", "丑": "墓", "寅": "绝", "卯": "胎", "辰": "养"},
    "壬": {"申": "长生", "酉": "沐浴", "戌": "冠带", "亥": "临官", "子": "帝旺",
           "丑": "衰", "寅": "病", "卯": "死", "辰": "墓", "巳": "绝", "午": "胎", "未": "养"},
    # 阴干（逆行）
    "乙": {"午": "长生", "巳": "沐浴", "辰": "冠带", "卯": "临官", "寅": "帝旺",
           "丑": "衰", "子": "病", "亥": "死", "戌": "墓", "酉": "绝", "申": "胎", "未": "养"},
    "丁": {"酉": "长生", "申": "沐浴", "未": "冠带", "午": "临官", "巳": "帝旺",
           "辰": "衰", "卯": "病", "寅": "死", "丑": "墓", "子": "绝", "亥": "胎", "戌": "养"},
    "己": {"酉": "长生", "申": "沐浴", "未": "冠带", "午": "临官", "巳": "帝旺",
           "辰": "衰", "卯": "病", "寅": "死", "丑": "墓", "子": "绝", "亥": "胎", "戌": "养"},
    "辛": {"子": "长生", "亥": "沐浴", "戌": "冠带", "酉": "临官", "申": "帝旺",
           "未": "衰", "午": "病", "巳": "死", "辰": "墓", "卯": "绝", "寅": "胎", "丑": "养"},
    "癸": {"卯": "长生", "寅": "沐浴", "丑": "冠带", "子": "临官", "亥": "帝旺",
           "戌": "衰", "酉": "病", "申": "死", "未": "墓", "午": "绝", "巳": "胎", "辰": "养"},
}

# 长生十二宫 → 得地分数
CHANGSHENG_SCORE: Dict[str, int] = {
    "长生": 2,   # 强根，日主在此地支获得生命力
    "临官": 2,   # 禄位，日主得禄，强力支撑
    "帝旺": 3,   # 最强根，日主在此地支达到巅峰
    "冠带": 1,   # 中等支撑
    "养":   1,   # 孕育中，有中等支撑
    "墓":   0,   # 入库，力量被封存
    "胎":   0,   # 初成形，力量很弱
    "沐浴": -1,  # 桃花位，日主在此不稳定
    "衰":   -1,  # 开始衰退
    "病":   -2,  # 虚弱
    "死":   -2,  # 无气
    "绝":   -2,  # 最弱
}


# ==================== 得地判断（长生十二宫） ====================

def _calc_de_di(day_tian: str, day_di: str, canggan: Dict) -> Dict:
    """
    得地：基于长生十二宫判断日支对日主的支撑力

    长生十二宫描述了日主天干在各地支的生命周期状态，
    比单纯看藏干更准确地反映日主的根气强弱。

    评分规则：
    - 帝旺 → +3（最强根）
    - 长生/临官 → +2（强根/禄位）
    - 冠带/养 → +1（中等支撑）
    - 墓/胎 → 0（入库/初成形）
    - 沐浴/衰 → -1（不稳定/衰退）
    - 病/死/绝 → -2（虚弱/无气）
    """
    day_wuxing = TIANGAN_WUXING[day_tian]

    # 获取长生十二宫位置
    stage = CHANGSHENG_MAP.get(day_tian, {}).get(day_di, "绝")
    score = CHANGSHENG_SCORE.get(stage, -2)

    # 生成描述
    if score >= 2:
        detail = "得地"
        description = f"日主{day_tian}在日支{day_di}为{stage}位，根气强旺，日主得地"
    elif score >= 1:
        detail = "有根"
        description = f"日主{day_tian}在日支{day_di}为{stage}位，有根气支撑"
    elif score >= 0:
        detail = "根弱"
        description = f"日主{day_tian}在日支{day_di}为{stage}位，根气微弱"
    else:
        detail = "失地"
        description = f"日主{day_tian}在日支{day_di}为{stage}位，根气不足，日主失地"

    return {
        "score": score,
        "detail": detail,
        "description": description,
        "changsheng_stage": stage,
    }


# ==================== 得势判断 ====================

def _calc_de_shi(day_tian: str, pillars: Dict, shishen: Dict,
                 he_branches: Set[str] = None) -> Dict:
    """
    得势：全局五行力量对比

    统计四柱天干+地支中，生扶日主的五行数量 vs 克泄耗日主的五行数量。
    参与合局的地支不计入得势（避免与得局重复计算）。

    - 生扶多 → 得势（+2分）
    - 克泄耗多 → 失势（-2分）
    - 相当 → 中平（0分）
    """
    if he_branches is None:
        he_branches = set()

    shengfu_count = 0
    kexie_count = 0
    day_wuxing = TIANGAN_WUXING[day_tian]

    # 四柱位置（兼容英文key和中文key）
    pillar_positions = ["year", "month", "day", "hour", "年", "月", "日", "时"]

    for pos in pillar_positions:
        pillar = pillars.get(pos, {})
        if not pillar:
            continue
        tian_gan = pillar.get("tian", "")
        di_zhi = pillar.get("di", "")

        # 天干：通过五行关系判断
        if tian_gan:
            tian_wuxing = TIANGAN_WUXING.get(tian_gan, "")
            if tian_wuxing:
                if tian_wuxing == day_wuxing:
                    shengfu_count += 1
                elif WUXING_SHENG_BY[day_wuxing] == tian_wuxing:
                    shengfu_count += 1
                else:
                    kexie_count += 1

        # 地支：跳过参与合局的地支（合局力量由得局维度单独计算）
        if di_zhi and di_zhi not in he_branches:
            di_wuxing = DIZHI_WUXING.get(di_zhi, "")
            if di_wuxing:
                if di_wuxing == day_wuxing:
                    shengfu_count += 1
                elif WUXING_SHENG_BY[day_wuxing] == di_wuxing:
                    shengfu_count += 1
                elif WUXING_KE_BY[day_wuxing] == di_wuxing:
                    kexie_count += 1
                elif WUXING_SHENG[day_wuxing] == di_wuxing:
                    kexie_count += 1
                elif WUXING_KE[day_wuxing] == di_wuxing:
                    kexie_count += 1

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


# ==================== 得局判断（新增） ====================

def _get_he_branches(pillars: Dict) -> Tuple[Set[str], List[Dict]]:
    """
    检测四柱地支中的合局（三会/三合），返回参与合局的地支集合和合局详情。

    优先级：三会 > 三合（同一地支不同时参与两种合局）。
    """
    # 兼容英文key和中文key
    pillar_positions = ["year", "month", "day", "hour", "年", "月", "日", "时"]
    dz_list = []
    seen = set()
    for pos in pillar_positions:
        pillar = pillars.get(pos, {})
        if not pillar:
            continue
        di = pillar.get("di", "")
        if di and di not in seen:
            dz_list.append(di)
            seen.add(di)

    dz_set = set(dz_list)
    he_branches: Set[str] = set()
    he_details: List[Dict] = []

    # 1. 检测三会局（优先级最高）
    for wuxing, members in SAN_HUI.items():
        if members <= dz_set:
            he_branches.update(members)
            he_details.append({
                "type": "三会",
                "wuxing": wuxing,
                "branches": sorted(members, key=lambda x: dz_list.index(x) if x in dz_list else 99),
            })

    # 2. 检测三合局（排除已被三会占用的地支）
    remaining = dz_set - he_branches
    for wuxing, members in SAN_HE.items():
        overlap = members & remaining
        if len(overlap) == 3:
            he_branches.update(overlap)
            he_details.append({
                "type": "三合",
                "wuxing": wuxing,
                "branches": sorted(overlap, key=lambda x: dz_list.index(x) if x in dz_list else 99),
            })
        elif len(overlap) == 2:
            # 半三合：需带中神（帝旺位）才有意义
            if overlap & SAN_HE_ZHONG_SHEN:
                he_branches.update(overlap)
                he_details.append({
                    "type": "半三合",
                    "wuxing": wuxing,
                    "branches": sorted(overlap, key=lambda x: dz_list.index(x) if x in dz_list else 99),
                })

    return he_branches, he_details


def _calc_de_ju(day_tian: str, pillars: Dict, month_di: str) -> Dict:
    """
    得局：地支合局与刑冲对日主旺衰的影响（新增第四维度）

    合局会改变地支的五行属性，对日主产生强力生扶或克泄。
    刑冲会削弱地支力量。

    权重：三会(+5) > 三合(+4) > 半三合/六合(+2)
    刑冲削弱：六冲(-2) > 三刑(-2) > 六害/六破(-1)

    规则：参与合局的地支不再单独计算刑冲（合局力量已包含整体效应）。
    """
    day_wuxing = TIANGAN_WUXING[day_tian]

    # 获取合局地支
    he_branches, he_details = _get_he_branches(pillars)

    score = 0
    ju_descriptions = []

    # 计算合局对日主的影响
    for he in he_details:
        he_wuxing = he["wuxing"]
        he_type = he["type"]
        branches_str = "、".join(he["branches"])

        if he_wuxing == day_wuxing:
            # 合化五行与日主同类 → 强力生扶（比肩/劫财）
            s = JU_WEIGHT.get(he_type, 2)
            score += s
            ju_descriptions.append(f"{branches_str}{he_type}{he_wuxing}局，与日主{day_tian}{day_wuxing}同类，强力帮身(+{s})")
        elif WUXING_SHENG[he_wuxing] == day_wuxing:
            # 合化五行生日主 → 强力生扶（印星）
            s = JU_WEIGHT.get(he_type, 2)
            score += s
            ju_descriptions.append(f"{branches_str}{he_type}{he_wuxing}局，{he_wuxing}生{day_wuxing}，印星生身(+{s})")
        elif WUXING_KE[day_wuxing] == he_wuxing:
            # 日主克合化五行 → 耗身（财星）
            s = -JU_WEIGHT.get(he_type, 2)
            score += s
            ju_descriptions.append(f"{branches_str}{he_type}{he_wuxing}局，日主{day_tian}{day_wuxing}克{he_wuxing}，耗身({s})")
        elif WUXING_KE[he_wuxing] == day_wuxing:
            # 合化五行克日主 → 攻身（官杀）
            s = -JU_WEIGHT.get(he_type, 2) - 1
            score += s
            ju_descriptions.append(f"{branches_str}{he_type}{he_wuxing}局，{he_wuxing}克{day_wuxing}，官杀攻身({s})")
        elif WUXING_SHENG[day_wuxing] == he_wuxing:
            # 日主生合化五行 → 泄身（食伤）
            s = -JU_WEIGHT.get(he_type, 2) + 1
            score += s
            ju_descriptions.append(f"{branches_str}{he_type}{he_wuxing}局，日主{day_tian}{day_wuxing}生{he_wuxing}，泄身({s})")
        else:
            ju_descriptions.append(f"{branches_str}{he_type}{he_wuxing}局，与日主关系平平")

    # 刑冲害破（仅对未参与合局的地支计算，避免重复）
    pillar_positions = ["year", "month", "day", "hour", "年", "月", "日", "时"]
    dz_list = []
    seen = set()
    for pos in pillar_positions:
        pillar = pillars.get(pos, {})
        if not pillar:
            continue
        di = pillar.get("di", "")
        if di and di not in seen:
            dz_list.append(di)
            seen.add(di)

    xingchong_details = []

    # 六冲
    for i in range(len(dz_list)):
        for j in range(i + 1, len(dz_list)):
            if dz_list[i] in he_branches or dz_list[j] in he_branches:
                continue  # 参与合局的地支不单独算冲
            if frozenset([dz_list[i], dz_list[j]]) in LIU_CHONG:
                score += XINGCHONG_WEIGHT["六冲"]
                xingchong_details.append(f"{dz_list[i]}{dz_list[j]}六冲({XINGCHONG_WEIGHT['六冲']})")

    # 三刑（三支）
    for xing_set in SAN_XING:
        non_he = xing_set - he_branches
        if len(non_he) >= 2 and non_he <= set(dz_list):
            score += XINGCHONG_WEIGHT["三刑"]
            xingchong_details.append(f"{''.join(sorted(non_he))}三刑({XINGCHONG_WEIGHT['三刑']})")

    # 二支刑（子卯）
    for i in range(len(dz_list)):
        for j in range(i + 1, len(dz_list)):
            if dz_list[i] in he_branches or dz_list[j] in he_branches:
                continue
            if frozenset([dz_list[i], dz_list[j]]) in ER_ZHI_XING:
                score += XINGCHONG_WEIGHT["二支刑"]
                xingchong_details.append(f"{dz_list[i]}{dz_list[j]}无礼之刑({XINGCHONG_WEIGHT['二支刑']})")

    # 自刑
    for i in range(len(dz_list)):
        for j in range(i + 1, len(dz_list)):
            if dz_list[i] in he_branches or dz_list[j] in he_branches:
                continue
            if dz_list[i] == dz_list[j] and dz_list[i] in ZI_XING:
                score += XINGCHONG_WEIGHT["自刑"]
                xingchong_details.append(f"{dz_list[i]}自刑({XINGCHONG_WEIGHT['自刑']})")

    # 六害
    for i in range(len(dz_list)):
        for j in range(i + 1, len(dz_list)):
            if dz_list[i] in he_branches or dz_list[j] in he_branches:
                continue
            if frozenset([dz_list[i], dz_list[j]]) in LIU_HAI:
                score += XINGCHONG_WEIGHT["六害"]
                xingchong_details.append(f"{dz_list[i]}{dz_list[j]}六害({XINGCHONG_WEIGHT['六害']})")

    # 六破
    for i in range(len(dz_list)):
        for j in range(i + 1, len(dz_list)):
            if dz_list[i] in he_branches or dz_list[j] in he_branches:
                continue
            if frozenset([dz_list[i], dz_list[j]]) in LIU_PO:
                score += XINGCHONG_WEIGHT["六破"]
                xingchong_details.append(f"{dz_list[i]}{dz_list[j]}六破({XINGCHONG_WEIGHT['六破']})")

    # 生成描述
    all_descriptions = ju_descriptions + xingchong_details
    if all_descriptions:
        description = "；".join(all_descriptions)
    else:
        description = "四柱无显著合局或刑冲"

    # 判定详情
    if score >= 4:
        detail = "强得局"
    elif score >= 2:
        detail = "得局"
    elif score >= -1:
        detail = "局平"
    else:
        detail = "失局"

    return {
        "score": score,
        "detail": detail,
        "description": description,
        "he_details": he_details,
        "he_branches": sorted(he_branches),
        "xingchong_details": xingchong_details,
    }


# ==================== 综合旺衰判定 ====================

def calculate_wangshuai(day_tian: str, month_di: str, day_di: str,
                        pillars: Dict, canggan: Dict, shishen: Dict) -> Dict:
    """
    日主旺衰综合判定（四维度）

    参数:
        day_tian: 日主天干（如 "甲"）
        month_di: 月令地支（如 "寅"）
        day_di: 日支地支（如 "子"）
        pillars: 四柱数据，格式如 {"年": {"tian": "甲", "di": "子"}, ...}
        canggan: 地支藏干数据，格式如 {"子": ["癸"], "丑": ["己", "辛", ""], ...}
        shishen: 十神数据，格式如 {"甲": "比肩", "丙": "正官", ...}

    返回:
        {
            "de_ling": {"score": 3, "detail": "得令", "description": "..."},
            "de_di": {"score": 1, "detail": "半得地", "description": "..."},
            "de_shi": {"score": 2, "detail": "得势", "description": "..."},
            "de_ju": {"score": 4, "detail": "得局", "description": "...", "he_details": [...], "he_branches": [...]},
            "total_score": 10,
            "conclusion": "身旺",
            "description": "日主乙木得令得势得局，综合判定为身旺"
        }
    """
    # 先计算合局（得局维度，同时得到参与合局的地支）
    de_ju = _calc_de_ju(day_tian, pillars, month_di)
    he_branches = set(de_ju.get("he_branches", []))

    # 计算其他三个维度（得势排除合局地支，避免重复计算）
    de_ling = _calc_de_ling(day_tian, month_di)
    de_di = _calc_de_di(day_tian, day_di, canggan)
    de_shi = _calc_de_shi(day_tian, pillars, shishen, he_branches)

    # 综合评分（四维度）
    total_score = de_ling["score"] + de_di["score"] + de_shi["score"] + de_ju["score"]

    # 判定结论
    day_wuxing = TIANGAN_WUXING[day_tian]
    if total_score >= 5:
        conclusion = "身旺"
    elif total_score >= 1:
        conclusion = "身偏旺"
    elif total_score >= -2:
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
    if de_ju["score"] > 0:
        parts.append(f"{de_ju['detail']}")

    if parts:
        advantage = "、".join(parts)
        description = f"日主{day_tian}{day_wuxing}{advantage}，综合判定为{conclusion}"
    else:
        description = f"日主{day_tian}{day_wuxing}不得令不得地不得势不得局，综合判定为{conclusion}"

    return {
        "de_ling": de_ling,
        "de_di": de_di,
        "de_shi": de_shi,
        "de_ju": de_ju,
        "total_score": total_score,
        "conclusion": conclusion,
        "description": description
    }
