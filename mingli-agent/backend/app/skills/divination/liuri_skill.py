"""
流日解读模块

分析当日干支与原局四柱、当前大运、当月流月的相互作用，给出当日吉凶判断。

设计约束（与「今日建议文案口径Spec」一致）：
- 判定逻辑全部复用 dayun_liunian_skill：_analyze_interactions / _compute_overall_judge，
  不新写校准规则，保证流日与流月/流年同一套口径。
- 输出的 judge 保留内部 5 档（大吉/吉/平/凶/大凶），对外只暴露 grade 由服务层映射。
"""

from datetime import datetime
from typing import Dict, List

from app.services.bazi_service import calculate_day_pillar, get_ganzhi

from app.skills.divination.dayun_liunian_skill import (
    DIZHI_WUXING,
    TIANGAN_WUXING,
    _analyze_interactions,
    _check_chong,
    _check_he,
    _check_zi_xing,
    _compute_dizhi_zhugan_shishen,
    _compute_overall_judge,
    compute_tiangan_shishen,
)


# ============================================================
# 干支计算
# ============================================================

def date_to_ganzhi(date_str: str) -> str:
    """把公历日期（YYYY-MM-DD）换算为当日干支。

    取当日 12:00 作为基准时刻，避开 23:00 晚子时的跨日偏移。
    日柱算法与 bazi_service.calculate_day_pillar 完全同源（1900-01-01=甲戌日）。
    """
    y, m, d = (int(x) for x in date_str.split("-"))
    tian, di = calculate_day_pillar(datetime(y, m, d, 12, 0))
    return tian + di


def year_to_ganzhi(year: int) -> str:
    """公历年份换算为流年干支（与 bazi_service 同一公式：(year-4) % 60）。"""
    return get_ganzhi((year - 4) % 60)


# ============================================================
# 流日分析
# ============================================================

def _analyze_with_target(
    tian: str,
    di: str,
    target_ganzhi: str,
    target_label: str,
    yongshen: str,
    jishen: str,
) -> List[str]:
    """分析当日干支与某个对照干支（大运/流月）的冲合关系。

    标注沿用 dayun_liunian_skill 的规范，供 _compute_overall_judge 解析：
    '相冲，主变动'(中性) / '六合绊用神' / '六合绊忌神' / '六合，主合作' / '五合，合化X，主变化'
    """
    if not target_ganzhi or len(target_ganzhi) < 2:
        return []

    interactions: List[str] = []
    t_di = target_ganzhi[1]
    t_di_wx = DIZHI_WUXING.get(t_di, "")

    if _check_chong(di, t_di):
        if t_di_wx == yongshen:
            interactions.append(f"流日{di}冲{target_label}{t_di}（冲用神，凶）")
        elif t_di_wx == jishen:
            interactions.append(f"流日{di}冲{target_label}{t_di}（冲忌神，去忌为吉）")
        else:
            interactions.append(f"流日{di}与{target_label}{t_di}相冲，主变动")

    if _check_he(di, t_di):
        d_wx = DIZHI_WUXING.get(di, "")
        if t_di_wx == yongshen or d_wx == yongshen:
            interactions.append(f"流日{di}与{target_label}{t_di}六合绊用神")
        elif t_di_wx == jishen or d_wx == jishen:
            interactions.append(f"流日{di}与{target_label}{t_di}六合绊忌神")
        else:
            interactions.append(f"流日{di}与{target_label}{t_di}六合，主合作")

    if di == t_di:
        zx = _check_zi_xing(di, t_di)
        if zx:
            interactions.append(f"流日{di}与{target_label}{t_di}{zx}")

    return interactions


def _build_reason(
    tian_wx: str, di_wx: str, yongshen: str, jishen: str,
    interactions: List[str], judge: str,
) -> str:
    """生成当日白话原因（避免术语裸用，术语由 chart_ref 承载）。"""
    reasons: List[str] = []
    if tian_wx == yongshen and di_wx == yongshen:
        reasons.append("当日干支同属喜用五行")
    elif tian_wx == yongshen or di_wx == yongshen:
        reasons.append("当日干支见喜用五行")
    if tian_wx == jishen or di_wx == jishen:
        reasons.append("当日干支见忌讳五行")
    for inter in interactions:
        if "冲" in inter:
            reasons.append("有冲，主变动")
            break
    for inter in interactions:
        if "合" in inter:
            reasons.append("有合，主合作")
            break
    if not reasons:
        reasons.append("当日气机平缓")
    return "，".join(reasons)


def analyze_liuri(
    date_str: str,
    day_tian: str,
    pillars: Dict,
    yongshen: str,
    jishen: str,
    dayun_ganzhi: str = "",
    liuyue_ganzhi: str = "",
    is_strong: bool = False,
) -> Dict:
    """分析某一日的吉凶（流日）。

    参数:
        date_str: 公历日期 YYYY-MM-DD
        day_tian: 日主天干
        pillars: 四柱 {"年": {"tian": "庚", "di": "午"}, ...}
        yongshen: 用神五行（如 "火"）
        jishen: 忌神五行（如 "水"）
        dayun_ganzhi: 当前大运干支（可选，用于流日-大运互动）
        liuyue_ganzhi: 当月流月干支（可选，用于流日-流月互动）
        is_strong: 是否身强（来自旺衰结论）

    返回:
        {
            "date": "2026-10-14",
            "ganzhi": "辛丑",
            "tian_wuxing": "金",
            "di_wuxing": "土",
            "is_yongshen": False,
            "is_jishen": False,
            "judge": "平",          # 内部 5 档
            "interactions": [...],
            "shishen_tian": "比肩",
            "shishen_di": "偏印",
            "reason": "..."
        }
    """
    ganzhi = date_to_ganzhi(date_str)
    tian, di = ganzhi[0], ganzhi[1]
    tian_wx = TIANGAN_WUXING[tian]
    di_wx = DIZHI_WUXING[di]

    is_yongshen = (tian_wx == yongshen or di_wx == yongshen)
    is_jishen = (tian_wx == jishen or di_wx == jishen)

    # 流日与原局四柱（复用与流月/流年完全相同的互动分析）
    interactions = _analyze_interactions(
        tian, di, pillars, day_tian, "流日", yongshen, jishen,
    )

    # 流日与当月流月、当前大运
    interactions += _analyze_with_target(
        tian, di, liuyue_ganzhi, "流月", yongshen, jishen,
    )
    interactions += _analyze_with_target(
        tian, di, dayun_ganzhi, "大运", yongshen, jishen,
    )

    judge = _compute_overall_judge(
        tian_wx, di_wx, yongshen, jishen, interactions,
        day_wx=TIANGAN_WUXING.get(day_tian, ""), is_strong=is_strong,
    )

    return {
        "date": date_str,
        "ganzhi": ganzhi,
        "tian_wuxing": tian_wx,
        "di_wuxing": di_wx,
        "is_yongshen": is_yongshen,
        "is_jishen": is_jishen,
        "judge": judge,
        "interactions": interactions,
        "shishen_tian": compute_tiangan_shishen(tian, day_tian),
        "shishen_di": _compute_dizhi_zhugan_shishen(di, day_tian),
        "reason": _build_reason(tian_wx, di_wx, yongshen, jishen, interactions, judge),
    }
