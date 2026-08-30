"""
神煞计算模块

基于日柱/年柱/月柱的天干地支，计算各柱对应的神煞。
神煞是纯规则计算，不涉及LLM。
"""
from typing import Dict, List, Optional


# ==================== 常量定义 ====================

TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 地支三合局（用于驿马、桃花、华盖等）
SAN_HE_GROUPS = {
    "申子辰": "水",
    "亥卯未": "木",
    "寅午戌": "火",
    "巳酉丑": "金",
}

# 驿马：三合局第一个地支的冲位
YIMA_MAP = {
    "申": "寅", "子": "寅", "辰": "寅",  # 申子辰 → 寅
    "亥": "巳", "卯": "巳", "未": "巳",  # 亥卯未 → 巳
    "寅": "申", "午": "申", "戌": "申",  # 寅午戌 → 申
    "巳": "亥", "酉": "亥", "丑": "亥",  # 巳酉丑 → 亥
}

# 桃花（咸池）：三合局第一个地支的沐浴位（即三合局帝旺的前一位）
TAOHUA_MAP = {
    "申": "酉", "子": "酉", "辰": "酉",  # 申子辰 → 酉
    "亥": "子", "卯": "子", "未": "子",  # 亥卯未 → 子
    "寅": "卯", "午": "卯", "戌": "卯",  # 寅午戌 → 卯
    "巳": "午", "酉": "午", "丑": "午",  # 巳酉丑 → 午
}

# 华盖：三合局最后一个地支（墓库位）
HUAGAI_MAP = {
    "申": "辰", "子": "辰", "辰": "辰",  # 申子辰 → 辰
    "亥": "未", "卯": "未", "未": "未",  # 亥卯未 → 未
    "寅": "戌", "午": "戌", "戌": "戌",  # 寅午戌 → 戌
    "巳": "丑", "酉": "丑", "丑": "丑",  # 巳酉丑 → 丑
}

# 天乙贵人：基于日干
TIANYI_GUIREN_MAP = {
    "甲": ["丑", "未"],
    "乙": ["子", "申"],
    "丙": ["亥", "酉"],
    "丁": ["亥", "酉"],
    "戊": ["丑", "未"],
    "己": ["子", "申"],
    "庚": ["丑", "未"],
    "辛": ["寅", "午"],
    "壬": ["卯", "巳"],
    "癸": ["卯", "巳"],
}

# 文昌贵人：基于日干
WENCHANG_MAP = {
    "甲": "巳", "乙": "午", "丙": "申", "丁": "酉",
    "戊": "申", "己": "酉", "庚": "亥", "辛": "子",
    "壬": "寅", "癸": "卯",
}

# 国印贵人：基于日干
GUOYIN_MAP = {
    "甲": "戌", "乙": "亥", "丙": "丑", "丁": "寅",
    "戊": "丑", "己": "寅", "庚": "辰", "辛": "巳",
    "壬": "未", "癸": "申",
}

# 天医：基于月支（前一位地支）
TIANYI_MAP = {
    "子": "亥", "丑": "子", "寅": "丑", "卯": "寅",
    "辰": "卯", "巳": "辰", "午": "巳", "未": "午",
    "申": "未", "酉": "申", "戌": "酉", "亥": "戌",
}

# 太极贵人：基于日干
TAIJI_MAP = {
    "甲": ["子", "午"],
    "乙": ["子", "午"],
    "丙": ["卯", "酉"],
    "丁": ["卯", "酉"],
    "戊": ["辰", "戌", "丑", "未"],
    "己": ["辰", "戌", "丑", "未"],
    "庚": ["寅", "申"],
    "辛": ["寅", "申"],
    "壬": ["巳", "亥"],
    "癸": ["巳", "亥"],
}

# 六厄：基于年支
LIUE_MAP = {
    "子": "卯", "丑": "子", "寅": "酉", "卯": "午",
    "辰": "卯", "巳": "子", "午": "酉", "未": "午",
    "申": "卯", "酉": "子", "戌": "酉", "亥": "午",
}

