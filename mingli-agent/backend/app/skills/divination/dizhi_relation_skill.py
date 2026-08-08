"""
命理地支关系计算模块

纯 Python 实现，无外部依赖。
涵盖：六合（三合局）、六冲、三刑、六害、六破。
"""

from typing import List, Dict, Tuple

# ============================================================
# 常量定义
# ============================================================

# 十二地支
DIZHI_ALL = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 四柱位置名称
PILLAR_NAMES = ["年", "月", "日", "时"]

# 四柱位置两两组合的名称映射：(i, j) -> "年月" / "月日" / ...
LOCATION_MAP: Dict[Tuple[int, int], str] = {
    (0, 1): "年月",
    (0, 2): "年日",
    (0, 3): "年时",
    (1, 2): "月日",
    (1, 3): "月时",
    (2, 3): "日时",
}

# ----------------------------------------------------------
# 三合局（六合）
# ----------------------------------------------------------
# 全合局: 三字齐全；半合局: 取相邻两字
# 每条记录: (地支三元组, 局名, 五行)
SAN_HE_JU = [
    ("申子辰", "水局", "水"),
    ("寅午戌", "火局", "火"),
    ("巳酉丑", "金局", "金"),
    ("亥卯未", "木局", "木"),
]

# 从全合局推导出所有半合对
# 半合取三元组中相邻的两字（首中、中尾）
BAN_HE_PAIRS: List[Tuple[str, str, str, str]] = []  # (dz1, dz2, 半合类型, 五行)
for _tri_str, _ju_name, _wuxing in SAN_HE_JU:
    _tri = list(_tri_str)
    BAN_HE_PAIRS.append((_tri[0], _tri[1], f"半合{_ju_name}", _wuxing))
    BAN_HE_PAIRS.append((_tri[1], _tri[2], f"半合{_ju_name}", _wuxing))

# 辰丑半合（湿土，无特定局）
BAN_HE_PAIRS.append(("辰", "丑", "半合湿土", "土"))

# 全合局查找表: frozenset(三地支) -> (局名, 五行)
QUAN_HE_MAP: Dict[frozenset, Tuple[str, str]] = {
    frozenset(list(tri_str)): (ju_name, wuxing)
    for tri_str, ju_name, wuxing in SAN_HE_JU
}

# 半合查找表: frozenset(两地支) -> (半合类型, 五行)
BAN_HE_MAP: Dict[frozenset, Tuple[str, str]] = {
    frozenset([dz1, dz2]): (he_type, wx)
    for dz1, dz2, he_type, wx in BAN_HE_PAIRS
}

# ----------------------------------------------------------
# 六冲
# ----------------------------------------------------------
LIU_CHONG_PAIRS: List[Tuple[str, str]] = [
    ("子", "午"),
    ("丑", "未"),
    ("寅", "申"),
    ("卯", "酉"),
    ("辰", "戌"),
    ("巳", "亥"),
]

LIU_CHONG_SET = frozenset(
    frozenset(pair) for pair in LIU_CHONG_PAIRS
)

# ----------------------------------------------------------
# 三刑
# ----------------------------------------------------------
# 无恩之刑、恃势之刑为三字刑；无礼之刑为两字刑；自刑为单字
SAN_XING_TRIPLE: List[Tuple[str, str, str, str]] = [
    # (dz1, dz2, dz3, 刑名)
    ("寅", "巳", "申", "无恩之刑"),
    ("丑", "戌", "未", "恃势之刑"),
]

SAN_XING_DOUBLE: List[Tuple[str, str, str]] = [
    # (dz1, dz2, 刑名)
    ("子", "卯", "无礼之刑"),
]

SAN_XING_SELF: List[Tuple[str, str]] = [
    # (地支, 刑名)
    ("辰", "自刑"),
    ("午", "自刑"),
    ("酉", "自刑"),
    ("亥", "自刑"),
]

# 三字刑查找表
SAN_XING_TRIPLE_MAP: Dict[frozenset, str] = {
    frozenset([dz1, dz2, dz3]): name
    for dz1, dz2, dz3, name in SAN_XING_TRIPLE
}

# 两字刑查找表
SAN_XING_DOUBLE_MAP: Dict[frozenset, str] = {
    frozenset([dz1, dz2]): name
    for dz1, dz2, name in SAN_XING_DOUBLE
}

# 自刑查找表
SAN_XING_SELF_SET: Dict[str, str] = {
    dz: name for dz, name in SAN_XING_SELF
}

