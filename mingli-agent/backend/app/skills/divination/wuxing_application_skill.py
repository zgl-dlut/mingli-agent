"""
五行应用静态映射模块

提供天干意象描述、五行应用对照、十神心理学转译等静态数据与查询接口。
纯数据映射，不依赖任何外部服务。
"""

from typing import Dict

# ============================================================
# 天干意象映射（十神心理学转译）
# ============================================================

TIANGAN_IMAGERY: Dict[str, Dict] = {
    "甲": {
        "wuxing": "木",
        "yin_yang": "阳",
        "imagery": "参天大树、栋梁之材",
        "personality": "正直刚毅、有领导力、向上攀爬",
        "psychology": "追求成长与成就，有强烈的自我实现需求",
        "health_focus": "肝胆、筋骨、头部",
        "color": "绿色、青色",
    },
    "乙": {
        "wuxing": "木",
        "yin_yang": "阴",
        "imagery": "花草藤蔓、柔韧之木",
        "personality": "温柔灵活、善于变通、外柔内刚",
        "psychology": "适应力强，善于在夹缝中求生存，有艺术天赋",
        "health_focus": "肝胆、神经、颈椎",
        "color": "浅绿、翠绿",
    },
    "丙": {
        "wuxing": "火",
        "yin_yang": "阳",
        "imagery": "太阳之火、光明普照",
        "personality": "热情开朗、光明磊落、乐于助人",
        "psychology": "需要被看见和认可，天生具有感染力和号召力",
        "health_focus": "心脏、眼睛、小肠",
        "color": "红色、橙色",
    },
    "丁": {
        "wuxing": "火",
        "yin_yang": "阴",
        "imagery": "灯烛之火、温暖内敛",
        "personality": "细腻敏感、内心温暖、善于洞察",
        "psychology": "追求深层连接，直觉敏锐，有强烈的内在精神世界",
        "health_focus": "心脏、血液、乳腺",
        "color": "粉色、紫色",
    },
    "戊": {
        "wuxing": "土",
        "yin_yang": "阳",
        "imagery": "高山大地、厚重稳固",
        "personality": "沉稳可靠、包容大度、重信守诺",
        "psychology": "追求安全感和稳定，是团队中的定海神针",
        "health_focus": "脾胃、消化、肌肉",
        "color": "黄色、棕色",
    },
    "己": {
        "wuxing": "土",
        "yin_yang": "阴",
        "imagery": "田园沃土、滋养万物",
        "personality": "谦和包容、细心周到、默默奉献",
        "psychology": "天生具有养育和包容特质，善于创造温馨氛围",
        "health_focus": "脾胃、肠道、皮肤",
        "color": "米黄、咖啡色",
    },
    "庚": {
        "wuxing": "金",
        "yin_yang": "阳",
        "imagery": "刀剑精钢、刚毅果断",
        "personality": "果断勇敢、重义气、执行力强",
        "psychology": "追求效率和结果，有强烈的正义感和变革精神",
        "health_focus": "肺、大肠、呼吸系统",
        "color": "白色、银色",
    },
    "辛": {
        "wuxing": "金",
        "yin_yang": "阴",
        "imagery": "珠宝首饰、精致华美",
        "personality": "精致优雅、追求完美、有审美力",
        "psychology": "注重品质和细节，有强烈的自我价值追求",
        "health_focus": "肺、咽喉、皮肤",
        "color": "白色、金色",
    },
    "壬": {
        "wuxing": "水",
        "yin_yang": "阳",
        "imagery": "江河大海、奔流不息",
        "personality": "聪明智慧、思维开阔、善于交际",
        "psychology": "追求自由和变化，有强烈的好奇心和学习能力",
        "health_focus": "肾、膀胱、泌尿系统",
        "color": "黑色、深蓝",
    },
    "癸": {
        "wuxing": "水",
        "yin_yang": "阴",
        "imagery": "雨露溪流、润物无声",
        "personality": "温柔细腻、直觉敏锐、富有想象力",
        "psychology": "内心丰富敏感，有强烈的感受力和共情能力",
        "health_focus": "肾、生殖系统、内分泌",
        "color": "浅蓝、灰色",
    },
}

# ============================================================
# 五行应用对照表
# ============================================================

WUXING_APPLICATION: Dict[str, Dict] = {
    "金": {
        "industries": "金融、银行、证券、珠宝、五金、机械、汽车、法律、军警",
        "colors": "白色、银色、金色",
        "directions": "西方",
        "season": "秋季",
        "health": "肺、大肠、呼吸系统、皮肤、鼻",
        "lucky_numbers": "4、9",
        "gemstones": "白水晶、银饰、铂金",
    },
    "木": {
        "industries": "教育、出版、文化、木材、家具、服装、医药、农业、环保",
        "colors": "绿色、青色",
        "directions": "东方",
        "season": "春季",
        "health": "肝、胆、筋骨、眼睛、头部",
        "lucky_numbers": "3、8",
        "gemstones": "翡翠、绿幽灵、绿发晶",
    },
    "水": {
        "industries": "物流、贸易、旅游、航运、水利、传媒、广告、咨询、酒类",
        "colors": "黑色、蓝色、灰色",
        "directions": "北方",
        "season": "冬季",
        "health": "肾、膀胱、泌尿系统、生殖系统、耳朵",
        "lucky_numbers": "1、6",
        "gemstones": "黑曜石、海蓝宝、黑碧玺",
    },
    "火": {
        "industries": "互联网、电子、能源、餐饮、娱乐、美容、影视、传媒、光学",
        "colors": "红色、紫色、橙色",
        "directions": "南方",
        "season": "夏季",
        "health": "心脏、小肠、血液循环、眼睛、舌头",
        "lucky_numbers": "2、7",
        "gemstones": "红宝石、石榴石、红珊瑚",
    },
    "土": {
        "industries": "房地产、建筑、农业、矿业、仓储、物业管理、酒店、食品",
        "colors": "黄色、棕色、咖啡色",
        "directions": "中央",
        "season": "四季之交",
        "health": "脾胃、消化系统、肌肉、口腔",
        "lucky_numbers": "5、0",
        "gemstones": "黄水晶、虎眼石、琥珀",
    },
}