# 将星：基于年支/日支（三合局帝旺位）
JIANGXING_MAP = {
    "申": "子", "子": "子", "辰": "子",  # 申子辰 → 子
    "亥": "卯", "卯": "卯", "未": "卯",  # 亥卯未 → 卯
    "寅": "午", "午": "午", "戌": "午",  # 寅午戌 → 午
    "巳": "酉", "酉": "酉", "丑": "酉",  # 巳酉丑 → 酉
}

# 十恶大败日（日柱）
SHIE_DABAI_DAYS = [
    "甲辰", "乙巳", "丙申", "丁亥", "戊戌",
    "己丑", "庚辰", "辛巳", "壬申", "癸亥",
]

# 童子煞：春秋寅子贵，冬夏卯未辰
# 春（寅卯辰月）→ 寅子
# 夏（巳午未月）→ 卯未
# 秋（申酉戌月）→ 寅子
# 冬（亥子丑月）→ 卯未辰
TONGZI_MAP = {
    "寅": ["寅", "子"], "卯": ["寅", "子"], "辰": ["寅", "子"],  # 春
    "巳": ["卯", "未"], "午": ["卯", "未"], "未": ["卯", "未"],  # 夏
    "申": ["寅", "子"], "酉": ["寅", "子"], "戌": ["寅", "子"],  # 秋
    "亥": ["卯", "未", "辰"], "子": ["卯", "未", "辰"], "丑": ["卯", "未", "辰"],  # 冬
}

# 天干五合
TIANGAN_WUHE = {
    ("甲", "己"): "土",
    ("乙", "庚"): "金",
    ("丙", "辛"): "水",
    ("丁", "壬"): "木",
    ("戊", "癸"): "火",
}

# 月德贵人：基于月支查天干（修正版）
YUEDE_MAP = {
    "寅": "丙", "卯": "甲", "辰": "壬", "巳": "庚",
    "午": "丙", "未": "甲", "申": "壬", "酉": "庚",
    "戌": "丙", "亥": "甲", "子": "壬", "丑": "庚",
}

# 月德合：基于月支查天干（月德天干的六合干）
YUEDE_HE_MAP = {
    "寅": "辛", "卯": "己", "辰": "丁", "巳": "乙",
    "午": "辛", "未": "己", "申": "丁", "酉": "乙",
    "戌": "辛", "亥": "己", "子": "丁", "丑": "乙",
}

# 红鸾：基于年支查
HONGLUAN_MAP = {
    "子": "卯", "丑": "寅", "寅": "丑", "卯": "子",
    "辰": "亥", "巳": "戌", "午": "酉", "未": "申",
    "申": "未", "酉": "午", "戌": "巳", "亥": "辰",
}

# 天喜：基于年支查（红鸾对宫）
TIANXI_MAP = {
    "子": "酉", "丑": "申", "寅": "未", "卯": "午",
    "辰": "巳", "巳": "辰", "午": "卯", "未": "寅",
    "申": "丑", "酉": "子", "戌": "亥", "亥": "戌",
}

# 孤辰：基于年支查
GUCHEN_MAP = {
    "子": "寅", "丑": "寅", "寅": "巳", "卯": "巳",
    "辰": "巳", "巳": "申", "午": "申", "未": "申",
    "申": "亥", "酉": "亥", "戌": "亥", "亥": "寅",
}

# 寡宿：基于年支查
GUASU_MAP = {
    "子": "戌", "丑": "戌", "寅": "丑", "卯": "丑",
    "辰": "丑", "巳": "辰", "午": "辰", "未": "辰",
    "申": "未", "酉": "未", "戌": "未", "亥": "戌",
}

# 元辰（大耗）：基于年支查，阳年顺数5位，阴年逆数5位
# 阳年(甲丙戊庚壬): 子→巳, 丑→午, 寅→未, 卯→申, 辰→酉, 巳→戌, 午→亥, 未→子, 申→丑, 酉→寅, 戌→卯, 亥→辰
# 阴年(乙丁己辛癸): 子→未, 丑→申, 寅→酉, 卯→戌, 辰→亥, 巳→子, 午→丑, 未→寅, 申→卯, 酉→辰, 戌→巳, 亥→午
YUANCHEN_YANG_MAP = {
    "子": "巳", "丑": "午", "寅": "未", "卯": "申",
    "辰": "酉", "巳": "戌", "午": "亥", "未": "子",
    "申": "丑", "酉": "寅", "戌": "卯", "亥": "辰",
}
YUANCHEN_YIN_MAP = {
    "子": "未", "丑": "申", "寅": "酉", "卯": "戌",
    "辰": "亥", "巳": "子", "午": "丑", "未": "寅",
    "申": "卯", "酉": "辰", "戌": "巳", "亥": "午",
}
YANG_TIANGAN = {"甲", "丙", "戊", "庚", "壬"}

