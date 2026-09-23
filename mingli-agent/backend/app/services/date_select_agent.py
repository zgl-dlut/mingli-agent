"""
择日决策 Agent

用户在对话中说"帮我挑个领证日子" → 意图识别 → Agent 自主调用工具筛选吉日
与 followup_structured 链路隔离，互不影响。

Agent 主循环（plan-and-execute + function calling）：
1. LLM 接收用户目标 + 命盘摘要，输出筛选计划 + 调用工具
2. 工具返回结果，LLM 决定下一步（继续筛选 or 给结果 or 重新规划）
3. 最多 5 轮工具调用，防止无限循环
4. 最终输出结构化 JSON（type=date_select），前端渲染日期卡片
"""

from __future__ import annotations

import json
import time
import logging
import calendar
from datetime import datetime, timedelta, date
from typing import AsyncGenerator, Dict, List, Optional

from app.services.ai_service import model_pool, get_client, build_llm_extra_body, build_cache_control_messages

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setLevel(logging.INFO)
    _h.setFormatter(logging.Formatter("[%(asctime)s] [DateSelectAgent] %(message)s"))
    logger.addHandler(_h)
    import os
    os.makedirs("logs", exist_ok=True)
    _fh = logging.FileHandler("logs/date_select_agent.log", encoding="utf-8")
    _fh.setLevel(logging.INFO)
    _fh.setFormatter(logging.Formatter("[%(asctime)s] [DateSelectAgent] %(message)s"))
    logger.addHandler(_fh)
    logger.setLevel(logging.INFO)
    logger.propagate = False


# ============================================================
# 常量复用（从 dayun_liunian_skill 导入，不重复定义）
# ============================================================

from app.skills.divination.dayun_liunian_skill import (
    TIANGAN, DIZHI, TIANGAN_WUXING, DIZHI_WUXING,
    DIZHI_CANGGAN, TIANGAN_YINYANG,
    compute_tiangan_shishen,
    _check_chong, _check_he, _check_tiangang_he,
    _check_zi_xing, _check_san_he,
)
from app.services.bazi_service import get_ganzhi, TIANGAN as BAZI_TIANGAN, DIZHI as BAZI_DIZHI


# ============================================================
# 工具1：get_chart —— 获取用户命盘摘要
# ============================================================

GET_CHART_TOOL = {
    "type": "function",
    "function": {
        "name": "get_chart",
        "description": "获取用户命盘的核心数据（日主、四柱、用神、忌神、当前大运）。所有择日判断必须基于此命盘数据。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

def _format_chart_result(analysis_data: Dict) -> str:
    """格式化命盘摘要给 LLM。"""
    pillars = analysis_data.get("四柱", {})
    day_master = analysis_data.get("日主", "")
    yongshen = analysis_data.get("用神", "")
    jishen = analysis_data.get("忌神", "")
    current_dayun = analysis_data.get("当前大运", "")
    wangshuai = analysis_data.get("旺衰", "")

    lines = [
        f"日主：{day_master}",
        f"四柱：{pillars}",
        f"旺衰：{wangshuai}",
        f"用神：{yongshen}",
        f"忌神：{jishen}",
    ]
    if current_dayun:
        lines.append(f"当前大运：{current_dayun}")

    # 四柱地支列表（供冲合判定参考）
    pillar_dz = []
    for name in ("年", "月", "日", "时"):
        p = pillars.get(name, {})
        if isinstance(p, dict) and p.get("di"):
            pillar_dz.append(p["di"])
    if pillar_dz:
        lines.append(f"四柱地支：{', '.join(pillar_dz)}")

    # 日柱地支（择日最关键——不能冲日柱）
    day_pillar = pillars.get("日", {})
    if isinstance(day_pillar, dict):
        day_di = day_pillar.get("di", "")
        if day_di:
            lines.append(f"日柱地支：{day_di}（择日不可冲此支）")

    return "\n".join(lines)


# ============================================================
# 工具2：list_candidate_days —— 列出候选日期
# ============================================================

LIST_DAYS_TOOL = {
    "type": "function",
    "function": {
        "name": "list_candidate_days",
        "description": "列出指定月份范围内的候选日期（公历），返回每天的日期、星期、干支。可筛选工作日/周末。",
        "parameters": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "年份，如2026"},
                "month": {"type": "integer", "description": "月份，1-12"},
                "weekday_filter": {
                    "type": "string",
                    "enum": ["all", "weekday", "weekend"],
                    "description": "筛选：all=全部, weekday=仅工作日, weekend=仅周末",
                },
            },
            "required": ["year", "month"],
        },
    },
}