# ============================================================
# 十神心理学转译映射
# ============================================================

SHISHEN_PSYCHOLOGY: Dict[str, Dict] = {
    "比肩": {
        "psychology": "独立自主、自我意识强、竞争意识",
        "strength": "有主见、执行力强",
        "weakness": "固执己见、不善合作",
        "life_area": "自我认知、人际关系",
    },
    "劫财": {
        "psychology": "社交能力强、好胜心强、善于争取",
        "strength": "行动力强、敢于冒险",
        "weakness": "容易冲动、财务波动",
        "life_area": "社交、财运",
    },
    "食神": {
        "psychology": "温和善良、有才华、享受生活",
        "strength": "创造力强、口才好、有福气",
        "weakness": "容易懒散、缺乏进取心",
        "life_area": "才华、子女、享受",
    },
    "伤官": {
        "psychology": "聪明叛逆、追求完美、表现欲强",
        "strength": "才华横溢、善于创新、有艺术天赋",
        "weakness": "口无遮拦、容易得罪人",
        "life_area": "才华、表达、感情",
    },
    "正财": {
        "psychology": "务实稳重、勤劳务实、重视物质",
        "strength": "理财能力强、脚踏实地",
        "weakness": "过于保守、缺乏冒险精神",
        "life_area": "财运、事业、配偶(男)",
    },
    "偏财": {
        "psychology": "慷慨大方、善于交际、眼光独到",
        "strength": "商业头脑、人脉广泛",
        "weakness": "感情丰富、容易破财",
        "life_area": "偏财运、社交、异性缘",
    },
    "正官": {
        "psychology": "正直守规、有责任感、追求地位",
        "strength": "自律性强、有管理能力",
        "weakness": "过于拘谨、容易有压力",
        "life_area": "事业、地位、配偶(女)",
    },
    "七杀": {
        "psychology": "果断刚毅、有魄力、追求权力",
        "strength": "执行力强、敢于面对挑战",
        "weakness": "容易焦虑、精神内耗、完美主义",
        "life_area": "事业、权力、压力",
    },
    "正印": {
        "psychology": "仁慈善良、重视学习、有涵养",
        "strength": "学习能力强、有贵人运",
        "weakness": "依赖性强、容易优柔寡断",
        "life_area": "学业、母亲、贵人",
    },
    "偏印": {
        "psychology": "思维独特、直觉敏锐、善于钻研",
        "strength": "有偏门才华、洞察力强",
        "weakness": "容易多疑、性格孤僻",
        "life_area": "偏门才华、直觉、继母",
    },
}

# ============================================================
# 意象关键词到短称的映射（用于日主描述）
# ============================================================

_IMAGERY_SHORT_MAP = {
    "参天大树、栋梁之材": "大树",
    "花草藤蔓、柔韧之木": "花草",
    "太阳之火、光明普照": "太阳",
    "灯烛之火、温暖内敛": "灯烛",
    "高山大地、厚重稳固": "大地",
    "田园沃土、滋养万物": "田园",
    "刀剑精钢、刚毅果断": "刀剑",
    "珠宝首饰、精致华美": "珠宝",
    "江河大海、奔流不息": "江河",
    "雨露溪流、润物无声": "雨露",
}


# ============================================================
# 接口函数
# ============================================================

def get_tiangan_imagery(tiangan: str) -> Dict:
    """获取天干意象描述。

    Args:
        tiangan: 天干字符，如 "甲"、"乙" 等。

    Returns:
        包含 wuxing、yin_yang、imagery、personality、psychology、
        health_focus、color 的字典。若天干不存在则返回空字典。
    """
    return TIANGAN_IMAGERY.get(tiangan, {})


def get_wuxing_application(wuxing: str) -> Dict:
    """获取五行应用对照。

    Args:
        wuxing: 五行名称，如 "金"、"木"、"水"、"火"、"土"。

    Returns:
        包含 industries、colors、directions、season、health、
        lucky_numbers、gemstones 的字典。若五行不存在则返回空字典。
    """
    return WUXING_APPLICATION.get(wuxing, {})


def get_shishen_psychology(shishen: str) -> Dict:
    """获取十神心理学转译。

    Args:
        shishen: 十神名称，如 "比肩"、"食神"、"正官" 等。

    Returns:
        包含 psychology、strength、weakness、life_area 的字典。
        若十神不存在则返回空字典。
    """
    return SHISHEN_PSYCHOLOGY.get(shishen, {})


def get_day_master_description(day_tian: str) -> str:
    """获取日主描述。

    格式: {天干}{五行}（{阴阳}{五行}{意象短称}）
    示例: 己土（阴土田园）

    Args:
        day_tian: 日柱天干字符，如 "己"。

    Returns:
        日主描述字符串。若天干不存在则返回空字符串。
    """
    info = TIANGAN_IMAGERY.get(day_tian)
    if info is None:
        return ""

    wuxing = info["wuxing"]
    yin_yang = info["yin_yang"]
    imagery = info["imagery"]
    short = _IMAGERY_SHORT_MAP.get(imagery, imagery.split("、")[0])

    return f"{day_tian}{wuxing}（{yin_yang}{wuxing}{short}）"
