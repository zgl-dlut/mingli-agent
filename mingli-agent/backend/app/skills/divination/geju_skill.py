"""
格局判定模块 —— 基于《渊海子平》

格局判定基于月令（月支）藏干中的十神关系，找出命局中的"格局用神"。
判定优先级：本气 > 中气 > 余气。
纯 Python 实现，无外部依赖。
"""

from typing import Dict, Optional

# ============================================================
# 常量定义
# ============================================================

TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]

# 天干五行
TIANGAN_WUXING = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}

# 天干五合
TIANGAN_HE = {
    "甲": "己", "己": "甲",
    "乙": "庚", "庚": "乙",
    "丙": "辛", "辛": "丙",
    "丁": "壬", "壬": "丁",
    "戊": "癸", "癸": "戊",
}

# 五合化气结果
TIANGAN_HE_HUA = {
    ("甲", "己"): "土",
    ("己", "甲"): "土",
    ("乙", "庚"): "金",
    ("庚", "乙"): "金",
    ("丙", "辛"): "水",
    ("辛", "丙"): "水",
    ("丁", "壬"): "木",
    ("壬", "丁"): "木",
    ("戊", "癸"): "火",
    ("癸", "戊"): "火",
}

# 月令藏干（本气、中气、余气）
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

# 藏干层级名称
CANGGAN_LEVEL = ["本气", "中气", "余气"]

# 格局名称映射
GEJU_NAME_MAP = {
    "正官": "正官格",
    "七杀": "七杀格（偏官格）",
    "正财": "正财格",
    "偏财": "偏财格",
    "食神": "食神格",
    "伤官": "伤官格",
    "正印": "正印格",
    "偏印": "偏印格（枭神格）",
}

# 格局喜忌（身旺/身弱时格局用神的喜忌不同）
GEJU_XI_JI = {
    "正官格": {
        "身旺": {
            "喜": "财星、食神",
            "忌": "印星、比劫",
            "描述": "身旺正官格，喜财星生官、食神制杀，忌印星泄官、比劫争权",
        },
        "身弱": {
            "喜": "印星、比劫",
            "忌": "财星、食伤",
            "描述": "身弱正官格，喜印星护官、比劫帮身，忌财星破印、食伤克官",
        },
    },
    "七杀格（偏官格）": {
        "身旺": {
            "喜": "食神、财星",
            "忌": "印星、比劫",
            "描述": "身旺七杀格，喜食神制杀、财星生杀，忌印星化杀为权太过",
        },
        "身弱": {
            "喜": "印星、比劫",
            "忌": "财星、食伤",
            "描述": "身弱七杀格，喜印星化杀生身、比劫帮身抗杀，忌财星生杀太过",
        },
    },
    "正财格": {
        "身旺": {
            "喜": "官星、食伤",
            "忌": "比劫",
            "描述": "身旺正财格，喜官星护财、食伤生财，忌比劫夺财",
        },
        "身弱": {
            "喜": "印星、比劫",
            "忌": "财星多见",
            "描述": "身弱正财格，喜印星生身、比劫帮身担财，忌财多身弱",
        },
    },
    "偏财格": {
        "身旺": {
            "喜": "官杀、食伤",
            "忌": "比劫",
            "描述": "身旺偏财格，喜官杀护财、食伤生财，忌比劫争夺",
        },
        "身弱": {
            "喜": "印星、比劫",
            "忌": "财星多见",
            "描述": "身弱偏财格，喜印星生身、比劫帮身，忌财多身弱",
        },
    },
    "食神格": {
        "身旺": {
            "喜": "财星、七杀",
            "忌": "印星、比劫",
            "描述": "身旺食神格，喜财星泄秀、食神制杀，忌印星夺食",
        },
        "身弱": {
            "喜": "印星、比劫",
            "忌": "财星、七杀",
            "描述": "身弱食神格，喜印星生身、比劫帮身，忌财泄太过",
        },
    },
    "伤官格": {
        "身旺": {
            "喜": "财星、印星",
            "忌": "比劫",
            "描述": "身旺伤官格，喜伤官生财、伤官配印，忌比劫争夺",
        },
        "身弱": {
            "喜": "印星、比劫",
            "忌": "财星、官星",
            "描述": "身弱伤官格，喜印星制伤、比劫帮身，忌伤官见官",
        },
    },
    "正印格": {
        "身旺": {
            "喜": "财星、食伤",
            "忌": "印星多见",
            "描述": "身旺正印格，喜财星坏印、食伤泄秀，忌印多为忌",
        },
        "身弱": {
            "喜": "印星、比劫",
            "忌": "财星、食伤",
            "描述": "身弱正印格，喜印星生身、比劫帮身，忌财星坏印",
        },
    },
    "偏印格（枭神格）": {
        "身旺": {
            "喜": "财星、食伤",
            "忌": "印星多见",
            "描述": "身旺偏印格，喜财星制枭、食伤泄秀，忌枭印夺食",
        },
        "身弱": {
            "喜": "印星、比劫",
            "忌": "财星、食伤",
            "描述": "身弱偏印格，喜印星生身、比劫帮身，忌财星制印",
        },
    },
}