def _format_list_days_result(year: int, month: int, weekday_filter: str = "all", analysis_data: Dict | None = None) -> str:
    """列出某月候选日期 + 干支，并标注每个日期与日柱的冲合关系（减少后续 check_day_chart 调用）。"""
    # 提取日柱地支（择日不可冲）
    user_day_di = ""
    if analysis_data:
        pillars = analysis_data.get("四柱", {})
        day_pillar = pillars.get("日", {}) if isinstance(pillars, dict) else {}
        if isinstance(day_pillar, dict):
            user_day_di = day_pillar.get("di", "")

    cal = calendar.Calendar()
    days = []
    for d in cal.itermonthdates(year, month):
        if d.month != month:
            continue
        # 计算干支：用与 1900-01-31（庚午日）的天数差
        base_date = date(1900, 1, 31)
        day_num = (d - base_date).days
        ganzhi = get_ganzhi(day_num)
        day_di = ganzhi[1]
        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        weekday_cn = weekday_names[d.weekday()]
        is_weekend = d.weekday() >= 5

        if weekday_filter == "weekend" and not is_weekend:
            continue
        if weekday_filter == "weekday" and is_weekend:
            continue

        # 标注冲/合日柱
        tags = []
        if user_day_di:
            if _check_chong(day_di, user_day_di):
                tags.append("冲日柱❌")
            elif _check_he(day_di, user_day_di):
                tags.append("合日柱✓")

        days.append({
            "date": d.isoformat(),
            "weekday": f"周{weekday_cn}",
            "ganzhi": ganzhi,
            "is_weekend": is_weekend,
            "tags": tags,
        })

    if not days:
        return f"{year}年{month}月无符合筛选条件的日期"

    # 统计冲日柱数量
    chong_count = sum(1 for d in days if "冲日柱❌" in d["tags"])
    lines = [f"{year}年{month}月候选日期（{weekday_filter}，共{len(days)}天，其中冲日柱{chong_count}天需排除）："]
    for d in days:
        tag = "周末" if d["is_weekend"] else "工作日"
        extra = f" [{','.join(d['tags'])}]" if d["tags"] else ""
        lines.append(f"  {d['date']} {d['weekday']} {d['ganzhi']} [{tag}]{extra}")
    lines.append(f"\n提示：标注「冲日柱❌」的日期不可用，无需再调 check_day_chart；其余日期可精选后再调 check_day_chart 确认。")
    return "\n".join(lines)


# ============================================================
# 工具3：check_day_chart —— 检查某日与命盘的冲合关系
# ============================================================

CHECK_DAY_TOOL = {
    "type": "function",
    "function": {
        "name": "check_day_chart",
        "description": "检查指定日期（公历日期，如2026-11-15）的干支与用户命盘的冲合关系。返回该日是否冲日柱、是否合用神、十神关系等。这是择日最核心的判断工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "date_str": {"type": "string", "description": "公历日期，格式YYYY-MM-DD，如2026-11-15"},
            },
            "required": ["date_str"],
        },
    },
}