# ----------------------------------------------------------
# 六害
# ----------------------------------------------------------
LIU_HAI_PAIRS: List[Tuple[str, str]] = [
    ("子", "未"),
    ("丑", "午"),
    ("寅", "巳"),
    ("卯", "辰"),
    ("申", "亥"),
    ("酉", "戌"),
]

LIU_HAI_SET = frozenset(
    frozenset(pair) for pair in LIU_HAI_PAIRS
)

# ----------------------------------------------------------
# 六破
# ----------------------------------------------------------
LIU_PO_PAIRS: List[Tuple[str, str]] = [
    ("子", "酉"),
    ("丑", "辰"),
    ("寅", "亥"),
    ("卯", "午"),
    ("巳", "申"),
    ("未", "戌"),
]

LIU_PO_SET = frozenset(
    frozenset(pair) for pair in LIU_PO_PAIRS
)


# ============================================================
# 辅助函数
# ============================================================

def _get_location(indices: List[int]) -> str:
    """根据地支在四柱中的索引位置，生成中文位置描述。"""
    if len(indices) == 2:
        key = (min(indices), max(indices))
        return LOCATION_MAP.get(key, "")
    elif len(indices) == 3:
        # 三字关系：列出所有两两位置，用顿号连接
        parts = []
        sorted_indices = sorted(indices)
        for i in range(len(sorted_indices)):
            for j in range(i + 1, len(sorted_indices)):
                key = (sorted_indices[i], sorted_indices[j])
                parts.append(LOCATION_MAP.get(key, ""))
        return "、".join(parts)
    return ""


def _format_dizhi_pair(dz1: str, dz2: str) -> str:
    """格式化两个地支为 '子午' 形式。"""
    return dz1 + dz2


# ============================================================
# 核心分析函数
# ============================================================

