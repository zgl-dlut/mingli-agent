"""追问报告风格库与轮换选择。

风格选择权在后端：每次生成前从风格库随机选 1 个开头风格 + 1 个总结风格，
排除最近 RECENT_WINDOW 轮已用过的风格（style_key 由生成后盖章落库），
prompt 只注入选中的那一条，不再全量枚举（省 token + 代码保证短期不重复）。
"""
import json
import random
from typing import List, Tuple

# ============================================================
# 开头风格库（12 种）
# ============================================================

OPENING_STYLES = {
    "现状承接式": "先一句话点出用户当前处境或纠结，再顺势给结论",
    "痛点直击式": "一句话点破用户真正纠结的核心矛盾，再给结论",
    "反常识提醒式": "先反转一个常见误判或惯性认知，再给出命盘结论",
    "情绪共情式": "先接住用户的情绪和压力表达理解，再自然给结论",
    "结论直击式": "不铺垫直接抛出最终结论，句式自然禁止模板化",
    "场景代入式": "先描绘用户正经历的一个现实场景，再引出判断",
    "悬念设问式": "先抛一个直击要害的设问，再给出命盘答案",
    "数据锚点式": "先用命盘里一个关键年份或吉凶节点锚定注意，再展开结论",
    "转折递进式": "先承认事情的一面，再用转折翻出另一面递进给结论",
    "类比启发式": "用一个生活化类比打比方引入，让结论通俗易懂",
    "时间对照式": "用两个时间段或吉凶年的对照开场，带出判断",
    "风险前置式": "先把最需要注意的风险或坑点出，再讲应对与出路",
}

# ============================================================
# 总结风格库（12 种）
# ============================================================

SUMMARY_STYLES = {
    "行动清单": "用一条条'何时做什么'的可执行行动收尾",
    "时间轴": "按时间先后把关键节点和对应动作串成线",
    "阶段提醒": "按不同阶段分别给出该阶段最要紧的提醒",
    "避坑清单": "聚焦风险点和坑，逐条给出规避做法",
    "剧情演进": "像讲故事推进一样把整段走向复盘一遍",
    "关键数字提炼式": "提炼关键年份、月份窗口等数字信息收尾",
    "三句话定心式": "浓缩成三句最要紧的话给用户定心",
    "风险对策对照式": "每个风险点配一条对策，一一对照给出",
    "里程碑节点式": "围绕几个关键里程碑节点给出对应动作",
    "主线分支式": "一条主线建议加一两条分支提醒",
    "取舍清单式": "用'该做什么/不该做什么'的取舍对照收尾",
    "复盘检查式": "给用户一份可自行对照核查的检查清单",
}

# 排除窗口：最近 N 轮已用风格不再选（N < 风格库容量，保证始终有候选）
RECENT_WINDOW = 8


def _collect_used_styles(history_messages: List[dict], window: int) -> Tuple[set, set]:
    """从历史 assistant 消息（倒序取最近 window 条可解析 JSON）收集已用风格 key。

    旧消息无 style_key 时跳过，不计入排除。
    """
    used_opening = []
    used_summary = []
    parsed = 0
    for msg in reversed(history_messages or []):
        if msg.get("role") != "assistant":
            continue
        try:
            data = json.loads(msg.get("content") or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        parsed += 1
        opening_key = (data.get("opening") or {}).get("style_key")
        summary_key = (data.get("summary") or {}).get("style_key")
        if opening_key and opening_key in OPENING_STYLES:
            used_opening.append(opening_key)
        if summary_key and summary_key in SUMMARY_STYLES:
            used_summary.append(summary_key)
        if parsed >= window:
            break
    return set(used_opening), set(used_summary)


def pick_styles(
    history_messages: List[dict],
) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    """为本次追问选定开头风格与总结风格。

    从「全部风格 − 最近 RECENT_WINDOW 轮已用风格」中随机各选一个，
    返回 ((opening_key, opening_desc), (summary_key, summary_desc))。
    """
    used_opening, used_summary = _collect_used_styles(history_messages, RECENT_WINDOW)
    opening_candidates = [k for k in OPENING_STYLES if k not in used_opening] or list(OPENING_STYLES)
    summary_candidates = [k for k in SUMMARY_STYLES if k not in used_summary] or list(SUMMARY_STYLES)
    opening_key = random.choice(opening_candidates)
    summary_key = random.choice(summary_candidates)
    return (opening_key, OPENING_STYLES[opening_key]), (summary_key, SUMMARY_STYLES[summary_key])