def _format_check_day_result(date_str: str, analysis_data: Dict) -> str:
    """检查某日干支与命盘的冲合关系。"""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return f"日期格式错误：{date_str}，需要YYYY-MM-DD格式"

    # 计算当日干支
    base_date = date(1900, 1, 31)
    day_num = (d - base_date).days
    day_ganzhi = get_ganzhi(day_num)
    day_tian = day_ganzhi[0]
    day_di = day_ganzhi[1]

    pillars = analysis_data.get("四柱", {})
    day_master = analysis_data.get("日主", "")
    yongshen = analysis_data.get("用神", "")
    jishen = analysis_data.get("忌神", "")

    # 日柱地支（择日不可冲）
    day_pillar = pillars.get("日", {})
    if isinstance(day_pillar, dict):
        user_day_di = day_pillar.get("di", "")
        user_day_tian = day_pillar.get("tian", "")
    else:
        user_day_di = ""
        user_day_tian = ""

    # 天干十神
    tian_shishen = compute_tiangan_shishen(day_tian, day_master) if day_master else ""
    # 地支十神（取藏干主气）
    di_shishen = ""
    if day_di in DIZHI_CANGGAN:
        main_gan = DIZHI_CANGGAN[day_di][0]
        di_shishen = compute_tiangan_shishen(main_gan, day_master) if day_master else ""

    tian_wx = TIANGAN_WUXING.get(day_tian, "")
    di_wx = DIZHI_WUXING.get(day_di, "")

    is_yongshen = (tian_wx == yongshen or di_wx == yongshen) if yongshen else False
    is_jishen = (tian_wx == jishen or di_wx == jishen) if jishen else False

    # 冲合检测
    interactions: List[str] = []

    # 冲日柱（最重要）
    if user_day_di and _check_chong(day_di, user_day_di):
        interactions.append(f"⚠ 当日地支{day_di}冲日柱{user_day_di}（大忌，不宜重大事宜）")

    # 合日柱
    if user_day_di and _check_he(day_di, user_day_di):
        interactions.append(f"✓ 当日地支{day_di}与日柱{user_day_di}六合（主和顺）")

    # 天干五合
    if user_day_tian and _check_tiangang_he(day_tian, user_day_tian):
        interactions.append(f"✓ 当日天干{day_tian}与日主{user_day_tian}天干合（主和谐）")

    # 与其他柱的冲合
    for pillar_name in ("年", "月", "时"):
        p = pillars.get(pillar_name, {})
        if not isinstance(p, dict):
            continue
        p_di = p.get("di", "")
        if not p_di:
            continue
        if _check_chong(day_di, p_di):
            p_wx = DIZHI_WUXING.get(p_di, "")
            if p_wx == yongshen:
                interactions.append(f"当日地支{day_di}冲{pillar_name}柱{p_di}（冲用神，不利）")
            elif p_wx == jishen:
                interactions.append(f"当日地支{day_di}冲{pillar_name}柱{p_di}（冲忌神，去忌为吉）")
            else:
                interactions.append(f"当日地支{day_di}与{pillar_name}柱{p_di}相冲（主变动）")
        if _check_he(day_di, p_di):
            interactions.append(f"当日地支{day_di}与{pillar_name}柱{p_di}六合")

    # 自刑
    if user_day_di and _check_zi_xing(day_di, user_day_di):
        interactions.append(f"当日地支{day_di}与日柱{user_day_di}自刑")

    # 五行吉凶
    if is_yongshen and not is_jishen:
        chart_judge = "吉（用神当令）"
    elif is_jishen and not is_yongshen:
        chart_judge = "凶（忌神当令）"
    elif is_yongshen and is_jishen:
        chart_judge = "半吉半凶（用忌兼具）"
    else:
        chart_judge = "平（用忌不明显）"

    # 冲日柱直接降级
    if user_day_di and _check_chong(day_di, user_day_di):
        chart_judge = "凶（冲日柱）"

    lines = [
        f"日期：{date_str}",
        f"干支：{day_ganzhi}（天干{day_tian}/{tian_wx}，地支{day_di}/{di_wx}）",
        f"十神：天干{tian_shishen}，地支{di_shishen}",
        f"五行吉凶：{chart_judge}",
    ]
    if interactions:
        lines.append("冲合关系：")
        for i in interactions:
            lines.append(f"  {i}")
    else:
        lines.append("冲合关系：无明显冲合")

    return "\n".join(lines)


# ============================================================
# 工具4：check_shensha —— 查询当日宜忌（简化版，基于通胜逻辑）
# ============================================================

CHECK_SHENSHA_TOOL = {
    "type": "function",
    "function": {
        "name": "check_shensha",
        "description": "查询指定日期的建除十二神（建/除/满/平/定/执/破/危/成/收/开/闭）和基础宜忌。返回该日适合/不适合做什么。",
        "parameters": {
            "type": "object",
            "properties": {
                "date_str": {"type": "string", "description": "公历日期，格式YYYY-MM-DD"},
            },
            "required": ["date_str"],
        },
    },
}

# 建除十二神轮值表（按日地支与月建的关系推算）
JIANCHU_12 = ["建", "除", "满", "平", "定", "执", "破", "危", "成", "收", "开", "闭"]