def analyze_dizhi_relations(dizhi_list: List[str]) -> Dict:
    """
    分析四个地支之间的关系。

    Args:
        dizhi_list: [年支, 月支, 日支, 时支]，长度必须为 4。

    Returns:
        {
            "六合": [{"type": "半合水局", "dizhi": ["子","辰"], "location": "年时", "wuxing": "水"}],
            "六冲": [{"dizhi": ["子","午"], "location": "年月"}],
            "三刑": [{"type": "无恩之刑", "dizhi": ["寅","巳","申"], "location": "年月时"}],
            "六害": [{"dizhi": ["卯","辰"], "location": "日时"}],
            "六破": [{"dizhi": ["子","酉"], "location": "年时"}],
            "summary": "子辰半合水局、寅巳申无恩之刑、卯辰相害..."
        }
    """
    if len(dizhi_list) != 4:
        raise ValueError(f"dizhi_list 长度必须为 4，当前为 {len(dizhi_list)}")

    result: Dict = {
        "六合": [],
        "六冲": [],
        "三刑": [],
        "六害": [],
        "六破": [],
        "summary": "",
    }

    summary_parts: List[str] = []

    # --------------------------------------------------
    # 1. 六合（三合局）：先检测全合，再检测半合
    # --------------------------------------------------
    # 收集所有已参与全合的地支索引，避免重复计入半合
    quan_he_used_indices: set = set()

    # 检测全合局
    for tri_chars, (ju_name, wuxing) in QUAN_HE_MAP.items():
        matched_indices = []
        for idx, dz in enumerate(dizhi_list):
            if dz in tri_chars:
                matched_indices.append(idx)
        if len(matched_indices) == 3:
            # 确认这三个地支恰好构成该三合局
            matched_dz_set = frozenset(dizhi_list[i] for i in matched_indices)
            if matched_dz_set == tri_chars:
                location = _get_location(matched_indices)
                dz_sorted = sorted(matched_dz_set, key=lambda d: DIZHI_ALL.index(d))
                entry = {
                    "type": f"全合{ju_name}",
                    "dizhi": dz_sorted,
                    "location": location,
                    "wuxing": wuxing,
                }
                result["六合"].append(entry)
                summary_parts.append(f"{''.join(dz_sorted)}全合{ju_name}")
                quan_he_used_indices.update(matched_indices)

    # 检测半合局（排除已参与全合的地支）
    for pair_set, (he_type, wuxing) in BAN_HE_MAP.items():
        pair_list = list(pair_set)
        matched_indices = []
        for idx, dz in enumerate(dizhi_list):
            if dz in pair_set and idx not in quan_he_used_indices:
                matched_indices.append(idx)
        if len(matched_indices) == 2:
            matched_dz_set = frozenset(dizhi_list[i] for i in matched_indices)
            if matched_dz_set == pair_set:
                location = _get_location(matched_indices)
                dz_sorted = sorted(matched_dz_set, key=lambda d: DIZHI_ALL.index(d))
                entry = {
                    "type": he_type,
                    "dizhi": dz_sorted,
                    "location": location,
                    "wuxing": wuxing,
                }
                result["六合"].append(entry)
                summary_parts.append(f"{''.join(dz_sorted)}{he_type}")

    # --------------------------------------------------
    # 2. 六冲
    # --------------------------------------------------
    for i in range(4):
        for j in range(i + 1, 4):
            pair = frozenset([dizhi_list[i], dizhi_list[j]])
            if pair in LIU_CHONG_SET:
                location = _get_location([i, j])
                dz_sorted = sorted(pair, key=lambda d: DIZHI_ALL.index(d))
                entry = {
                    "dizhi": dz_sorted,
                    "location": location,
                }
                result["六冲"].append(entry)
                summary_parts.append(f"{''.join(dz_sorted)}相冲")

    # --------------------------------------------------
    # 3. 三刑
    # --------------------------------------------------
    # 三字刑
    for tri_set, xing_name in SAN_XING_TRIPLE_MAP.items():
        matched_indices = []
        for idx, dz in enumerate(dizhi_list):
            if dz in tri_set:
                matched_indices.append(idx)
        if len(matched_indices) == 3:
            matched_dz_set = frozenset(dizhi_list[i] for i in matched_indices)
            if matched_dz_set == tri_set:
                location = _get_location(matched_indices)
                dz_sorted = sorted(matched_dz_set, key=lambda d: DIZHI_ALL.index(d))
                entry = {
                    "type": xing_name,
                    "dizhi": dz_sorted,
                    "location": location,
                }
                result["三刑"].append(entry)
                summary_parts.append(f"{''.join(dz_sorted)}{xing_name}")

    # 两字刑
    for pair_set, xing_name in SAN_XING_DOUBLE_MAP.items():
        for i in range(4):
            for j in range(i + 1, 4):
                pair = frozenset([dizhi_list[i], dizhi_list[j]])
                if pair == pair_set:
                    location = _get_location([i, j])
                    dz_sorted = sorted(pair, key=lambda d: DIZHI_ALL.index(d))
                    entry = {
                        "type": xing_name,
                        "dizhi": dz_sorted,
                        "location": location,
                    }
                    result["三刑"].append(entry)
                    summary_parts.append(f"{''.join(dz_sorted)}{xing_name}")

    # 自刑
    for dz, xing_name in SAN_XING_SELF_SET.items():
        indices = [idx for idx, d in enumerate(dizhi_list) if d == dz]
        if len(indices) >= 2:
            # 自刑需要至少两个相同地支
            location = _get_location(indices[:2])
            entry = {
                "type": xing_name,
                "dizhi": [dz, dz],
                "location": location,
            }
            result["三刑"].append(entry)
            summary_parts.append(f"{dz}{dz}{xing_name}")

    # --------------------------------------------------
    # 4. 六害
    # --------------------------------------------------
    for i in range(4):
        for j in range(i + 1, 4):
            pair = frozenset([dizhi_list[i], dizhi_list[j]])
            if pair in LIU_HAI_SET:
                location = _get_location([i, j])
                dz_sorted = sorted(pair, key=lambda d: DIZHI_ALL.index(d))
                entry = {
                    "dizhi": dz_sorted,
                    "location": location,
                }
                result["六害"].append(entry)
                summary_parts.append(f"{''.join(dz_sorted)}相害")

    # --------------------------------------------------
    # 5. 六破
    # --------------------------------------------------
    for i in range(4):
        for j in range(i + 1, 4):
            pair = frozenset([dizhi_list[i], dizhi_list[j]])
            if pair in LIU_PO_SET:
                location = _get_location([i, j])
                dz_sorted = sorted(pair, key=lambda d: DIZHI_ALL.index(d))
                entry = {
                    "dizhi": dz_sorted,
                    "location": location,
                }
                result["六破"].append(entry)
                summary_parts.append(f"{''.join(dz_sorted)}相破")

    # --------------------------------------------------
    # 生成摘要
    # --------------------------------------------------
    result["summary"] = "、".join(summary_parts) if summary_parts else ""

    return result