# 福星贵人：基于日干查
FUXING_MAP = {
    "甲": "寅", "乙": "丑", "丙": "子", "丁": "酉",
    "戊": "申", "己": "未", "庚": "午", "辛": "巳",
    "壬": "辰", "癸": "卯",
}

# 十灵日：特定日柱
SHILING_DAYS = ["甲辰", "乙亥", "丙辰", "丁酉", "戊午", "庚寅", "庚戌", "辛亥", "壬寅", "癸未"]

# 六秀日：特定日柱
LIUXIU_DAYS = ["丙午", "丁巳", "戊午", "己巳", "庚戌", "辛亥"]

# 金舆：基于日干查地支（修正版）
JINYU_MAP = {
    "甲": "辰", "乙": "巳", "丙": "未", "丁": "申",
    "戊": "未", "己": "申", "庚": "戌", "辛": "亥",
    "壬": "丑", "癸": "寅",
}

# 德秀贵人：基于月支查天干（《三命通会》规则，含德+秀）
# 寅午戌月：丙丁为德，戊癸为秀
# 申子辰月：壬癸戊己为德，丙辛甲己为秀
# 巳酉丑月：庚辛为德，乙庚为秀
# 亥卯未月：甲乙为德，丁壬为秀
DEXIU_MONTH_MAP = {
    "寅": ["丙", "丁", "戊", "癸"], "午": ["丙", "丁", "戊", "癸"], "戌": ["丙", "丁", "戊", "癸"],
    "申": ["壬", "癸", "戊", "己", "丙", "辛", "甲"], "子": ["壬", "癸", "戊", "己", "丙", "辛", "甲"], "辰": ["壬", "癸", "戊", "己", "丙", "辛", "甲"],
    "巳": ["庚", "辛", "乙"], "酉": ["庚", "辛", "乙"], "丑": ["庚", "辛", "乙"],
    "亥": ["甲", "乙", "丁", "壬"], "卯": ["甲", "乙", "丁", "壬"], "未": ["甲", "乙", "丁", "壬"],
}

# 天德贵人：基于月支查天干或地支
TIANDE_MAP = {
    "寅": "丁", "卯": "申", "辰": "壬", "巳": "辛",
    "午": "亥", "未": "甲", "申": "癸", "酉": "寅",
    "戌": "丙", "亥": "乙", "子": "巳", "丑": "庚",
}

# 亡神：基于年支或日支查（三合局前一位）
WANGSHEN_MAP = {
    "申": "巳", "子": "巳", "辰": "巳",  # 申子辰 → 巳
    "亥": "寅", "卯": "寅", "未": "寅",  # 亥卯未 → 寅
    "寅": "亥", "午": "亥", "戌": "亥",  # 寅午戌 → 亥
    "巳": "申", "酉": "申", "丑": "申",  # 巳酉丑 → 申
}

# 劫煞：基于年支或日支查（三合局绝位）
JIESHA_MAP = {
    "申": "巳", "子": "巳", "辰": "巳",  # 申子辰 → 巳
    "亥": "申", "卯": "申", "未": "申",  # 亥卯未 → 申
    "寅": "亥", "午": "亥", "戌": "亥",  # 寅午戌 → 亥
    "巳": "寅", "酉": "寅", "丑": "寅",  # 巳酉丑 → 寅
}

# 羊刃：基于日干查
YANGREN_MAP = {
    "甲": "卯", "乙": "寅", "丙": "午", "丁": "巳",
    "戊": "午", "己": "巳", "庚": "酉", "辛": "申",
    "壬": "子", "癸": "亥",
}