# 各神的宜忌（简化版，基于传统通胜）
JIANCHU_YIJI = {
    "建": {"yi": "谒贵、出行、谋事", "ji": "动土、开仓"},
    "除": {"yi": "治病、解除、扫舍", "ji": "嫁娶、上任"},
    "满": {"yi": "祭祀、祈福、进人口", "ji": "安葬、移徙"},
    "平": {"yi": "修造、动土、出行", "ji": "开渠、挖掘"},
    "定": {"yi": "嫁娶、冠笄、谋事", "ji": "诉讼、出行"},
    "执": {"yi": "捕捉、畋猎", "ji": "开市、立券"},
    "破": {"yi": "求医、破屋", "ji": "嫁娶、开市、动土"},
    "危": {"yi": "祭祀、祈福", "ji": "登山、乘船"},
    "成": {"yi": "嫁娶、开市、入宅、移徙", "ji": "诉讼、行丧"},
    "收": {"yi": "进人口、纳财、捕捉", "ji": "出行、安葬"},
    "开": {"yi": "开市、入宅、移徙、动土", "ji": "安葬、下葬"},
    "闭": {"yi": "筑堤、塞穴", "ji": "开市、嫁娶、出行"},
}

def _get_jianchu(day_di: str, month_di: str) -> str:
    """推算建除十二神。

    基本规则：月建地支为"建"，按地支顺序轮转。
    如寅月（立春后），寅日=建，卯日=除，辰日=满...
    """
    if day_di not in DIZHI or month_di not in DIZHI:
        return "建"
    month_idx = DIZHI.index(month_di)
    day_idx = DIZHI.index(day_di)
    # 建除从月建开始轮，差值 mod 12
    offset = (day_idx - month_idx) % 12
    return JIANCHU_12[offset]

def _format_shensha_result(date_str: str, analysis_data: Dict) -> str:
    """查询当日建除宜忌。"""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return f"日期格式错误：{date_str}"

    base_date = date(1900, 1, 31)
    day_num = (d - base_date).days
    day_ganzhi = get_ganzhi(day_num)
    day_di = day_ganzhi[1]

    # 确定月建地支（简化：按公历月份估算节气月，精确版需查节气表）
    # 寅月=2月(立春后), 卯=3月, 辰=4月, 巳=5月, 午=6月, 未=7月,
    # 申=8月, 酉=9月, 戌=10月, 亥=11月, 子=12月, 丑=1月
    month_di_map = {
        1: "丑", 2: "寅", 3: "卯", 4: "辰", 5: "巳", 6: "午",
        7: "未", 8: "申", 9: "酉", 10: "戌", 11: "亥", 12: "子",
    }
    month_di = month_di_map.get(d.month, "寅")

    jianchu = _get_jianchu(day_di, month_di)
    yiji = JIANCHU_YIJI.get(jianchu, {"yi": "—", "ji": "—"})

    lines = [
        f"日期：{date_str}",
        f"干支：{day_ganzhi}",
        f"建除十二神：{jianchu}",
        f"宜：{yiji['yi']}",
        f"忌：{yiji['ji']}",
    ]

    # 标注是否适合嫁娶
    if "嫁娶" in yiji["yi"]:
        lines.append("★ 此日通胜宜嫁娶")
    elif "嫁娶" in yiji["ji"]:
        lines.append("⚠ 此日通胜忌嫁娶")
    else:
        lines.append("○ 此日通胜对嫁娶无明显标注")

    return "\n".join(lines)


# ============================================================
# 工具5：explain_choice —— 对选中日子生成命理依据解释
# ============================================================

EXPLAIN_TOOL = {
    "type": "function",
    "function": {
        "name": "explain_choice",
        "description": "对最终选中的吉日生成命理依据解释。传入选中日期列表，返回每个日期推荐理由的摘要（干支、十神、冲合、宜忌）。供最终输出给用户时引用。",
        "parameters": {
            "type": "object",
            "properties": {
                "dates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "选中的日期列表，如[\"2026-11-15\", \"2026-11-28\"]",
                },
            },
            "required": ["dates"],
        },
    },
}

