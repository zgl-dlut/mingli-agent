"""
Skill 编排器 —— 整合所有命理 Skill 的输出，生成完整的第一阶段 JSON 数据。

调用链:
  bazi_service          -> 基础八字排盘
  dizhi_relation_skill  -> 地支关系（六合/六冲/三刑/六害/六破）
  wangshuai_skill       -> 日主旺衰（得令/得地/得势）
  tiaohou_skill         -> 调候用神（穷通宝鉴）
  geju_skill            -> 格局判定（渊海子平）
  dayun_liunian_skill   -> 大运流年解读（可选，导入失败则跳过）
  wuxing_application_skill -> 五行应用 + 天干意象
  astrology_service     -> 占星排盘
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 内部工具函数
# ============================================================

def _convert_pillars_key(pillars_cn: Dict) -> Dict:
    """
    将 bazi_service 返回的中文 key 四柱数据转换为英文 key。

    bazi_service 使用 {"年": ..., "月": ..., "日": ..., "时": ...}
    wangshuai_skill 需要 {"year": ..., "month": ..., "day": ..., "hour": ...}
    """
    key_map = {"年": "year", "月": "month", "日": "day", "时": "hour"}
    return {key_map[k]: v for k, v in pillars_cn.items()}


def _convert_canggan_to_dizhi_key(pillars_cn: Dict, canggan_cn: Dict) -> Dict:
    """
    将藏干数据从「柱位键」转换为「地支键」。

    bazi_service 返回 {"年": [...], "月": [...], ...}（柱位为键）
    wangshuai_skill._calc_de_di 期望 {"子": [...], "丑": [...], ...}（地支为键），
    通过 canggan.get(day_di, []) 查找日支藏干。

    若直接用英文柱位键，get(day_di) 永远命中空列表，导致得地判断完全失效。
    本函数遍历四柱，以地支字符重建键，使旺衰得地判断能正确命中藏干。
    """
    result: Dict = {}
    for pillar_name in ["年", "月", "日", "时"]:
        di = pillars_cn[pillar_name]["di"]
        result[di] = canggan_cn.get(pillar_name, [])
    return result


def _build_shishen_map(day_tian: str, pillars: Dict, canggan: Dict) -> Dict[str, str]:
    """
    构建完整的十神映射，key 为天干字符。

    遍历四柱天干和地支藏干，为每个天干计算其相对于日主的十神。

    Args:
        day_tian: 日主天干
        pillars: 四柱数据（中文 key），格式 {"年": {"tian": "庚", "di": "午"}, ...}
        canggan: 藏干数据（中文 key），格式 {"年": ["癸"], "月": ["己", "辛", "癸"], ...}

    Returns:
        {"庚": "正财", "丙": "正印", "乙": "比肩", ...}
    """
    from app.services.bazi_service import calculate_shishen

    shishen_map: Dict[str, str] = {}
    for key in ["年", "月", "日", "时"]:
        p = pillars[key]
        tian = p["tian"]
        if tian and tian not in shishen_map:
            shishen_map[tian] = calculate_shishen(day_tian, tian)
        # 藏干的十神
        for cg in canggan.get(key, []):
            if cg and cg not in shishen_map:
                shishen_map[cg] = calculate_shishen(day_tian, cg)
    return shishen_map


def _build_shishen_distribution(pillars: Dict, shishen_map: Dict[str, str]) -> str:
    """
    生成十神分布描述字符串。

    Args:
        pillars: 四柱数据（中文 key）
        shishen_map: 天干 -> 十神映射

    Returns:
        "年干正财、月干正印、日干比肩、时干正财"
    """
    pillar_names = {"年": "年干", "月": "月干", "日": "日干", "时": "时干"}
    parts = []
    for key in ["年", "月", "日", "时"]:
        tian = pillars[key]["tian"]
        ss = shishen_map.get(tian, "")
        if key == "日":
            parts.append(f"{pillar_names[key]}日主")
        else:
            parts.append(f"{pillar_names[key]}{ss}")
    return "、".join(parts)


def _build_sizhu_string(pillars: Dict) -> str:
    """
    将四柱数据组装为字符串。

    Args:
        pillars: 四柱数据（中文 key）

    Returns:
        "庚午 丙子 乙巳 庚辰"
    """
    parts = []
    for key in ["年", "月", "日", "时"]:
        p = pillars[key]
        parts.append(p["tian"] + p["di"])
    return " ".join(parts)


def _build_yueling_description(month_di: str) -> str:
    """
    生成月令描述。

    Args:
        month_di: 月令地支

    Returns:
        "子月（仲冬，隆冬水旺，天寒地冻）"
    """
    from app.skills.divination.tiaohou_skill import YUE_LING_CLIMATE

    info = YUE_LING_CLIMATE.get(month_di, {})
    name = info.get("name", "")
    climate = info.get("climate", "")
    return f"{month_di}月（{name}，{climate}）"


def _build_wuxing_application_section(
    yongshen: str, xishen: str, jishen: str
) -> Dict[str, Dict]:
    """
    构建五行应用部分。

    Args:
        yongshen: 用神五行
        xishen: 喜神五行
        jishen: 忌神五行

    Returns:
        {
            "用神_火": {"行业": "...", "色彩": "...", ...},
            "喜神_土": {"行业": "...", "色彩": "...", ...},
        }
    """
    from app.skills.divination.wuxing_application_skill import get_wuxing_application

    result = {}
    for label, wx in [("用神", yongshen), ("喜神", xishen), ("忌神", jishen)]:
        if wx:
            app = get_wuxing_application(wx)
            if app:
                result[f"{label}_{wx}"] = {
                    "行业": app.get("industries", ""),
                    "色彩": app.get("colors", ""),
                    "方向": app.get("directions", ""),
                    "健康": app.get("health", ""),
                    "幸运数字": app.get("lucky_numbers", ""),
                    "宝石": app.get("gemstones", ""),
                }
    return result


def _build_astrology_section(astro_chart) -> Dict[str, Any]:
    """
    构建占星数据部分。

    Args:
        astro_chart: AstrologyChart 实例

    Returns:
        {
            "太阳": "Scorpio",
            "月亮": "Leo",
            "上升": "Sagittarius",
            "元素分布": {...},
            "模式分布": {...},
        }
    """
    result: Dict[str, Any] = {
        "太阳": astro_chart.sun_sign,
        "月亮": astro_chart.moon_sign,
        "上升": astro_chart.ascendant,
        "元素分布": astro_chart.element_distribution,
        "模式分布": astro_chart.mode_distribution,
    }
    return result


# ============================================================
# 主编排函数
# ============================================================

def generate_full_analysis(
    birth_date: str,
    birth_time: str,
    longitude: float,
    latitude: float,
    gender: str,
    location: str,
) -> Dict[str, Any]:
    """
    生成完整的命理分析 JSON（第一阶段输出）。

    整合所有命理 Skill 的计算结果，组装为前端可直接使用的完整 JSON。

    Args:
        birth_date: 出生日期，格式 "1990-11-10"
        birth_time: 出生时间，格式 "08:00"
        longitude: 经度，如 116.4
        latitude: 纬度，如 39.9
        gender: 性别，"男" 或 "女"
        location: 出生地，如 "北京"

    Returns:
        完整的命理分析 JSON 字典，包含四柱、日主、旺衰、格局、调候、
        地支关系、十神、五行、纳音、大运、流年、五行应用、占星数据、生肖等。
    """
    from app.services.bazi_service import (
        calculate_bazi,
        calculate_shishen,
        DIZHI_CANGGAN,
        TIANGAN_WUXING,
        get_zodiac,
    )
    from app.skills.divination.dizhi_relation_skill import analyze_dizhi_relations
    from app.skills.divination.wangshuai_skill import calculate_wangshuai
    from app.skills.divination.tiaohou_skill import calculate_tiaohou
    from app.skills.divination.geju_skill import calculate_geju
    from app.skills.divination.wuxing_application_skill import get_day_master_description
    from app.skills.divination.motto_skill import generate_motto

    # ================================================================
    # 1. 基础八字排盘（根，失败则向上抛出带上下文的异常，由调用方降级）
    # ================================================================
    try:
        bazi = calculate_bazi(birth_date, birth_time, longitude, gender)
    except Exception as e:
        logger.error(
            f"[排盘] 基础八字计算失败 birth_date={birth_date} birth_time={birth_time} "
            f"lng={longitude} gender={gender}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise RuntimeError(
            f"基础排盘失败 birth_date={birth_date} birth_time={birth_time}: {type(e).__name__}: {e}"
        ) from e
    pillars_cn = bazi.pillars          # {"年": {"tian": "庚", "di": "午"}, ...}
    canggan_cn = bazi.canggan          # {"年": ["癸"], "月": ["己", "辛", "癸"], ...}
    wuxing = bazi.wuxing               # {"金": 2, "木": 1, ...}
    nayin = bazi.nayin                 # {"年": "路旁土", ...}
    dayun_list = bazi.dayun            # [{"ganzhi": "癸卯", "start_year": "2020", ...}, ...]
    current_dayun = bazi.current_dayun  # "癸卯" 或 None
    dayun_direction = getattr(bazi, 'dayun_direction', None)  # "顺" 或 "逆"
    start_age = getattr(bazi, 'start_age', None)  # 起运年龄
    kongwang = getattr(bazi, 'kongwang', None)  # 空亡
    changsheng = getattr(bazi, 'changsheng', None)  # 长生十二宫
    shensha = getattr(bazi, 'shensha', None)  # 神煞
    tiangan_he = getattr(bazi, 'tiangan_he', None)  # 天干五合

    day_tian = pillars_cn["日"]["tian"]
    day_di = pillars_cn["日"]["di"]
    month_di = pillars_cn["月"]["di"]

    # 生肖
    birth_year = int(birth_date.split("-")[0])
    zodiac = get_zodiac(birth_year)

    # ================================================================
    # 2. 地支关系（局部容错，失败置空不影响其他 skill）
    # ================================================================
    dizhi_list = [pillars_cn[k]["di"] for k in ["年", "月", "日", "时"]]
    try:
        dizhi_result = analyze_dizhi_relations(dizhi_list)
    except Exception as e:
        logger.warning(f"[排盘] 地支关系计算失败，置空: {type(e).__name__}: {e}", exc_info=True)
        dizhi_result = {"summary": ""}

    # ================================================================
    # 3. 日主旺衰（需要英文 key）
    # ================================================================
    pillars_en = _convert_pillars_key(pillars_cn)
    # 注意：wangshuai_skill 的得地判断用 canggan.get(day_di, []) 查找日支藏干，
    # key 必须是地支字符，而非英文柱位。
    canggan_dizhi = _convert_canggan_to_dizhi_key(pillars_cn, canggan_cn)

    # 构建完整的十神映射（天干 -> 十神），供 wangshuai_skill 使用
    shishen_map = _build_shishen_map(day_tian, pillars_cn, canggan_cn)

    try:
        wangshuai_result = calculate_wangshuai(
            day_tian=day_tian,
            month_di=month_di,
            day_di=day_di,
            pillars=pillars_en,
            canggan=canggan_dizhi,
            shishen=shishen_map,
        )
    except Exception as e:
        logger.warning(f"[排盘] 旺衰计算失败，置空: {type(e).__name__}: {e}", exc_info=True)
        wangshuai_result = {
            "conclusion": "", "de_ling": {}, "de_di": {}, "de_shi": {}, "total_score": 0,
        }

    # ================================================================
    # 4. 调候用神
    # ================================================================
    try:
        tiaohou_result = calculate_tiaohou(day_tian, month_di)
    except Exception as e:
        logger.warning(f"[排盘] 调候用神计算失败，置空: {type(e).__name__}: {e}", exc_info=True)
        tiaohou_result = {
            "yongshen": "", "xishen": "", "jishen": "", "tiaohou_description": "",
        }

    # ================================================================
    # 5. 格局判定（使用中文 key 的 pillars 和 shishen）
    # ================================================================
    # geju_skill 接受的 shishen 格式: {"年": {"tian": "正财", "di": "偏印"}, ...}
    # 与 bazi_service 返回的 shishen 格式一致
    try:
        geju_result = calculate_geju(
            day_tian=day_tian,
            month_di=month_di,
            pillars=pillars_cn,
            shishen=bazi.shishen,
            wangshuai_conclusion=wangshuai_result.get("conclusion", ""),
        )
    except Exception as e:
        logger.warning(f"[排盘] 格局判定失败，置空: {type(e).__name__}: {e}", exc_info=True)
        geju_result = {
            "geju_type": "", "geju_source_ganzhi": "", "xi_ji": {}, "geju_shishen": "",
        }

    # ================================================================
    # 6. 大运流年解读（可选，导入失败则跳过）
    # ================================================================
    dayun_interpretation = ""
    key_liunian_list: List[Dict] = []

    try:
        from app.skills.divination.dayun_liunian_skill import (
            analyze_dayun,
            get_key_years,
        )

        # 将 DayunItem 列表转为 dict 列表
        dayun_dict_list = []
        for d in dayun_list:
            if hasattr(d, 'model_dump'):
                dayun_dict_list.append(d.model_dump())
            elif hasattr(d, 'ganzhi'):
                dayun_dict_list.append({
                    "ganzhi": d.ganzhi, "start_year": d.start_year,
                    "end_year": d.end_year, "is_current": d.is_current,
                })
            else:
                dayun_dict_list.append(d)

        if current_dayun:
            dayun_result = analyze_dayun(
                dayun_ganzhi=current_dayun,
                day_tian=day_tian,
                pillars=pillars_cn,
                yongshen=tiaohou_result["yongshen"],
                jishen=tiaohou_result["jishen"],
            )
            dayun_interpretation = dayun_result.get("description", "")

        current_year = datetime.now().year
        key_liunian_list = get_key_years(
            dayun_list=dayun_dict_list,
            day_tian=day_tian,
            pillars=pillars_cn,
            yongshen=tiaohou_result["yongshen"],
            jishen=tiaohou_result["jishen"],
            current_year=current_year - 5,  # 从当前年份前5年开始，包含2021-2025历史流年
            analyze_range=25,  # 共25年：前5年 + 后20年
        )
    except ImportError as e:
        logger.warning(f"dayun_liunian_skill 未就绪，跳过大运流年解读部分: {e}")
    except Exception as e:
        logger.warning(f"大运流年解读计算失败，跳过: {e}")

    # ================================================================
    # 7. 五行应用（局部容错，失败置空）
    # ================================================================
    try:
        wuxing_app = _build_wuxing_application_section(
            yongshen=tiaohou_result.get("yongshen", ""),
            xishen=tiaohou_result.get("xishen", ""),
            jishen=tiaohou_result.get("jishen", ""),
        )
    except Exception as e:
        logger.warning(f"[排盘] 五行应用计算失败，置空: {type(e).__name__}: {e}", exc_info=True)
        wuxing_app = {}

    # ================================================================
    # 8. 占星数据
    # ================================================================
    astrology_data: Dict[str, Any] = {}
    try:
        from app.services.astrology_service import calculate_astrology

        astro_chart = calculate_astrology(birth_date, birth_time, latitude, longitude)
        astrology_data = _build_astrology_section(astro_chart)
    except Exception as e:
        logger.warning(f"占星数据计算失败，跳过: {e}")

    # ================================================================
    # 9. 组装完整 JSON
    # ================================================================

    # 日主描述
    try:
        day_master_desc = get_day_master_description(day_tian)
    except Exception as e:
        logger.warning(f"[排盘] 日主描述生成失败，置空: {type(e).__name__}: {e}", exc_info=True)
        day_master_desc = ""

    # 四柱字符串
    try:
        sizhu_str = _build_sizhu_string(pillars_cn)
    except Exception as e:
        logger.warning(f"[排盘] 四柱字符串构建失败，置空: {type(e).__name__}: {e}", exc_info=True)
        sizhu_str = ""

    # 月令描述
    try:
        yueling_desc = _build_yueling_description(month_di)
    except Exception as e:
        logger.warning(f"[排盘] 月令描述生成失败，置空: {type(e).__name__}: {e}", exc_info=True)
        yueling_desc = ""

    # 十神分布描述
    try:
        shishen_dist = _build_shishen_distribution(pillars_cn, shishen_map)
    except Exception as e:
        logger.warning(f"[排盘] 十神分布描述生成失败，置空: {type(e).__name__}: {e}", exc_info=True)
        shishen_dist = ""

    # 当前大运描述
    current_dayun_str = ""
    if current_dayun:
        for d in dayun_list:
            gz = d.ganzhi if hasattr(d, 'ganzhi') else d["ganzhi"]
            sy = d.start_year if hasattr(d, 'start_year') else d["start_year"]
            ey = d.end_year if hasattr(d, 'end_year') else d["end_year"]
            if gz == current_dayun:
                current_dayun_str = f"{gz} {sy}-{ey}"
                break

    # 大运列表（完整10步大运，供评测端校验 LLM 引用的大运是否合法；
    # 未起运时"当前大运"为空，此列表是唯一的大运合法依据）
    dayun_list_output = []
    for d in dayun_list:
        dayun_list_output.append({
            "ganzhi": d.ganzhi if hasattr(d, 'ganzhi') else d["ganzhi"],
            "start_year": d.start_year if hasattr(d, 'start_year') else d["start_year"],
            "end_year": d.end_year if hasattr(d, 'end_year') else d["end_year"],
        })

    # 纳音（中文 key 转换）
    nayin_output = nayin  # 已经是 {"年": "路旁土", ...} 格式

    # 旺衰详情
    wangshuai_detail = {
        "得令": wangshuai_result.get("de_ling", {}),
        "得地": wangshuai_result.get("de_di", {}),
        "得势": wangshuai_result.get("de_shi", {}),
        "总分": wangshuai_result.get("total_score", 0),
    }

    # 格局详情
    geju_detail = {
        "类型": geju_result.get("geju_type", ""),
        "来源": geju_result.get("geju_source_ganzhi", ""),
        "喜忌": geju_result.get("xi_ji", {}),
    }

    # ================================================================
    # 8.5 命格箴言（局部容错，失败置空）
    # ================================================================
    try:
        motto_result = generate_motto(
            month_di=month_di,
            tiaohou_yongshen=tiaohou_result.get("yongshen", ""),
            tiaohou_description=tiaohou_result.get("tiaohou_description", ""),
            shishen_distribution=shishen_dist,
            geju_type=geju_result.get("geju_type", ""),
            geju_shishen=geju_result.get("geju_shishen", ""),
            wangshuai_conclusion=wangshuai_result.get("conclusion", ""),
            shishen_map=shishen_map,
            pillars=pillars_cn,
        )
    except Exception as e:
        logger.warning(f"[排盘] 命格箴言生成失败，置空: {type(e).__name__}: {e}", exc_info=True)
        motto_result = {"命格箴言": "", "调候标签": "", "十神做功标签": ""}

    result: Dict[str, Any] = {
        "四柱": sizhu_str,
        "日主": day_master_desc,
        "月令": yueling_desc,
        "旺衰结论": wangshuai_result.get("conclusion", ""),
        "旺衰详情": wangshuai_detail,
        "格局": geju_result.get("geju_type", ""),
        "格局详情": geju_detail,
        "用神": tiaohou_result.get("yongshen", ""),
        "喜神": tiaohou_result.get("xishen", ""),
        "忌神": tiaohou_result.get("jishen", ""),
        "调候描述": tiaohou_result.get("tiaohou_description", ""),
        "地支作用": dizhi_result.get("summary", ""),
        "十神分布": shishen_dist,
        "五行分布": wuxing,
        "纳音": nayin_output,
        "大运方向": dayun_direction,
        "起运年龄": start_age,
        "当前大运": current_dayun_str,
        "大运列表": dayun_list_output,
        "大运解读": dayun_interpretation,
        "重点流年": key_liunian_list,
        "五行应用": wuxing_app,
        "占星数据": astrology_data,
        "生肖": zodiac,
        "命格箴言": motto_result.get("命格箴言", ""),
        "命格箴言标签": {
            "调候标签": motto_result.get("调候标签", ""),
            "十神做功标签": motto_result.get("十神做功标签", ""),
        },
        "空亡": kongwang,
        "长生十二宫": changsheng,
        "神煞": shensha,
        "天干五合": tiangan_he,
    }

    return result
