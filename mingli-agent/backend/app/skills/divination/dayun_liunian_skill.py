"""
大运流年解读模块

纯 Python 实现，无外部依赖。
分析大运干支与原局四柱的相互作用，以及流年干支与大运、原局的相互作用，
给出吉凶判断和重点年份标注。
"""

from typing import List, Dict, Tuple, Set

# ============================================================
# 常量定义
# ============================================================

TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

TIANGAN_WUXING = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}

DIZHI_WUXING = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土",
    "巳": "火", "午": "火", "未": "土", "申": "金", "酉": "金",
    "戌": "土", "亥": "水",
}

DIZHI_CANGGAN = {
    "子": ["癸"],
    "丑": ["己", "辛", "癸"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "戊", "庚"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}

# 六冲
LIU_CHONG: Set[frozenset] = {
    frozenset(["子", "午"]), frozenset(["丑", "未"]), frozenset(["寅", "申"]),
    frozenset(["卯", "酉"]), frozenset(["辰", "戌"]), frozenset(["巳", "亥"]),
}

# 六合
LIU_HE: Set[frozenset] = {
    frozenset(["子", "丑"]), frozenset(["寅", "亥"]), frozenset(["卯", "戌"]),
    frozenset(["辰", "酉"]), frozenset(["巳", "申"]), frozenset(["午", "未"]),
}

# 三合局：申子辰水、寅午戌火、巳酉丑金、亥卯未木（无土局）
# 每局三个地支：长生 + 中神(帝旺) + 墓
SAN_HE: Dict[str, Set[str]] = {
    "水": {"申", "子", "辰"},
    "火": {"寅", "午", "戌"},
    "金": {"巳", "酉", "丑"},
    "木": {"亥", "卯", "未"},
}

# 自刑
ZI_XING: Dict[str, str] = {
    "辰": "辰辰自刑",
    "午": "午午自刑",
    "酉": "酉酉自刑",
    "亥": "亥亥自刑",
}

# 天干五合
TIANGAN_HE: Set[frozenset] = {
    frozenset(["甲", "己"]), frozenset(["乙", "庚"]), frozenset(["丙", "辛"]),
    frozenset(["丁", "壬"]), frozenset(["戊", "癸"]),
}

# 天干五合化气
TIANGAN_HE_WUXING: Dict[str, str] = {
    "甲己": "土", "乙庚": "金", "丙辛": "水",
    "丁壬": "木", "戊癸": "火",
}

# 天干相克
TIANGAN_KE: Dict[str, str] = {
    "木": "土", "火": "金", "土": "水",
    "金": "木", "水": "火",
}

# 五行生克关系
WUXING_SHENG: Dict[str, str] = {
    "木": "火", "火": "土", "土": "金", "金": "水", "水": "木",
}
WUXING_KE: Dict[str, str] = {
    "木": "土", "火": "金", "土": "水", "金": "木", "水": "火",
}

# 四柱位置名称
PILLAR_NAMES = ["年", "月", "日", "时"]


# ============================================================
# 内部辅助函数
# ============================================================

def _check_chong(dz1: str, dz2: str) -> bool:
    """判断两地支是否相冲。"""
    return frozenset([dz1, dz2]) in LIU_CHONG


def _check_he(dz1: str, dz2: str) -> bool:
    """判断两地支是否六合。"""
    return frozenset([dz1, dz2]) in LIU_HE


def _check_tiangang_he(tg1: str, tg2: str) -> bool:
    """判断两天干是否五合。"""
    return frozenset([tg1, tg2]) in TIANGAN_HE


def _get_tiangang_he_wuxing(tg1: str, tg2: str) -> str:
    """获取天干合化后的五行。"""
    key = tg1 + tg2 if TIANGAN.index(tg1) < TIANGAN.index(tg2) else tg2 + tg1
    return TIANGAN_HE_WUXING.get(key, "")


def _check_zi_xing(dz1: str, dz2: str) -> str:
    """判断两地支是否自刑，返回自刑描述，空字符串表示无自刑。"""
    if dz1 == dz2 and dz1 in ZI_XING:
        return ZI_XING[dz1]
    return ""


def _check_san_he(dz1: str, dz2: str) -> str:
    """判断两地支是否构成三合局的半合，返回五行或空字符串。

    注意：两地支相同不构成半合（相同地支走自刑判定）。
    """
    if dz1 == dz2:
        return ""
    pair = {dz1, dz2}
    for wuxing, members in SAN_HE.items():
        if pair <= members:
            return wuxing
    return ""


def _wuxing_judge(wuxing: str, yongshen: str, jishen: str) -> str:
    """判断单个五行与用神/忌神的关系，返回 '吉'/'凶'/'平'。"""
    if wuxing == yongshen:
        return "吉"
    if wuxing == jishen:
        return "凶"
    # 判断是否生用神（喜神）
    if WUXING_SHENG.get(wuxing) == yongshen:
        return "吉"
    # 判断是否生忌神
    if WUXING_SHENG.get(wuxing) == jishen:
        return "凶"
    return "平"


def _get_shishen_name(day_tian: str, tg: str) -> str:
    """
    根据日主天干和目标天干，返回十神名称。

    十神正偏规则：同阴阳→偏（偏印/偏财/七杀），异阴阳→正（正印/正财/正官）。
    此前印星/财星/官杀的正偏写反，已修正。
    """
    day_wx = TIANGAN_WUXING[day_tian]
    tg_wx = TIANGAN_WUXING[tg]
    day_yy = TIANGAN.index(day_tian) % 2  # 0=阳, 1=阴
    tg_yy = TIANGAN.index(tg) % 2
    same_yy = (day_yy == tg_yy)

    if day_wx == tg_wx:
        # 同我 → 比劫：同性比肩，异性劫财
        return "比肩" if same_yy else "劫财"
    if WUXING_SHENG.get(day_wx) == tg_wx:
        # 我生 → 食伤：同性食神，异性伤官
        return "食神" if same_yy else "伤官"
    if WUXING_SHENG.get(tg_wx) == day_wx:
        # 生我 → 印星：同性偏印，异性正印
        return "偏印" if same_yy else "正印"
    if WUXING_KE.get(day_wx) == tg_wx:
        # 我克 → 财星：同性偏财，异性正财
        return "偏财" if same_yy else "正财"
    if WUXING_KE.get(tg_wx) == day_wx:
        # 克我 → 官杀：同性七杀，异性正官
        return "七杀" if same_yy else "正官"
    return ""


def _get_pillar_dizhi_list(pillars: Dict) -> List[str]:
    """提取四柱地支列表。"""
    result = []
    for name in PILLAR_NAMES:
        if name in pillars:
            result.append(pillars[name]["di"])
    return result


def _get_pillar_tiangang_list(pillars: Dict) -> List[str]:
    """提取四柱天干列表。"""
    result = []
    for name in PILLAR_NAMES:
        if name in pillars:
            result.append(pillars[name]["tian"])
    return result


def _analyze_interactions(
    tian: str, di: str,
    pillars: Dict,
    day_tian: str,
    source_label: str,
    yongshen: str,
    jishen: str,
) -> List[str]:
    """
    分析某个干支（大运或流年）与原局四柱的相互作用，返回描述列表。
    source_label: "大运" 或 "流年"
    """
    interactions: List[str] = []
    tian_wx = TIANGAN_WUXING[tian]
    di_wx = DIZHI_WUXING[di]
    shishen = _get_shishen_name(day_tian, tian)

    # --- 天干与原局天干的关系 ---
    pillar_tg_list = _get_pillar_tiangang_list(pillars)
    for i, p_tg in enumerate(pillar_tg_list):
        pname = PILLAR_NAMES[i]
        if _check_tiangang_he(tian, p_tg):
            he_wx = _get_tiangang_he_wuxing(tian, p_tg)
            interactions.append(
                f"{source_label}天干{tian}与{pname}柱{p_tg}天干五合，合化{he_wx}"
            )
        # 天干相克
        p_tg_wx = TIANGAN_WUXING[p_tg]
        if TIANGAN_KE.get(tian_wx) == p_tg_wx:
            interactions.append(
                f"{source_label}天干{tian}{tian_wx}克{pname}柱{p_tg}{p_tg_wx}"
            )
        if TIANGAN_KE.get(p_tg_wx) == tian_wx:
            interactions.append(
                f"{pname}柱{p_tg}{p_tg_wx}克{source_label}天干{tian}{tian_wx}"
            )

    # --- 地支与原局地支的关系 ---
    pillar_dz_list = _get_pillar_dizhi_list(pillars)
    for i, p_dz in enumerate(pillar_dz_list):
        pname = PILLAR_NAMES[i]

        # 六冲
        if _check_chong(di, p_dz):
            interactions.append(
                f"{source_label}地支{di}与{pname}柱{p_dz}相冲，主变动"
            )

        # 六合
        if _check_he(di, p_dz):
            interactions.append(
                f"{source_label}地支{di}与{pname}柱{p_dz}六合，主合作"
            )

        # 自刑
        zx = _check_zi_xing(di, p_dz)
        if zx:
            interactions.append(
                f"{source_label}地支{di}与{pname}柱{p_dz}{zx}，注意内心冲突"
            )

        # 三合半合
        san_he_wx = _check_san_he(di, p_dz)
        if san_he_wx:
            interactions.append(
                f"{source_label}地支{di}与{pname}柱{p_dz}半合{san_he_wx}局"
            )

    # --- 用神/忌神天干描述 ---
    if tian_wx == yongshen:
        interactions.insert(0, f"{source_label}天干{tian}为用神，生助日主")
    elif tian_wx == jishen:
        interactions.insert(0, f"{source_label}天干{tian}为忌神，克制日主")
    elif WUXING_SHENG.get(tian_wx) == yongshen:
        interactions.insert(0, f"{source_label}天干{tian}生用神，间接助身")
    elif WUXING_SHENG.get(tian_wx) == jishen:
        interactions.insert(0, f"{source_label}天干{tian}生忌神，间接克身")
    else:
        interactions.insert(0, f"{source_label}天干{tian}（{shishen}）")

    # --- 用神/忌神地支描述 ---
    if di_wx == yongshen:
        interactions.insert(1, f"{source_label}地支{di}为用神五行")
    elif di_wx == jishen:
        interactions.insert(1, f"{source_label}地支{di}为忌神五行")

    return interactions


def _compute_overall_judge(
    tian_wx: str, di_wx: str, yongshen: str, jishen: str,
    interactions: List[str], has_chong: bool = False, has_zi_xing: bool = False,
) -> str:
    """
    综合判定吉凶。
    返回: "大吉" / "吉" / "平" / "凶" / "大凶"
    """
    scores = []
    scores.append(_wuxing_judge(tian_wx, yongshen, jishen))
    scores.append(_wuxing_judge(di_wx, yongshen, jishen))

    # 天干生用神/忌神的间接影响
    if WUXING_SHENG.get(tian_wx) == yongshen and tian_wx != yongshen:
        pass  # 已在 _wuxing_judge 中处理

    ji_count = scores.count("吉")
    xiong_count = scores.count("凶")
    ping_count = scores.count("平")

    if has_chong:
        xiong_count += 1

    if ji_count == 2 and not has_chong and not has_zi_xing:
        return "大吉"
    if ji_count >= 1 and xiong_count == 0:
        return "吉"
    if ji_count == xiong_count or (ji_count == 1 and xiong_count == 1):
        if has_zi_xing:
            return "平"
        if has_chong:
            return "凶"
        return "平"
    if xiong_count >= 1 and ji_count == 0:
        if has_chong:
            return "大凶"
        return "凶"
    if xiong_count > ji_count:
        if has_chong:
            return "大凶"
        return "凶"
    return "平"


def _build_description(
    ganzhi: str, tian: str, di: str, tian_wx: str, di_wx: str,
    day_tian: str, overall_judge: str, interactions: List[str],
    source_label: str,
) -> str:
    """生成自然语言描述。"""
    shishen = _get_shishen_name(day_tian, tian)
    parts = []

    # 开头概述
    parts.append(f"{ganzhi}{source_label}，{tian_wx}{di_wx}{'旺相' if tian_wx == di_wx else ''}。")

    # 天干十神描述
    if shishen:
        parts.append(f"{tian}{tian_wx}{shishen}，")

    # 根据吉凶补充
    if overall_judge in ("大吉", "吉"):
        parts.append(f"此{source_label}总体吉利，")
    elif overall_judge in ("大凶", "凶"):
        parts.append(f"此{source_label}需防不利，")
    else:
        parts.append(f"此{source_label}吉凶参半，")

    # 择取关键互动
    key_interactions = [i for i in interactions if "冲" in i or "合" in i or "刑" in i]
    if key_interactions:
        parts.append("".join(key_interactions[:3]) + "。")
    else:
        parts.append("与原局无明显冲合关系。")

    return "".join(parts)


# ============================================================
# 年份干支计算
# ============================================================

def _year_to_ganzhi(year: int) -> str:
    """将公历年份转换为干支。"""
    # 天干：以4为基准，(year - 4) % 10
    tg_idx = (year - 4) % 10
    # 地支：以4为基准，(year - 4) % 12
    dz_idx = (year - 4) % 12
    return TIANGAN[tg_idx] + DIZHI[dz_idx]


def _find_dayun_for_year(dayun_list: List[Dict], year: int) -> Dict:
    """
    根据年份找到当前所处的大运。
    dayun_list 中每项应包含 'start_year' 和 'ganzhi' 字段。
    """
    current_dayun = dayun_list[0] if dayun_list else {}
    for dy in dayun_list:
        start = int(dy.get("start_year", 0))
        end = int(dy.get("end_year", 9999))
        if start <= year <= end:
            current_dayun = dy
            break
        if int(dy.get("start_year", 0)) > year:
            break
        current_dayun = dy
    return current_dayun


# ============================================================
# 公开接口
# ============================================================

def analyze_dayun(
    dayun_ganzhi: str,
    day_tian: str,
    pillars: Dict,
    yongshen: str,
    jishen: str,
) -> Dict:
    """
    分析大运与原局的关系。

    参数:
        dayun_ganzhi: 大运干支（如 "癸卯"）
        day_tian: 日主天干
        pillars: 四柱 {"年": {"tian": "庚", "di": "午"}, ...}
        yongshen: 用神五行（如 "火"）
        jishen: 忌神五行（如 "水"）

    返回:
        {
            "ganzhi": "癸卯",
            "tian_wuxing": "水",
            "di_wuxing": "木",
            "is_yongshen": False,
            "is_jishen": True,
            "interactions": [...],
            "overall_judge": "凶",
            "description": "..."
        }
    """
    tian = dayun_ganzhi[0]
    di = dayun_ganzhi[1]
    tian_wx = TIANGAN_WUXING[tian]
    di_wx = DIZHI_WUXING[di]

    is_yongshen = (tian_wx == yongshen or di_wx == yongshen)
    is_jishen = (tian_wx == jishen or di_wx == jishen)

    interactions = _analyze_interactions(
        tian, di, pillars, day_tian, "大运", yongshen, jishen,
    )

    # 检测是否有冲和自刑
    has_chong = any("相冲" in i for i in interactions)
    has_zi_xing = any("自刑" in i for i in interactions)

    overall_judge = _compute_overall_judge(
        tian_wx, di_wx, yongshen, jishen, interactions, has_chong, has_zi_xing,
    )

    description = _build_description(
        dayun_ganzhi, tian, di, tian_wx, di_wx,
        day_tian, overall_judge, interactions, "大运",
    )

    return {
        "ganzhi": dayun_ganzhi,
        "tian_wuxing": tian_wx,
        "di_wuxing": di_wx,
        "is_yongshen": is_yongshen,
        "is_jishen": is_jishen,
        "interactions": interactions,
        "overall_judge": overall_judge,
        "description": description,
    }


def analyze_liunian(
    liunian_ganzhi: str,
    dayun_ganzhi: str,
    day_tian: str,
    pillars: Dict,
    yongshen: str,
    jishen: str,
) -> Dict:
    """
    分析流年与大运、原局的关系。

    参数:
        liunian_ganzhi: 流年干支（如 "丙午"）
        dayun_ganzhi: 当前大运干支（如 "癸卯"）
        day_tian: 日主天干
        pillars: 四柱 {"年": {"tian": "庚", "di": "午"}, ...}
        yongshen: 用神五行（如 "火"）
        jishen: 忌神五行（如 "水"）

    返回:
        {
            "ganzhi": "丙午",
            "tian_wuxing": "火",
            "di_wuxing": "火",
            "is_yongshen": True,
            "is_jishen": False,
            "interactions": [...],
            "overall_judge": "吉",
            "description": "..."
        }
    """
    tian = liunian_ganzhi[0]
    di = liunian_ganzhi[1]
    tian_wx = TIANGAN_WUXING[tian]
    di_wx = DIZHI_WUXING[di]

    is_yongshen = (tian_wx == yongshen or di_wx == yongshen)
    is_jishen = (tian_wx == jishen or di_wx == jishen)

    # 流年与原局的相互作用
    interactions = _analyze_interactions(
        tian, di, pillars, day_tian, "流年", yongshen, jishen,
    )

    # 流年与大运的相互作用
    dy_tian = dayun_ganzhi[0]
    dy_di = dayun_ganzhi[1]

    # 流年天干与大运天干
    if _check_tiangang_he(tian, dy_tian):
        he_wx = _get_tiangang_he_wuxing(tian, dy_tian)
        interactions.append(
            f"流年天干{tian}与大运天干{dy_tian}五合，合化{he_wx}，主变化"
        )

    dy_tian_wx = TIANGAN_WUXING[dy_tian]
    if TIANGAN_KE.get(tian_wx) == dy_tian_wx:
        interactions.append(
            f"流年天干{tian}{tian_wx}克大运天干{dy_tian}{dy_tian_wx}"
        )
    if TIANGAN_KE.get(dy_tian_wx) == tian_wx:
        interactions.append(
            f"大运天干{dy_tian}{dy_tian_wx}克流年天干{tian}{tian_wx}"
        )

    # 流年地支与大运地支
    if _check_chong(di, dy_di):
        interactions.append(
            f"流年地支{di}与大运地支{dy_di}相冲，运中多变"
        )
    if _check_he(di, dy_di):
        interactions.append(
            f"流年地支{di}与大运地支{dy_di}六合，运中有合"
        )

    zx = _check_zi_xing(di, dy_di)
    if zx:
        interactions.append(f"流年地支{di}与大运地支{dy_di}{zx}，注意内心冲突")

    san_he_wx = _check_san_he(di, dy_di)
    if san_he_wx:
        interactions.append(
            f"流年地支{di}与大运地支{dy_di}半合{san_he_wx}局"
        )

    # 检测冲和自刑
    has_chong = any("相冲" in i for i in interactions)
    has_zi_xing = any("自刑" in i for i in interactions)

    overall_judge = _compute_overall_judge(
        tian_wx, di_wx, yongshen, jishen, interactions, has_chong, has_zi_xing,
    )

    description = _build_description(
        liunian_ganzhi, tian, di, tian_wx, di_wx,
        day_tian, overall_judge, interactions, "流年",
    )

    return {
        "ganzhi": liunian_ganzhi,
        "tian_wuxing": tian_wx,
        "di_wuxing": di_wx,
        "is_yongshen": is_yongshen,
        "is_jishen": is_jishen,
        "interactions": interactions,
        "overall_judge": overall_judge,
        "description": description,
    }


def get_key_years(
    dayun_list: List[Dict],
    day_tian: str,
    pillars: Dict,
    yongshen: str,
    jishen: str,
    current_year: int,
    analyze_range: int = 20,
) -> List[Dict]:
    """
    获取重点流年列表，按重要程度排序。

    参数:
        dayun_list: 大运列表，每项含 'start_year', 'end_year', 'ganzhi'
        day_tian: 日主天干
        pillars: 四柱 {"年": {"tian": "庚", "di": "午"}, ...}
        yongshen: 用神五行（如 "火"）
        jishen: 忌神五行（如 "水"）
        current_year: 当前年份
        analyze_range: 分析未来多少年（默认20年）

    返回: 按重要程度排序的流年列表
        [
            {"year": 2026, "ganzhi": "丙午", "judge": "大吉", "reason": "..."},
            ...
        ]
    """
    results: List[Dict] = []

    for offset in range(analyze_range):
        year = current_year + offset
        ganzhi = _year_to_ganzhi(year)

        # 找到该年所处的大运
        dayun = _find_dayun_for_year(dayun_list, year)
        dayun_ganzhi = dayun.get("ganzhi", "")

        if not dayun_ganzhi:
            continue

        # 分析流年
        analysis = analyze_liunian(
            ganzhi, dayun_ganzhi, day_tian, pillars, yongshen, jishen,
        )

        # 构建理由
        reasons = []
        tian_wx = analysis["tian_wuxing"]
        di_wx = analysis["di_wuxing"]

        if tian_wx == yongshen and di_wx == yongshen:
            reasons.append(f"纯{yongshen}用神年")
        elif tian_wx == yongshen:
            reasons.append(f"天干{yongshen}用神")
        elif di_wx == yongshen:
            reasons.append(f"地支{yongshen}用神")

        if tian_wx == jishen or di_wx == jishen:
            reasons.append(f"{'天干' if tian_wx == jishen else '地支'}{jishen}忌神")

        # 冲合刑标记
        for inter in analysis["interactions"]:
            if "相冲" in inter:
                reasons.append("有冲，主变动")
                break

        for inter in analysis["interactions"]:
            if "自刑" in inter:
                reasons.append("有自刑，需注意")
                break

        for inter in analysis["interactions"]:
            if "五合" in inter:
                reasons.append("天干合，主变化")
                break

        for inter in analysis["interactions"]:
            if "六合" in inter or "半合" in inter:
                reasons.append("有合，主合作")
                break

        if not reasons:
            reasons.append("平缓之年")

        reason_str = "，".join(reasons)

        # 判定标签
        judge = analysis["overall_judge"]
        # 重点年份标注逻辑
        if tian_wx == yongshen and di_wx == yongshen:
            judge = "大吉"
        elif tian_wx == jishen and di_wx == jishen and any("相冲" in i for i in analysis["interactions"]):
            judge = "大凶"
        elif any("自刑" in i for i in analysis["interactions"]):
            if judge == "吉":
                judge = "吉（注意）"
            elif judge == "平":
                judge = "平（注意）"
            elif judge == "凶":
                judge = "凶（注意）"
        elif any("五合" in i for i in analysis["interactions"]):
            if judge in ("吉", "大吉"):
                pass  # 保持
            else:
                reason_str += "，天干合化主变化"

        results.append({
            "year": year,
            "ganzhi": ganzhi,
            "judge": judge,
            "reason": reason_str,
            "detail": analysis,
            "liuyue": analyze_liuyue(ganzhi, day_tian, pillars, yongshen, jishen),
        })

    # 按重要程度排序：大吉/大凶优先，然后吉/凶，然后平
    def _sort_key(item: Dict) -> int:
        j = item["judge"]
        if "大吉" in j:
            return 0
        if "大凶" in j:
            return 1
        if j.startswith("吉"):
            return 2
        if j.startswith("凶"):
            return 3
        return 4

    results.sort(key=_sort_key)
    return results


# ============================================================
# 流月分析（新增）
# ============================================================

# 五虎遁：年干 → 寅月天干
WU_HU_DUN = {
    "甲": "丙", "己": "丙",
    "乙": "戊", "庚": "戊",
    "丙": "庚", "辛": "庚",
    "丁": "壬", "壬": "壬",
    "戊": "甲", "癸": "甲",
}

# 12个月地支（从寅月开始）及对应公历月份
LIUYUE_MONTHS = [
    (2, "寅", "立春-惊蛰"),
    (3, "卯", "惊蛰-清明"),
    (4, "辰", "清明-立夏"),
    (5, "巳", "立夏-芒种"),
    (6, "午", "芒种-小暑"),
    (7, "未", "小暑-立秋"),
    (8, "申", "立秋-白露"),
    (9, "酉", "白露-寒露"),
    (10, "戌", "寒露-立冬"),
    (11, "亥", "立冬-大雪"),
    (12, "子", "大雪-小寒"),
    (1, "丑", "小寒-立春"),
]


def analyze_liuyue(
    liunian_ganzhi: str,
    day_tian: str,
    pillars: Dict,
    yongshen: str,
    jishen: str,
) -> List[Dict]:
    """
    分析流年12个月的吉凶（流月分析）。

    根据五虎遁推算月令干支，结合月令五行与用神/忌神的关系，
    以及月令地支与原局地支的冲合，判断每个月的吉凶。

    参数:
        liunian_ganzhi: 流年干支（如 "丙午"）
        day_tian: 日主天干
        pillars: 四柱
        yongshen: 用神五行
        jishen: 忌神五行

    返回: 12个月的吉凶列表
    """
    year_tian = liunian_ganzhi[0]
    yin_tian = WU_HU_DUN.get(year_tian, "丙")
    yin_idx = TIANGAN.index(yin_tian)

    results: List[Dict] = []
    for i, (solar_month, month_di, jieqi) in enumerate(LIUYUE_MONTHS):
        # 月干：从寅月天干开始，按天干顺序递推
        month_tian = TIANGAN[(yin_idx + i) % 10]
        month_ganzhi = month_tian + month_di

        tian_wx = TIANGAN_WUXING[month_tian]
        di_wx = DIZHI_WUXING[month_di]

        is_yongshen = (tian_wx == yongshen or di_wx == yongshen)
        is_jishen = (tian_wx == jishen or di_wx == jishen)

        # 月令地支与原局地支的冲合
        interactions: List[str] = []
        for pillar_name, pillar in pillars.items():
            p_di = pillar["di"]
            if _check_chong(month_di, p_di):
                interactions.append(f"月令{month_di}与{pillar_name}支{p_di}相冲，主变动")
            if _check_he(month_di, p_di):
                interactions.append(f"月令{month_di}与{pillar_name}支{p_di}六合，主合作")

        # 月令地支与流年地支的冲合（如子月冲午年）
        liunian_di = liunian_ganzhi[1]
        if _check_chong(month_di, liunian_di):
            interactions.append(f"月令{month_di}与流年{liunian_di}相冲，流月冲流年主大变动")
        if _check_he(month_di, liunian_di):
            interactions.append(f"月令{month_di}与流年{liunian_di}六合，流月合流年主顺遂")

        has_chong = any("相冲" in inter for inter in interactions)
        has_zi_xing = False
        # 自刑（月令与原局相同地支）
        for pillar_name, pillar in pillars.items():
            zx = _check_zi_xing(month_di, pillar["di"])
            if zx:
                interactions.append(f"月令{month_di}与{pillar_name}支{zx}")
                has_zi_xing = True

        # 综合吉凶判断
        overall_judge = _compute_overall_judge(
            tian_wx, di_wx, yongshen, jishen, interactions, has_chong, has_zi_xing,
        )

        # 构建理由
        reasons = []
        if tian_wx == yongshen and di_wx == yongshen:
            reasons.append(f"纯{yongshen}用神月")
            overall_judge = "大吉"
        elif tian_wx == yongshen:
            reasons.append(f"天干{yongshen}用神")
        elif di_wx == yongshen:
            reasons.append(f"地支{yongshen}用神")

        if tian_wx == jishen or di_wx == jishen:
            reasons.append(f"{'天干' if tian_wx == jishen else '地支'}{jishen}忌神")

        for inter in interactions:
            if "相冲" in inter:
                reasons.append("有冲，主变动")
                break
        for inter in interactions:
            if "六合" in inter:
                reasons.append("有合，主合作")
                break

        if not reasons:
            reasons.append("平缓之月")

        results.append({
            "solar_month": solar_month,
            "month_ganzhi": month_ganzhi,
            "tian_wuxing": tian_wx,
            "di_wuxing": di_wx,
            "is_yongshen": is_yongshen,
            "is_jishen": is_jishen,
            "judge": overall_judge,
            "reason": "，".join(reasons),
            "interactions": interactions,
        })

    return results