def _format_explain_result(dates: List[str], analysis_data: Dict) -> str:
    """对选中日期生成解释摘要。"""
    day_master = analysis_data.get("日主", "")
    yongshen = analysis_data.get("用神", "")
    jishen = analysis_data.get("忌神", "")
    pillars = analysis_data.get("四柱", {})
    day_pillar = pillars.get("日", {})
    if isinstance(day_pillar, dict):
        user_day_di = day_pillar.get("di", "")
    else:
        user_day_di = ""

    lines = [f"选中日期命理依据汇总（共{len(dates)}个）："]
    for date_str in dates:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        base_date = date(1900, 1, 31)
        day_num = (d - base_date).days
        day_ganzhi = get_ganzhi(day_num)
        day_tian = day_ganzhi[0]
        day_di = day_ganzhi[1]
        tian_shishen = compute_tiangan_shishen(day_tian, day_master) if day_master else ""
        tian_wx = TIANGAN_WUXING.get(day_tian, "")
        di_wx = DIZHI_WUXING.get(day_di, "")
        is_yongshen = (tian_wx == yongshen or di_wx == yongshen) if yongshen else False
        is_jishen = (tian_wx == jishen or di_wx == jishen) if jishen else False

        reasons = []
        if is_yongshen and not is_jishen:
            reasons.append(f"用神{yongshen}当令")
        if user_day_di and _check_he(day_di, user_day_di):
            reasons.append(f"与日柱{user_day_di}六合")
        if _check_tiangang_he(day_tian, day_master) if day_master else False:
            reasons.append(f"天干与日主合")
        if not reasons:
            reasons.append("无明显冲克")

        # 建除宜忌
        month_di_map = {
            1: "丑", 2: "寅", 3: "卯", 4: "辰", 5: "巳", 6: "午",
            7: "未", 8: "申", 9: "酉", 10: "戌", 11: "亥", 12: "子",
        }
        month_di = month_di_map.get(d.month, "寅")
        jianchu = _get_jianchu(day_di, month_di)
        yiji = JIANCHU_YIJI.get(jianchu, {"yi": "—", "ji": "—"})

        lines.append(
            f"  {date_str}（{day_ganzhi}）：十神{tian_shishen}，"
            f"{'、'.join(reasons)}；建除{jianchu}，宜{yiji['yi']}"
        )

    return "\n".join(lines)


# ============================================================
# 工具注册表 + 调度
# ============================================================

ALL_TOOLS = [GET_CHART_TOOL, LIST_DAYS_TOOL, CHECK_DAY_TOOL, CHECK_SHENSHA_TOOL, EXPLAIN_TOOL]

def dispatch_tool(tool_name: str, args: dict, analysis_data: Dict) -> str:
    """调度工具函数，返回结果文本。"""
    # 兜底反序列化（保险：防止 chat.py 里反序列化漏网）
    import json as _j
    if isinstance(analysis_data, str):
        try:
            analysis_data = _j.loads(analysis_data)
        except Exception:
            pass

    # 兼容旧版排盘格式：四柱是字符串 "己亥 丙寅 癸巳 壬子" → 转成 dict
    pillars = analysis_data.get("四柱") if isinstance(analysis_data, dict) else None
    if isinstance(pillars, str):
        pillar_names = ("年", "月", "日", "时")
        parts = pillars.split()
        if len(parts) == 4:
            new_pillars = {}
            for name, gz in zip(pillar_names, parts):
                if len(gz) >= 2:
                    new_pillars[name] = {"tian": gz[0], "di": gz[1]}
            if new_pillars:
                analysis_data = dict(analysis_data)
                analysis_data["四柱"] = new_pillars
        logger.info(f"[dispatch_tool] 旧版四柱字符串已转换为 dict: {pillars}")

    # 兼容旧版日主格式："癸水" → 只取天干 "癸"
    dm = analysis_data.get("日主") if isinstance(analysis_data, dict) else None
    if isinstance(dm, str) and len(dm) >= 2:
        analysis_data = dict(analysis_data)
        analysis_data["日主"] = dm[0]
    if tool_name == "get_chart":
        return _format_chart_result(analysis_data)
    elif tool_name == "list_candidate_days":
        # 防御性校验：LLM 可能传过期年份/月份，自动纠正到当前年月，避免选出过去的日期
        _year = args.get("year", date.today().year)
        _month = args.get("month", date.today().month)
        _today = date.today()
        if (_year, _month) < (_today.year, _today.month):
            logger.info(f"[DateSelectAgent] list_candidate_days 收到过期年月 {_year}-{_month}，纠正为当前 {_today.year}-{_today.month}")
            _year, _month = _today.year, _today.month
        return _format_list_days_result(
            _year,
            _month,
            args.get("weekday_filter", "all"),
            analysis_data,
        )
    elif tool_name == "check_day_chart":
        return _format_check_day_result(args.get("date_str", ""), analysis_data)
    elif tool_name == "check_shensha":
        return _format_shensha_result(args.get("date_str", ""), analysis_data)
    elif tool_name == "explain_choice":
        return _format_explain_result(args.get("dates", []), analysis_data)
    else:
        return f"未知工具：{tool_name}"