# 特殊格局判定条件
SPECIAL_GEJU = {
    "从格": {
        "condition": "日主无根无生扶，全局从旺或从弱",
        "description": "日主极弱或极旺，从势而行",
    },
    "化气格": {
        "condition": "天干五合化气成功（如甲己合化土）",
        "description": "天干相合化气，以化气五行为主",
    },
}

# 建禄格对应关系：月令地支 -> 建禄天干
# 建禄即月令藏干本气与日主同类（比肩/劫财）时的特殊格局
JIANLU_MAP = {
    "寅": "甲",  # 甲禄在寅
    "卯": "乙",  # 乙禄在卯
    "巳": "丙",  # 丙禄在巳
    "午": "丁",  # 丁禄在午
    "申": "庚",  # 庚禄在申
    "酉": "辛",  # 辛禄在酉
    "亥": "壬",  # 壬禄在亥
    "子": "癸",  # 癸禄在子
}


# ============================================================
# 内部工具函数
# ============================================================

def _calc_shishen(day_tian: str, tian: str) -> str:
    """
    计算十神（基于五行生克 + 阴阳正偏）。

    与 bazi_service.calculate_shishen 算法保持一致，避免阴干日主正偏全反的 bug。

    规则：
    1. 先定五行关系：同我→比劫，我生→食伤，我克→财星，克我→官杀，生我→印星
    2. 再定阴阳正偏：同阴阳→偏，异阴阳→正

    天干索引：甲0乙1丙2丁3戊4己5庚6辛7壬8癸9
    五行索引（index//2）：木0 火1 土2 金3 水4
    wuxing_diff = (tian_wuxing - day_wuxing) % 5
      0=同我(比劫) 1=我生(食伤) 2=我克(财星) 3=克我(官杀) 4=生我(印星)
    """
    day_index = TIANGAN.index(day_tian)
    tian_index = TIANGAN.index(tian)

    day_wuxing = day_index // 2
    tian_wuxing = tian_index // 2
    same_yin_yang = (day_index % 2) == (tian_index % 2)

    wuxing_diff = (tian_wuxing - day_wuxing) % 5

    if wuxing_diff == 0:
        # 同我 → 比劫
        return "比肩" if same_yin_yang else "劫财"
    elif wuxing_diff == 1:
        # 我生 → 食伤
        return "食神" if same_yin_yang else "伤官"
    elif wuxing_diff == 2:
        # 我克 → 财星
        return "偏财" if same_yin_yang else "正财"
    elif wuxing_diff == 3:
        # 克我 → 官杀
        return "七杀" if same_yin_yang else "正官"
    else:
        # 生我 → 印星
        return "偏印" if same_yin_yang else "正印"


def _check_tiangang_he(pillars: Dict) -> Optional[Dict]:
    """
    检查四柱天干是否有五合。

    参数:
        pillars: 四柱 {"年": {"tian": "庚", "di": "午"}, ...}

    返回:
        如果存在五合，返回 {"天干1": x, "天干2": y, "化气": z, "说明": ...}；
        否则返回 None。
    """
    tian_gans = []
    pillar_names = ["年", "月", "日", "时"]
    for name in pillar_names:
        if name in pillars and "tian" in pillars[name]:
            tian_gans.append(pillars[name]["tian"])

    # 检查相邻天干是否有五合（年月、月日、日时）
    adjacent_pairs = [
        (tian_gans[0], tian_gans[1], "年月"),
        (tian_gans[1], tian_gans[2], "月日"),
        (tian_gans[2], tian_gans[3], "日时"),
    ]

    for tg1, tg2, pos in adjacent_pairs:
        if tg2 == TIANGAN_HE.get(tg1):
            hua = TIANGAN_HE_HUA.get((tg1, tg2), "")
            return {
                "天干1": tg1,
                "天干2": tg2,
                "位置": pos,
                "化气": hua,
                "说明": f"{pos}干{tg1}{tg2}相合，化{hua}气",
            }

    return None


