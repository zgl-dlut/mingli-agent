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

# 三合中神（帝旺位）：半合带中神力量较强，不带中神半合力弱
SAN_HE_ZHONG_SHEN: Set[str] = {"子", "午", "卯", "酉"}

# 三会局：寅卯辰会木、巳午未会火、申酉戌会金、亥子丑会水
# 三会力量强于三合，且无半会（必须三支齐全方论会）
SAN_HUI: Dict[str, Set[str]] = {
    "木": {"寅", "卯", "辰"},
    "火": {"巳", "午", "未"},
    "金": {"申", "酉", "戌"},
    "水": {"亥", "子", "丑"},
}

# 月令五行（地支当令本气五行，用于合化"化神得令"校验）
DIZHI_LING_WUXING = DIZHI_WUXING  # 当令本气即地支本五行

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


def _check_full_san_he(di: str, pillar_dz_list: List[str]) -> str:
    """检测流年/大运地支与原局地支是否构成完整三合局，返回合化五行或空字符串。

    三合局需三个地支齐全（如原局已有亥、卯，流年未到则亥卯未全化木）。
    半合（仅两个地支）力量弱，不在此判定，走 _check_san_he。
    """
    all_dz = set(pillar_dz_list)
    all_dz.add(di)
    for wuxing, members in SAN_HE.items():
        if members <= all_dz:
            return wuxing
    return ""


def _check_full_san_hui(di: str, pillar_dz_list: List[str]) -> str:
    """检测流年/大运地支与原局地支是否构成完整三会局，返回合化五行或空字符串。

    三会局（寅卯辰会木等）需三支齐全，力量强于三合，且无半会。
    """
    all_dz = set(pillar_dz_list)
    all_dz.add(di)
    for wuxing, members in SAN_HUI.items():
        if members <= all_dz:
            return wuxing
    return ""


def _san_he_ban_he_has_zhongshen(dz1: str, dz2: str) -> bool:
    """半合是否带中神（子午卯酉帝旺位），带中神半合力量较强。"""
    return dz1 in SAN_HE_ZHONG_SHEN or dz2 in SAN_HE_ZHONG_SHEN


def _he_hua_relation(he_wx: str, day_tian: str, yongshen: str, jishen: str) -> str:
    """合化五行与日主/用忌的关系。

    返回: '忌'(合化忌神或克日主=七杀攻身) / '用'(合化用神或生日主=印星生身) / '平'。
    """
    day_wx = TIANGAN_WUXING[day_tian]
    if he_wx == jishen or WUXING_KE.get(he_wx) == day_wx:
        return "忌"
    if he_wx == yongshen or WUXING_SHENG.get(he_wx) == day_wx:
        return "用"
    return "平"