# ============================================================
# Agent 系统提示词
# ============================================================

AGENT_SYSTEM_PROMPT = """你是命理择日顾问。用户需要你帮忙挑选吉日（如领证、搬家、开业等）。

你拥有以下工具：
1. get_chart：获取用户命盘数据（日主、四柱、用神忌神、当前大运）
2. list_candidate_days：列出某年某月的候选日期及干支，可筛选工作日/周末
3. check_day_chart：检查某日与命盘的冲合关系（是否冲日柱、合用神等）——这是核心判断工具
4. check_shensha：查询当日建除十二神和宜忌
5. explain_choice：对选中的吉日生成命理依据解释

# 工作流程（必须遵循）
1. 先调 get_chart 获取用户命盘
2. 确定择日的时间范围和偏好（**绝对不要停下来问用户！** 按以下默认值自行补全）：
   - **时间范围默认值**：用户没说具体月份 → 默认从**当前月到未来2个月**（共3个月），范围太广则收窄为未来30天
   - **工作日/周末默认值**：用户没说偏好 → weekday_filter="all"（全部都可以）
   - **事件类型**：从用户问题推断（领证/结婚/搬家/开业/签约/出行/动土等），用于 check_shensha 时匹配宜忌
3. 用 list_candidate_days 列出候选日（按步骤2确定的范围和筛选）
   - **重要**：list_candidate_days 返回的每个日期已标注「冲日柱❌」或「合日柱✓」。**冲日柱的日期直接排除，不要再调 check_day_chart 检查它们！**
4. 从剩余日期中精选 3-5 个最优候选（优先选「合日柱✓」、用神当令、周末/节假日的日期），只对这几个精选日期调 check_day_chart 检查冲合关系
5. 对精选吉日调 check_shensha 查宜忌
6. 调 explain_choice 生成推荐理由
7. 输出最终结果

# 冲突重规划规则（重要）
- 如果所有候选日都冲日柱，不要返回空结果！应：
  a. 判断哪个约束可以放宽（如"周末"放宽为"工作日"，或"11月"放宽到"12月"）
  b. 重新调用 list_candidate_days 获取新范围
  c. 重新筛选
- 如果候选日中工作日是吉日但用户要周末，主动说明"周末都不理想，某工作日反而好"并让用户选择

# 输出格式
最终输出纯JSON（不要用```json包裹），结构如下：
{
  "type": "date_select",
  "recommended_dates": [
    {
      "date": "2026-11-15",
      "ganzhi": "甲辰",
      "weekday": "周日",
      "shishen": "偏印",
      "reason": "与日柱六合，用神火当令；建除成日，宜嫁娶入宅",
      "score": 92
    }
  ],
  "conflict_note": "（可选）如有冲突或限制说明，如'11月周末均冲日柱，推荐的两个工作日反而更吉'",
  "summary": "综合来看，11月15日和28日最适合领证..."
}

# 硬约束
- **只能推荐今天及未来的日期**，过去的日期绝对不能出现在 recommended_dates 里。调用 list_candidate_days 时 year/month 必须 >= 当前年月。
- **绝对不要在输出中反问用户或请求补充信息**（如"请告诉我您的出生年月日"、"请问偏好周末还是工作日"、"计划在哪月"）。所有缺失参数按上述默认值自行补全。
- **不要以"命盘获取失败"为借口停止**，get_chart 失败时也要继续用用户问题里的时间范围走下去，尽量返回日期结果。
- recommended_dates 必须包含真实的干支和十神（由工具计算，禁止编造）
- 冲日柱的日期绝对不能出现在 recommended_dates 里
- reason 必须基于工具返回的数据（冲合关系、用忌神、建除宜忌），禁止编造
- score 是0-100的整数，用神当令+合日柱+宜嫁娶=90+，有轻微不利=70-89，明显不利不入推荐
- 如果最终没有合适日期，返回空 recommended_dates 并在 conflict_note 说明原因
"""