def _normalize_wangshuai(wangshuai_conclusion: str) -> str:
    """
    将旺衰结论归一化为"身旺"或"身弱"。

    参数:
        wangshuai_conclusion: 旺衰结论，如 "身旺"/"身弱"/"身偏旺"/"身偏弱"

    返回:
        "身旺" 或 "身弱"
    """
    if "旺" in wangshuai_conclusion:
        return "身旺"
    return "身弱"


def _get_wuxing_name(tian: str) -> str:
    """获取天干五行名称。"""
    return TIANGAN_WUXING.get(tian, "")


# 印星五行映射（生我者为印）
YINSHEN_WUXING = {"木": "水", "火": "木", "土": "火", "金": "土", "水": "金"}

# 冬月（水旺需火暖局）、夏月（火旺需水润局）
TIAOHOU_MONTH = {
    "亥": "火", "子": "火", "丑": "火",   # 冬月 → 调候用神火
    "巳": "水", "午": "水", "未": "水",   # 夏月 → 调候用神水
}

# 调候用神五行 → 对日主的十神类型
TIAOHOU_SHISHEN = {"木": "比劫", "火": "食伤", "土": "财星", "金": "官杀", "水": "印星"}


def _apply_tiaohou_correction(xi_ji: Dict, day_tian: str, month_di: str, geju_type: str) -> Dict:
    """
    调候修正：当固定格局模板的"喜印星"与调候用神矛盾时，以调候用神为准修正喜忌。

    典型场景：乙木生子月（冬月水旺木冻），身弱食神格固定模板说"喜印星（水）"，
    但冬月水旺本身就是病，印星（水）为忌非喜，调候用神火（食伤）才是真喜。
    """
    if not xi_ji or "印星" not in xi_ji.get("喜", ""):
        return xi_ji

    tiaohou_wuxing = TIAOHOU_MONTH.get(month_di)
    if not tiaohou_wuxing:
        return xi_ji

    day_wuxing = TIANGAN_WUXING.get(day_tian, "")
    yinshen_wuxing = YINSHEN_WUXING.get(day_wuxing, "")

    # 印星五行与调候用神五行相同 → 印星即为调候用神，无矛盾
    if yinshen_wuxing == tiaohou_wuxing:
        return xi_ji

    # 印星五行与调候用神五行不同 → 矛盾，调候优先
    # 例：冬月调候需火，但印星是水（水旺为忌） → 修正为喜食伤（火）
    tiaohou_shishen = TIAOHOU_SHISHEN.get(tiaohou_wuxing, "")
    season_label = "冬月水旺" if tiaohou_wuxing == "火" else "夏月火旺"
    corrected = {
        "喜": f"{tiaohou_shishen}（调候用神{tiaohou_wuxing}）、比劫",
        "忌": f"印星（{yinshen_wuxing}旺为忌）、财星",
        "描述": (
            f"身弱{geju_type}，但生于{month_di}月{season_label}，"
            f"非{tiaohou_wuxing}不能解冻——调候用神为{tiaohou_wuxing}（{tiaohou_shishen}），"
            f"喜{tiaohou_shishen}暖局、比劫帮身，忌印星（{yinshen_wuxing}）太过"
        ),
    }
    return corrected


# ============================================================
# 主接口
# ============================================================