def _check_hua_shen_deling(he_wx: str, month_dz: str, extra_dz: str = "") -> bool:
    """化神是否得令（合化成立条件）。

    标准命理：合化需化神得令或有根。此处校验：
    - 原局月支五行==化神（化神当令）
    - 原局月支五行生化神（如月亥水生木）
    - 流年/大运地支五行==化神（动态助化）
    满足其一即真化；否则合而不化，只论合绊。
    无月令信息时默认真化（兼容旧调用）。
    """
    if not month_dz:
        return True
    m_wx = DIZHI_WUXING.get(month_dz, "")
    if m_wx == he_wx:
        return True
    if WUXING_SHENG.get(m_wx) == he_wx:
        return True
    if extra_dz and DIZHI_WUXING.get(extra_dz, "") == he_wx:
        return True
    return False


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

    标注规范（_compute_overall_judge 据此计分）：
    - 冲：'冲用神'(凶) / '冲忌神'(去忌为吉) / '相冲，主变动'(中性)
    - 合化：'三合X局克身/生身' / '三会X局克身/生身' / '半合X局（带中神）克身/生身'
    - 天干合：'合化X（忌神/用神/中性）' / '合而不化'
    - 六合绊：'六合绊用神'(减吉) / '六合绊忌神'(减凶) / '六合，主合作'(中性)
    - 合而不化时只论合绊，不计合化吉凶
    """
    interactions: List[str] = []
    tian_wx = TIANGAN_WUXING[tian]
    di_wx = DIZHI_WUXING[di]
    shishen = _get_shishen_name(day_tian, tian)
    month_dz = pillars.get("月", {}).get("di", "")  # 原局月支，用于合化得令校验

    # --- 天干与原局天干的关系 ---
    pillar_tg_list = _get_pillar_tiangang_list(pillars)
    for i, p_tg in enumerate(pillar_tg_list):
        pname = PILLAR_NAMES[i]
        if _check_tiangang_he(tian, p_tg):
            he_wx = _get_tiangang_he_wuxing(tian, p_tg)
            if _check_hua_shen_deling(he_wx, month_dz, di):
                rel = _he_hua_relation(he_wx, day_tian, yongshen, jishen)
                tag = {"忌": "忌神", "用": "用神", "平": "中性"}.get(rel, "中性")
                interactions.append(
                    f"{source_label}天干{tian}与{pname}柱{p_tg}天干五合，合化{he_wx}（{tag}）"
                )
            else:
                interactions.append(
                    f"{source_label}天干{tian}与{pname}柱{p_tg}天干五合，合而不化（合绊）"
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
        p_wx = DIZHI_WUXING[p_dz]

        # 六冲：区分冲用神(凶)/冲忌神(去忌为吉)/中性冲(主变动)
        if _check_chong(di, p_dz):
            if p_wx == yongshen:
                interactions.append(
                    f"{source_label}地支{di}冲{pname}柱{p_dz}（冲用神，凶）"
                )
            elif p_wx == jishen:
                interactions.append(
                    f"{source_label}地支{di}冲{pname}柱{p_dz}（冲忌神，去忌为吉）"
                )
            else:
                interactions.append(
                    f"{source_label}地支{di}与{pname}柱{p_dz}相冲，主变动"
                )

        # 六合：六合不化，论合绊（绊用神减吉/绊忌神减凶/中性合作）
        if _check_he(di, p_dz):
            if p_wx == yongshen or di_wx == yongshen:
                interactions.append(
                    f"{source_label}地支{di}与{pname}柱{p_dz}六合绊用神"
                )
            elif p_wx == jishen or di_wx == jishen:
                interactions.append(
                    f"{source_label}地支{di}与{pname}柱{p_dz}六合绊忌神"
                )
            else:
                interactions.append(
                    f"{source_label}地支{di}与{pname}柱{p_dz}六合，主合作"
                )

        # 自刑
        zx = _check_zi_xing(di, p_dz)
        if zx:
            interactions.append(
                f"{source_label}地支{di}与{pname}柱{p_dz}{zx}，注意内心冲突"
            )

        # 三合半合：带中神且化神得令时，化忌克身/化用生身参与吉凶
        san_he_wx = _check_san_he(di, p_dz)
        if san_he_wx:
            has_zs = _san_he_ban_he_has_zhongshen(di, p_dz)
            if has_zs and _check_hua_shen_deling(san_he_wx, month_dz, di):
                rel = _he_hua_relation(san_he_wx, day_tian, yongshen, jishen)
                tag = {"忌": "克身", "用": "生身"}.get(rel, "")
                zs_tag = "（带中神）"
                if tag:
                    interactions.append(
                        f"{source_label}地支{di}与{pname}柱{p_dz}半合{san_he_wx}局{zs_tag}{tag}"
                    )
                else:
                    interactions.append(
                        f"{source_label}地支{di}与{pname}柱{p_dz}半合{san_he_wx}局{zs_tag}"
                    )
            else:
                interactions.append(
                    f"{source_label}地支{di}与{pname}柱{p_dz}半合{san_he_wx}局"
                )

    # 完整三合局：力量强，化神得令则化忌克身/化用生身，否则合而不化
    full_san_he = _check_full_san_he(di, pillar_dz_list)
    if full_san_he:
        if _check_hua_shen_deling(full_san_he, month_dz, di):
            rel = _he_hua_relation(full_san_he, day_tian, yongshen, jishen)
            tag = {"忌": "克身", "用": "生身"}.get(rel, "")
            if tag:
                interactions.append(
                    f"{source_label}地支{di}与原局构成三合{full_san_he}局{tag}"
                )
            else:
                interactions.append(
                    f"{source_label}地支{di}与原局构成三合{full_san_he}局"
                )
        else:
            interactions.append(
                f"{source_label}地支{di}与原局构成三合{full_san_he}局（合而不化）"
            )

    # 完整三会局：力量强于三合，化神得令则化忌克身/化用生身
    full_san_hui = _check_full_san_hui(di, pillar_dz_list)
    if full_san_hui:
        if _check_hua_shen_deling(full_san_hui, month_dz, di):
            rel = _he_hua_relation(full_san_hui, day_tian, yongshen, jishen)
            tag = {"忌": "克身", "用": "生身"}.get(rel, "")
            if tag:
                interactions.append(
                    f"{source_label}地支{di}与原局构成三会{full_san_hui}局{tag}"
                )
            else:
                interactions.append(
                    f"{source_label}地支{di}与原局构成三会{full_san_hui}局"
                )
        else:
            interactions.append(
                f"{source_label}地支{di}与原局构成三会{full_san_hui}局（合而不化）"
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
    interactions: List[str],
) -> str:
    """综合判定吉凶，从 interactions 解析冲合化刑要素计分。

    返回: "大吉" / "吉" / "平" / "凶" / "大凶"

    计分规则（标准排盘合化体系）：
    - 基础：天干/地支五行 vs 用忌（_wuxing_judge）
    - 冲用神: xiong+2（用神被冲破，大凶）；冲忌神: ji+1（去忌为吉）；中性冲: xiong+1（主变动）
    - 三会化忌克身: xiong+3（力量最强）；三合化忌克身: xiong+2；带中神半合化忌: xiong+1
    - 三会化用生身: ji+3；三合化用生身: ji+2；带中神半合化用: ji+1
    - 天干合化忌神: xiong+1；天干合化用神: ji+1；合而不化不计
    - 六合绊用神: xiong+1（羁绊用神减吉）；六合绊忌神: ji+1（羁绊忌神减凶）
    - 自刑: 偏凶，影响判定阈值
    """
    scores = [_wuxing_judge(tian_wx, yongshen, jishen), _wuxing_judge(di_wx, yongshen, jishen)]
    ji_count = scores.count("吉")
    xiong_count = scores.count("凶")

    has_chong = False       # 有冲（中性冲或冲用神）
    has_zi_xing = False     # 有自刑
    has_he_ji = False       # 完整三合/三会化忌克身（强力凶，影响大吉判定）

    for inter in interactions:
        if "自刑" in inter:
            has_zi_xing = True
            continue
        # 六冲方向（先判冲用神/冲忌神，再判中性冲）
        if "冲用神" in inter:
            has_chong = True
            xiong_count += 2
        elif "冲忌神" in inter:
            ji_count += 1  # 去忌为吉，不计冲凶
        elif "相冲，主变动" in inter:
            has_chong = True
            xiong_count += 1
        # 三会局化神（力量最强）
        elif "三会" in inter and "克身" in inter:
            has_he_ji = True
            xiong_count += 3
        elif "三会" in inter and "生身" in inter:
            ji_count += 3
        # 完整三合局化神
        elif "三合" in inter and "克身" in inter:
            has_he_ji = True
            xiong_count += 2
        elif "三合" in inter and "生身" in inter:
            ji_count += 2
        # 带中神半合化神
        elif "半合" in inter and "克身" in inter:
            xiong_count += 1
        elif "半合" in inter and "生身" in inter:
            ji_count += 1
        # 天干合化（区分合化忌神/用神/中性，合而不化不计）
        elif "合化" in inter and "忌神" in inter:
            xiong_count += 1
        elif "合化" in inter and "用神" in inter:
            ji_count += 1
        # 六合绊（区分绊用神/绊忌神/中性合作）
        elif "六合绊用神" in inter:
            xiong_count += 1
        elif "六合绊忌神" in inter:
            ji_count += 1

    # 判定阈值（保持原框架，has_chong/has_zi_xing/has_he_ji 抑制大吉）
    if ji_count >= 2 and xiong_count == 0 and not has_chong and not has_zi_xing and not has_he_ji:
        return "大吉"
    if ji_count >= 1 and xiong_count == 0:
        return "吉"
    if ji_count > xiong_count and xiong_count > 0:
        # 吉多凶少（如三合生身+地支生忌），偏吉
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

    # 综合判定（冲合化刑要素由 _compute_overall_judge 从 interactions 解析）
    overall_judge = _compute_overall_judge(
        tian_wx, di_wx, yongshen, jishen, interactions,
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

    # 流年地支与大运地支（方向标注，与原局一致）
    dy_di_wx = DIZHI_WUXING[dy_di]
    month_dz = pillars.get("月", {}).get("di", "")
    if _check_chong(di, dy_di):
        if dy_di_wx == yongshen:
            interactions.append(f"流年地支{di}冲大运地支{dy_di}（冲用神，凶）")
        elif dy_di_wx == jishen:
            interactions.append(f"流年地支{di}冲大运地支{dy_di}（冲忌神，去忌为吉）")
        else:
            interactions.append(f"流年地支{di}与大运地支{dy_di}相冲，主变动")
    if _check_he(di, dy_di):
        if dy_di_wx == yongshen or di_wx == yongshen:
            interactions.append(f"流年地支{di}与大运地支{dy_di}六合绊用神")
        elif dy_di_wx == jishen or di_wx == jishen:
            interactions.append(f"流年地支{di}与大运地支{dy_di}六合绊忌神")
        else:
            interactions.append(f"流年地支{di}与大运地支{dy_di}六合，主合作")

    zx = _check_zi_xing(di, dy_di)
    if zx:
        interactions.append(f"流年地支{di}与大运地支{dy_di}{zx}，注意内心冲突")

    san_he_wx = _check_san_he(di, dy_di)
    if san_he_wx:
        has_zs = _san_he_ban_he_has_zhongshen(di, dy_di)
        if has_zs and _check_hua_shen_deling(san_he_wx, month_dz, di):
            rel = _he_hua_relation(san_he_wx, day_tian, yongshen, jishen)
            tag = {"忌": "克身", "用": "生身"}.get(rel, "")
            zs_tag = "（带中神）"
            if tag:
                interactions.append(f"流年地支{di}与大运地支{dy_di}半合{san_he_wx}局{zs_tag}{tag}")
            else:
                interactions.append(f"流年地支{di}与大运地支{dy_di}半合{san_he_wx}局{zs_tag}")
        else:
            interactions.append(f"流年地支{di}与大运地支{dy_di}半合{san_he_wx}局")

    # 综合判定（冲合化刑要素由 _compute_overall_judge 从 interactions 解析）
    overall_judge = _compute_overall_judge(
        tian_wx, di_wx, yongshen, jishen, interactions,
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

        # 完整三合局优先于六合/半合判定：合化忌神或克日主标"克身"，否则"主合作"
        san_he_added = False
        for inter in analysis["interactions"]:
            if "三合" in inter and "局" in inter:
                for wx in ("木", "火", "土", "金", "水"):
                    if f"三合{wx}局" in inter:
                        day_wx = TIANGAN_WUXING[day_tian]
                        if wx == jishen or WUXING_KE.get(wx) == day_wx:
                            reasons.append(f"三合{wx}局克身，压力大")
                        else:
                            reasons.append("有合，主合作")
                        san_he_added = True
                        break
                break
        if not san_he_added:
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

        # 月令地支与原局地支的冲合（方向标注，与大运/流年一致）
        interactions: List[str] = []
        for pillar_name, pillar in pillars.items():
            p_di = pillar["di"]
            p_wx = DIZHI_WUXING[p_di]
            if _check_chong(month_di, p_di):
                if p_wx == yongshen:
                    interactions.append(f"月令{month_di}冲{pillar_name}支{p_di}（冲用神，凶）")
                elif p_wx == jishen:
                    interactions.append(f"月令{month_di}冲{pillar_name}支{p_di}（冲忌神，去忌为吉）")
                else:
                    interactions.append(f"月令{month_di}与{pillar_name}支{p_di}相冲，主变动")
            if _check_he(month_di, p_di):
                m_wx = DIZHI_WUXING[month_di]
                if p_wx == yongshen or m_wx == yongshen:
                    interactions.append(f"月令{month_di}与{pillar_name}支{p_di}六合绊用神")
                elif p_wx == jishen or m_wx == jishen:
                    interactions.append(f"月令{month_di}与{pillar_name}支{p_di}六合绊忌神")
                else:
                    interactions.append(f"月令{month_di}与{pillar_name}支{p_di}六合，主合作")

        # 月令地支与流年地支的冲合（如子月冲午年）
        liunian_di = liunian_ganzhi[1]
        l_di_wx = DIZHI_WUXING[liunian_di]
        if _check_chong(month_di, liunian_di):
            if l_di_wx == yongshen:
                interactions.append(f"月令{month_di}冲流年{liunian_di}（冲用神，凶）")
            elif l_di_wx == jishen:
                interactions.append(f"月令{month_di}冲流年{liunian_di}（冲忌神，去忌为吉）")
            else:
                interactions.append(f"月令{month_di}与流年{liunian_di}相冲，主变动")
        if _check_he(month_di, liunian_di):
            m_wx = DIZHI_WUXING[month_di]
            if l_di_wx == yongshen or m_wx == yongshen:
                interactions.append(f"月令{month_di}与流年{liunian_di}六合绊用神")
            elif l_di_wx == jishen or m_wx == jishen:
                interactions.append(f"月令{month_di}与流年{liunian_di}六合绊忌神")
            else:
                interactions.append(f"月令{month_di}与流年{liunian_di}六合，主合作")

        # 自刑（月令与原局相同地支）
        for pillar_name, pillar in pillars.items():
            zx = _check_zi_xing(month_di, pillar["di"])
            if zx:
                interactions.append(f"月令{month_di}与{pillar_name}支{zx}")

        # 综合吉凶判断（冲合化刑由 _compute_overall_judge 从 interactions 解析）
        overall_judge = _compute_overall_judge(
            tian_wx, di_wx, yongshen, jishen, interactions,
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