# ============================================================
# Agent 主循环
# ============================================================

async def generate_date_select(
    user_question: str,
    analysis_data: Dict,
    usage_holder: Optional[dict] = None,
) -> AsyncGenerator[str, None]:
    """
    择日 Agent 主循环。

    使用 function calling 让 LLM 自主决定调用哪些工具、按什么顺序。
    最多 5 轮工具调用，防止无限循环。

    输出 JSON 字符串（type=date_select），存入 ChatMessage.content，
    前端识别 type=date_select 走 DateSelectCard 渲染。
    """
    if not model_pool:
        logger.error("[DateSelectAgent] model_pool 为空")
        yield json.dumps({"type": "date_select", "error": "AI模型未配置"}, ensure_ascii=False)
        return

    model_config = model_pool[0]
    client = await get_client(model_config)

    # 注入当前真实日期，防止 LLM 用训练数据里的旧年份导致选到过去的日期
    today = date.today()
    today_str = f"{today.year}年{today.month}月{today.day}日"
    messages = [{
        "role": "user",
        "content": f"当前日期是 {today.isoformat()}（{today_str}）。\n用户请求：{user_question}",
    }]
    all_messages = build_cache_control_messages(AGENT_SYSTEM_PROMPT, messages)

    start = time.time()
    tool_call_count = 0
    max_tool_rounds = 8

    logger.info(f"[DateSelectAgent] 开始, 模型={model_config.name}, 问题: {user_question[:80]}")

    for round_num in range(max_tool_rounds + 1):
        try:
            response = await client.chat.completions.create(
                model=model_config.name,
                messages=all_messages,
                tools=ALL_TOOLS,
                temperature=0.3,
                max_tokens=4000,
                response_format={"type": "json_object"},
                timeout=120,
                extra_body=build_llm_extra_body(model_config.name),
            )
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"[DateSelectAgent] LLM请求失败: 耗时={elapsed:.1f}s, 错误={type(e).__name__}: {str(e)[:200]}")
            yield json.dumps({"type": "date_select", "error": f"AI调用失败: {type(e).__name__}"}, ensure_ascii=False)
            return

        if not response.choices:
            yield json.dumps({"type": "date_select", "error": "LLM返回空响应"}, ensure_ascii=False)
            return

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # 处理工具调用
        if msg.tool_calls:
            tool_call_count += len(msg.tool_calls)
            tool_names = [tc.function.name for tc in msg.tool_calls]
            logger.info(f"[DateSelectAgent] 第{round_num + 1}轮工具调用: {tool_names}")

            all_messages.append(msg)  # 添加 assistant 消息（含 tool_calls）

            for tool_call in msg.tool_calls:
                try:
                    args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    result = dispatch_tool(tool_call.function.name, args, analysis_data)
                    logger.info(f"[DateSelectAgent] 工具 {tool_call.function.name} 返回, 长度={len(result)}")
                    # 记录工具调用步骤（供 agent 轨迹展示）
                    if usage_holder is not None:
                        if "agent_steps" not in usage_holder:
                            usage_holder["agent_steps"] = []
                        usage_holder["agent_steps"].append({
                            "tool": tool_call.function.name,
                            "args": args,
                            "result_preview": result[:200],
                        })
                except Exception as e:
                    logger.error(f"[DateSelectAgent] 工具 {tool_call.function.name} 异常: {e}")
                    if tool_call.function.name == "get_chart":
                        # 命盘获取失败时，给 LLM 一个降级提示让它继续，不要停下来问用户
                        result = "命盘数据暂不可用。请继续用后续工具（list_candidate_days / check_day_chart / check_shensha）按传统通胜宜忌和干支择日，优先避开冲日柱的日期。用户的生辰八字信息已在系统中，请不要要求用户重新提供。"
                    else:
                        result = f"工具调用失败: {type(e).__name__}: {e}"
                all_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
                # 实时推送进度给前端（格式：__PROGRESS__简短工具名:描述）
                _tool_label = {
                    "get_chart": "获取命盘数据",
                    "list_candidate_days": "列出候选日期",
                    "check_day_chart": "逐日筛选冲合关系",
                    "check_shensha": "查询建除宜忌",
                    "explain_choice": "生成推荐理由",
                }.get(tool_call.function.name, tool_call.function.name)
                yield f"__PROGRESS__{_tool_label}\n"
            continue  # 继续下一轮 LLM 调用

        # 无工具调用，获取最终响应
        raw_content = msg.content or ""
        break
    else:
        # 超过最大轮次仍未完成
        raw_content = json.dumps({
            "type": "date_select",
            "error": "Agent超过最大工具调用轮次",
        }, ensure_ascii=False)

    elapsed = time.time() - start

    # token 用量统计
    prompt_tokens = completion_tokens = total_tokens = 0
    usage = getattr(response, "usage", None)
    if usage is not None:
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens)

    logger.info(
        f"[DateSelectAgent] 完成: 耗时={elapsed:.1f}s, 工具调用={tool_call_count}次, "
        f"token: prompt={prompt_tokens}, completion={completion_tokens}, "
        f"输出长度={len(raw_content)}"
    )

    # 填充用量
    if usage_holder is not None:
        usage_holder.update({
            "success": True,
            "model": model_config.name,
            "input_chars": len(AGENT_SYSTEM_PROMPT),
            "output_chars": len(raw_content),
            "elapsed": elapsed,
            "tool_calls": tool_call_count,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        })

    yield raw_content