# 学堂：基于日干查
XUETANG_MAP = {
    "甲": "亥", "乙": "午", "丙": "寅", "丁": "酉",
    "戊": "寅", "己": "巳", "庚": "巳", "辛": "子",
    "壬": "申", "癸": "卯",
}

# 勾绞：基于日干查
GOUJIAO_MAP = {
    "甲": ["酉", "卯"], "乙": ["申", "寅"], "丙": ["子", "午"],
    "丁": ["亥", "巳"], "戊": ["子", "午"], "己": ["亥", "巳"],
    "庚": ["卯", "酉"], "辛": ["寅", "申"], "壬": ["午", "子"],
    "癸": ["巳", "亥"],
}


# ==================== 核心计算函数 ====================

def _get_san_he_group(di: str) -> Optional[str]:
    """获取地支所属的三合局组"""
    for group in SAN_HE_GROUPS:
        if di in group:
            return group
    return None


def calculate_shensha(
    pillars: Dict[str, Dict[str, str]],
    day_tian: str,
    day_di: str,
    month_di: str,
    year_di: str,
    year_tian: str,
    year_nayin: str,
    kongwang: Optional[List[str]] = None,
) -> Dict[str, List[str]]:
    """
    计算四柱神煞

    返回格式：{"year": ["神煞1", "神煞2"], "month": [...], "day": [...], "hour": [...]}
    
    支持中英文键：pillars 可以用 "年"/"year" 等键
    """
    # 键名映射（中文 → 英文）
    KEY_MAP = {"年": "year", "月": "month", "日": "day", "时": "hour"}
    
    # 统一转换为英文键
    en_pillars = {}
    for k, v in pillars.items():
        en_key = KEY_MAP.get(k, k)
        en_pillars[en_key] = v

    # 纳音五行映射（用于童子煞）
    NAYIN_WUXING = {
        "海中金": "金", "剑锋金": "金", "白蜡金": "金", "沙中金": "金", "钏金": "金",
        "炉中火": "火", "山头火": "火", "霹雳火": "火", "山下火": "火", "天上火": "火",
        "大林木": "木", "杨柳木": "木", "松柏木": "木", "平地木": "木", "桑柘木": "木",
        "涧下水": "水", "泉中水": "水", "长流水": "水", "天河水": "水", "大海水": "水",
        "路旁土": "土", "城头土": "土", "屋上土": "土", "壁上土": "土", "大驿土": "土",
    }
    # 纳音五行 → 童子煞目标地支
    NAYIN_TONGZI = {
        "金": ["子", "卯"],
        "木": ["巳", "午"],
        "水": ["辰", "戌"],
        "火": ["卯", "酉"],
        "土": ["子", "卯"],
    }

    result: Dict[str, List[str]] = {
        "year": [],
        "month": [],
        "day": [],
        "hour": [],
    }

    # 德秀贵人判断：如果月干本身在该月对应的德秀天干列表中，则四柱全部标注德秀贵人（与测测App对齐）
    dexiu_tians = DEXIU_MONTH_MAP.get(month_di, [])
    month_tian = en_pillars["month"]["tian"]
    has_dexiu = month_tian in dexiu_tians

    # 遍历每一柱，计算该柱地支对应的神煞
    for pos in ["year", "month", "day", "hour"]:
        di = en_pillars[pos]["di"]
        tian = en_pillars[pos]["tian"]
        shensha_list: List[str] = []

        # 1. 驿马（以年支或日支查）
        if YIMA_MAP.get(year_di) == di or YIMA_MAP.get(day_di) == di:
            shensha_list.append("驿马")

        # 2. 桃花（以年支或日支查）
        if TAOHUA_MAP.get(year_di) == di or TAOHUA_MAP.get(day_di) == di:
            shensha_list.append("桃花")

        # 3. 华盖（以年支或日支查）
        if HUAGAI_MAP.get(year_di) == di or HUAGAI_MAP.get(day_di) == di:
            shensha_list.append("华盖")

        # 4. 天乙贵人（以日干和年干查）
        day_gui = TIANYI_GUIREN_MAP.get(day_tian, [])
        year_gui = TIANYI_GUIREN_MAP.get(year_tian, [])
        if di in day_gui or di in year_gui:
            shensha_list.append("天乙贵人")

        # 5. 文昌贵人（以日干查）
        if WENCHANG_MAP.get(day_tian) == di:
            shensha_list.append("文昌贵人")

        # 6. 国印贵人（仅时柱以当前柱天干查）
        if pos == "hour" and GUOYIN_MAP.get(tian) == di:
            shensha_list.append("国印")

        # 7. 天医（以月支查）
        if TIANYI_MAP.get(month_di) == di:
            shensha_list.append("天医")

        # 8. 太极贵人（以日干和年干查，同时考虑纳音）
        day_taiji = TAIJI_MAP.get(day_tian, [])
        year_taiji = TAIJI_MAP.get(year_tian, [])
        if di in day_taiji or di in year_taiji:
            shensha_list.append("太极贵人")
        
        # 8b. 太极贵人补充：基于年柱纳音五行（与测测App对齐）
        NAYIN_TAIJI = {
            "金": ["寅", "申"], "木": ["子", "午"],
            "水": ["卯", "酉"], "火": ["辰", "戌"],
            "土": ["丑", "未"],
        }
        nayin_wx = NAYIN_WUXING.get(year_nayin, "")
        nayin_taiji = NAYIN_TAIJI.get(nayin_wx, [])
        if di in nayin_taiji and "太极贵人" not in shensha_list:
            shensha_list.append("太极贵人")

        # 9. 六厄（以年支查）
        if LIUE_MAP.get(year_di) == di:
            shensha_list.append("六厄")

        # 10. 将星（以年支或日支查）
        if JIANGXING_MAP.get(year_di) == di or JIANGXING_MAP.get(day_di) == di:
            shensha_list.append("将星")

        # 11. 空亡（以日柱旬查）
        if kongwang and di in kongwang:
            shensha_list.append("空亡")

        # 12. 十恶大败（仅日柱）
        if pos == "day" and f"{day_tian}{day_di}" in SHIE_DABAI_DAYS:
            shensha_list.append("十恶大败")

        # 13. 童子煞（以年柱纳音查，仅日柱和时柱）
        if pos in ["day", "hour"]:
            nayin_wx = NAYIN_WUXING.get(year_nayin, "")
            tongzi_targets = NAYIN_TONGZI.get(nayin_wx, [])
            if di in tongzi_targets:
                shensha_list.append("童子")

        # 14. 五行正印（以日干查）
        ZHENG_YIN_MAP = {
            "甲": "子", "乙": "亥", "丙": "卯", "丁": "寅",
            "戊": "午", "己": "巳", "庚": "丑", "辛": "辰",
            "壬": "酉", "癸": "申",
        }
        if ZHENG_YIN_MAP.get(day_tian) == di:
            shensha_list.append("五行正印")

        # 15. 月德贵人（以月支查天干，匹配四柱天干）
        yuede_tian = YUEDE_MAP.get(month_di, "")
        if yuede_tian and tian == yuede_tian:
            shensha_list.append("月德贵人")

        # 16. 天德贵人（以月支查天干/地支）
        tiande = TIANDE_MAP.get(month_di, "")
        if tiande and (tian == tiande or di == tiande):
            shensha_list.append("天德")

        # 17. 金舆（以日干查）
        if JINYU_MAP.get(day_tian) == di:
            shensha_list.append("金舆")

        # 18. 亡神（以年支或日支查，仅年柱和月柱）
        if pos in ["year", "month"]:
            if WANGSHEN_MAP.get(year_di) == di or WANGSHEN_MAP.get(day_di) == di:
                shensha_list.append("亡神")

        # 19. 劫煞（以年支或日支查）
        if JIESHA_MAP.get(year_di) == di or JIESHA_MAP.get(day_di) == di:
            shensha_list.append("劫煞")

        # 20. 羊刃（以日干查，不限柱位）
        if YANGREN_MAP.get(day_tian) == di:
            shensha_list.append("羊刃")

        # 21. 学堂（以日干查）
        if XUETANG_MAP.get(day_tian) == di:
            shensha_list.append("学堂")

        # 22. 勾绞（以日干查）
        goujiao_targets = GOUJIAO_MAP.get(day_tian, [])
        if isinstance(goujiao_targets, list):
            if di in goujiao_targets:
                shensha_list.append("勾绞")
        elif goujiao_targets == di:
            shensha_list.append("勾绞")

        # 23. 德秀贵人（全局判断：四柱任一柱天干满足条件，则全部标注）
        if has_dexiu:
            shensha_list.append("德秀贵人")

        # 24. 金神（以日干查，仅日柱）
        JINSHEN_DAYS = ["乙丑", "己巳", "癸酉"]
        if pos == "day" and f"{day_tian}{day_di}" in JINSHEN_DAYS:
            shensha_list.append("金神")

        # 25. 红鸾（以年支查）
        if HONGLUAN_MAP.get(year_di) == di:
            shensha_list.append("红鸾")

        # 26. 天喜（以年支查）
        if TIANXI_MAP.get(year_di) == di:
            shensha_list.append("天喜")

        # 27. 孤辰（以年支查）
        if GUCHEN_MAP.get(year_di) == di:
            shensha_list.append("孤辰")

        # 28. 寡宿（以年支查）
        if GUASU_MAP.get(year_di) == di:
            shensha_list.append("寡宿")

        # 29. 元辰（以年支查，阳年顺数5位，阴年逆数5位）
        if year_tian in YANG_TIANGAN:
            yuanchen_target = YUANCHEN_YANG_MAP.get(year_di)
        else:
            yuanchen_target = YUANCHEN_YIN_MAP.get(year_di)
        if yuanchen_target == di:
            shensha_list.append("元辰")

        # 30. 月德合（以月支查天干，匹配当前柱天干）
        yuede_he_tian = YUEDE_HE_MAP.get(month_di, "")
        if yuede_he_tian and tian == yuede_he_tian:
            shensha_list.append("月德合")

        # 31. 福星贵人（以日干查）
        if FUXING_MAP.get(day_tian) == di:
            shensha_list.append("福星贵人")

        # 32. 十灵日（仅日柱）
        if pos == "day" and f"{day_tian}{day_di}" in SHILING_DAYS:
            shensha_list.append("十灵日")

        # 33. 六秀日（仅日柱）
        if pos == "day" and f"{day_tian}{day_di}" in LIUXIU_DAYS:
            shensha_list.append("六秀日")

        result[pos] = shensha_list

    # 将英文键转回中文键，与调用方保持一致
    KEY_MAP_REVERSE = {"year": "年", "month": "月", "day": "日", "hour": "时"}
    return {KEY_MAP_REVERSE[k]: v for k, v in result.items()}