def calculate_geju(
    day_tian: str,
    month_di: str,
    pillars: Dict,
    shishen: Dict,
    wangshuai_conclusion: str,
) -> Dict:
    """
    格局判定。

    参数:
        day_tian: 日主天干
        month_di: 月令地支
        pillars: 四柱 {"年": {"tian": "庚", "di": "午"}, ...}
        shishen: 十神 {"年": {"tian": "正财", "di": "偏印"}, ...}
        wangshuai_conclusion: 旺衰结论 "身旺"/"身弱"/"身偏旺"/"身偏弱"

    返回:
        {
            "geju_type": "正官格",
            "geju_source": "月令本气",
            "geju_shishen": "正官",
            "geju_source_ganzhi": "月令子，本气癸水",
            "xi_ji": {"喜": "...", "忌": "...", "描述": "..."},
            "special_geju": None,
            "full_description": "..."
        }
    """
    # ---- 1. 获取月令藏干 ----
    canggan_list = DIZHI_CANGGAN.get(month_di, [])
    if not canggan_list:
        return {
            "geju_type": "未知格局",
            "geju_source": "无法判定",
            "geju_shishen": "",
            "geju_source_ganzhi": f"月令{month_di}无藏干记录",
            "xi_ji": {},
            "special_geju": None,
            "full_description": f"月令{month_di}无藏干记录，无法判定格局。",
        }

    # ---- 2. 按优先级（本气 > 中气 > 余气）逐层判定 ----
    geju_shishen = None
    geju_source = None
    geju_source_ganzhi = None
    used_gan = None

    for i, cang_gan in enumerate(canggan_list):
        level_name = CANGGAN_LEVEL[i] if i < len(CANGGAN_LEVEL) else f"第{i+1}气"
        ss = _calc_shishen(day_tian, cang_gan)

        if ss not in ("比肩", "劫财"):
            geju_shishen = ss
            geju_source = f"月令{level_name}"
            wuxing = _get_wuxing_name(cang_gan)
            geju_source_ganzhi = f"月令{month_di}，{level_name}{cang_gan}{wuxing}"
            used_gan = cang_gan
            break

    # ---- 3. 所有藏干都是比肩/劫财 → 建禄格 ----
    if geju_shishen is None:
        geju_type = "建禄格"
        geju_source = "月令建禄"
        benqi = canggan_list[0]
        wuxing = _get_wuxing_name(benqi)
        geju_source_ganzhi = f"月令{month_di}，本气{benqi}{wuxing}为日主同类，取建禄格"
        geju_shishen = "比肩"
        # 建禄格的喜忌
        ws = _normalize_wangshuai(wangshuai_conclusion)
        xi_ji = {
            "身旺": {
                "喜": "财星、官杀、食伤",
                "忌": "印星、比劫",
                "描述": "身旺建禄格，身强禄旺，喜财官食伤泄耗，忌印比再助",
            },
            "身弱": {
                "喜": "印星、比劫",
                "忌": "财星、官杀、食伤",
                "描述": "身弱建禄格，虽有禄根但全局泄耗太过，喜印比生扶",
            },
        }.get(ws, {})

        # 建禄格也做调候修正
        xi_ji = _apply_tiaohou_correction(xi_ji, day_tian, month_di, geju_type)

        full_desc = (
            f"{day_tian}{_get_wuxing_name(day_tian)}生于{month_di}月，"
            f"月令藏干皆为日主同类，取建禄格。"
        )
        if xi_ji:
            full_desc += xi_ji.get("描述", "")
    else:
        # ---- 4. 正常格局 ----
        geju_type = GEJU_NAME_MAP.get(geju_shishen, f"{geju_shishen}格")

        # ---- 5. 查找喜忌 ----
        ws = _normalize_wangshuai(wangshuai_conclusion)
        xi_ji = GEJU_XI_JI.get(geju_type, {}).get(ws, {})

        # ---- 5.1 调候修正（冬月/夏月，印星与调候用神矛盾时以调候为准）----
        xi_ji = _apply_tiaohou_correction(xi_ji, day_tian, month_di, geju_type)

        # ---- 6. 组装完整描述 ----
        wuxing_day = _get_wuxing_name(day_tian)
        full_desc = (
            f"{day_tian}{wuxing_day}生于{month_di}月，"
            f"{geju_source_ganzhi}为{geju_shishen}，取{geju_type}。"
        )
        if xi_ji and "描述" in xi_ji:
            full_desc += xi_ji["描述"]

    # ---- 7. 检查特殊格局 ----
    special_geju = None

    # 7a. 化气格：检查天干五合
    he_info = _check_tiangang_he(pillars)
    if he_info is not None:
        special_geju = {
            "type": "化气格",
            "detail": he_info,
            "description": SPECIAL_GEJU["化气格"]["description"],
        }

    # 7b. 从格：日主极弱或极旺的简单判断
    #     这里做基础判断 —— 如果旺衰结论包含"极"字或四柱无印无比劫（身弱从格）
    #     实际从格判定更复杂，此处仅作标注提示
    if "极" in wangshuai_conclusion:
        if special_geju is None:
            special_geju = {}
        special_geju["从格提示"] = {
            "type": "从格",
            "description": SPECIAL_GEJU["从格"]["description"],
            "condition": SPECIAL_GEJU["从格"]["condition"],
            "说明": f"旺衰结论为「{wangshuai_conclusion}」，可能构成从格，需结合全局详细判断",
        }

    # ---- 8. 返回结果 ----
    result = {
        "geju_type": geju_type,
        "geju_source": geju_source,
        "geju_shishen": geju_shishen,
        "geju_source_ganzhi": geju_source_ganzhi,
        "xi_ji": xi_ji,
        "special_geju": special_geju,
        "full_description": full_desc,
    }

    return result