# ============================================================
# 意图识别：判断用户问题是否是择日请求
# ============================================================

_DATE_SELECT_KEYWORDS = [
    "择日", "挑日子", "选日子", "挑个好日子", "选个好日子",
    "领证", "结婚日期", "婚期", "结婚日子",
    "搬家", "入宅", "搬迁", "乔迁", "搬屋",
    "开业", "开张", "开店", "开市",
    "面试日期", "签约吉日", "签约",
    "黄道吉日", "吉日", "好日子",
    "哪天适合", "哪天好", "几号好", "什么日子",
    "什么时候搬家", "什么时候领证", "什么时候开业",
    "挑个.*日子", "选个.*日子",
]

def _keyword_match(question: str) -> bool:
    """关键词快速匹配（0延迟）。"""
    import re
    q = question.strip().lower()
    for kw in _DATE_SELECT_KEYWORDS:
        if ".*" in kw:
            if re.search(kw, q):
                return True
        elif kw in q:
            return True
    return False

# LLM 兜底分类的提示词
_INTENT_CLASSIFY_PROMPT = """判断用户的问题是否在请求"挑选日期/选择吉日"。

判定标准：用户想让你帮他从日历中选出具体的日期（某天/某几天），用于做某件事（领证、搬家、开业、签约、出行、动土等）。
不判定的情况：用户只是问运势/事业/感情/财运趋势，或问某个时间段的情况，或问性格/能力，没有"选日期"的意图。

只回答JSON：{"is_date_select": true} 或 {"is_date_select": false}"""

async def is_date_select_intent_async(question: str) -> bool:
    """判断用户问题是否是择日请求（关键词快速命中 + LLM 兜底分类）。"""
    # 第一层：关键词快速命中
    if _keyword_match(question):
        return True
    # 第二层：LLM 兜底分类
    if not model_pool:
        return False
    try:
        model_config = model_pool[-1]  # 用最小的模型
        client = await get_client(model_config)
        response = await client.chat.completions.create(
            model=model_config.name,
            messages=[
                {"role": "system", "content": _INTENT_CLASSIFY_PROMPT},
                {"role": "user", "content": question},
            ],
            temperature=0,
            max_tokens=20,
            response_format={"type": "json_object"},
            timeout=10,
            extra_body=build_llm_extra_body(model_config.name),
        )
        result = json.loads(response.choices[0].message.content)
        is_ds = result.get("is_date_select", False)
        logger.info(f"[DateSelectAgent] LLM兜底分类: 问题='{question[:40]}' => {is_ds}")
        return is_ds
    except Exception as e:
        logger.warning(f"[DateSelectAgent] LLM兜底分类失败,回退False: {e}")
        return False