def calculate_tiangan_he(pillars: Dict[str, Dict[str, str]]) -> List[str]:
    """
    计算天干五合（仅展示，不判断是否化气）

    返回格式：["甲己合化土", "丁壬合化木", ...]
    """
    KEY_MAP = {"年": "year", "月": "month", "日": "day", "时": "hour"}
    en_pillars = {}
    for k, v in pillars.items():
        en_key = KEY_MAP.get(k, k)
        en_pillars[en_key] = v

    all_tian = [
        en_pillars["year"]["tian"],
        en_pillars["month"]["tian"],
        en_pillars["day"]["tian"],
        en_pillars["hour"]["tian"],
    ]

    he_list = []
    checked = set()

    for i in range(len(all_tian)):
        for j in range(i + 1, len(all_tian)):
            # 用固定顺序查找：按天干顺序表中的索引排序
            t1, t2 = all_tian[i], all_tian[j]
            idx1 = TIANGAN.index(t1) if t1 in TIANGAN else -1
            idx2 = TIANGAN.index(t2) if t2 in TIANGAN else -1
            if idx1 > idx2:
                t1, t2 = t2, t1
            pair = (t1, t2)
            if pair in checked:
                continue
            if pair in TIANGAN_WUHE:
                hua_wuxing = TIANGAN_WUHE[pair]
                he_list.append(f"{t1}{t2}合化{hua_wuxing}")
                checked.add(pair)

    return he_list
