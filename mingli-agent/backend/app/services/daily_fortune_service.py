"""
每日运势 / 今日建议 生成服务

链路：档案 bazi_data（四柱/用神/忌神/大运）→ 流日算法（+ 流月、当前大运）
      → 组装 source 权威基准 → LLM 生成三段文案（action/basis/chart_ref）→ 自检。

文案口径严格遵循《今日建议文案口径Spec》：
- action 零术语；basis 白话；chart_ref 术语仅此一行，且必须与 source 完全一致
- 十神/干支由算法算好后注入 prompt，禁止 LLM 自行推演
- 等级双层：算法 judge（大吉/吉/平/凶/大凶，不改校准）→ 对外只暴露 grade
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.ai_service import build_llm_extra_body, get_client, model_pool
from app.skills.divination.dayun_liunian_skill import analyze_liuyue
from app.skills.divination.liuri_skill import analyze_liuri, year_to_ganzhi

logger = logging.getLogger(__name__)


# ============================================================
# 常量
# ============================================================

# 算法 judge（内部 5 档）→ 对外 grade（3 个英文 token）
GRADE_MAP: Dict[str, str] = {
    "大吉": "good",
    "吉": "good",
    "平": "neutral",
    "凶": "caution",
    "大凶": "caution",
}

# 禁用词（《今日建议文案口径Spec》5.2），生成后自动扫描，命中即降级兜底。
# 说明：Spec 5.2 中「会 / 将 / 灾 / 凶」等单字未纳入本表——它们在中文里高频作为构词成分
# （机会、将来、灾害、凶猛），字面扫描会把正常句子误判为违规，故这些词的约束由 prompt
# 红线承担，扫描表只收敛到无歧义的词。
FORBIDDEN_WORDS: List[str] = [
    # 绝对化
    "一定", "必然", "必将", "注定", "绝对", "肯定", "100%",
    # 预测性
    "预示", "命中注定", "迟早", "注定要",
    # 灾祸类
    "大凶", "破财", "血光", "犯小人", "冲煞", "劫难", "凶险", "霉运",
    # 迷信服务
    "开运", "转运", "化解", "消灾", "法事", "开光", "改运", "招财符", "辟邪",
    # 诱导消费
    "付费即可改运", "充值才能化解", "买会员避灾", "不开通就错过",
    # 数字预言
    "加薪", "翻倍", "必得",
    # 术语裸用
    "吉凶", "煞气", "命里注定",
]

# 命理术语（action / basis 内禁止出现；chart_ref 是唯一允许出现处）
SHISHEN_NAMES: List[str] = [
    "比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印",
]
TERM_WORDS: List[str] = [
    "用神", "忌神", "大运", "流年", "流月", "流日", "命盘", "八字", "五行",
    "天干", "地支", "煞气", "自刑", "相冲", "比劫", "印星", "财星", "官杀",
    "食伤", "空亡", "神煞", "纳音", "调候",
]

# 各档兜底文案（LLM 失败或自检不通过时使用，全部为白话语料）
FALLBACK_ADVICE: Dict[str, Dict[str, Any]] = {
    "good": {
        "action": "今天适合把手头要紧的事往前推一推。",
        "basis": "今天整体节奏偏顺，适合主动一点。",
        "yi": ["谈事", "学习"],
        "ji": ["拖延"],
        "pressure_level": 35,
    },
    "neutral": {
        "action": "今天按部就班，把计划内的事做扎实。",
        "basis": "今天整体平缓，稳住平时的节奏就好。",
        "yi": ["整理", "复盘"],
        "ji": ["冒进"],
        "pressure_level": 50,
    },
    "caution": {
        "action": "今天宜守不宜攻，少做新决定。",
        "basis": "今天节奏偏紧，把想说的话先沉一沉。",
        "yi": ["独处", "守成"],
        "ji": ["签约", "远行"],
        "pressure_level": 70,
    },
}


# ============================================================
# 基础工具
# ============================================================

def map_grade(judge: str) -> str:
    """算法 judge → 对外 grade（未知值按 neutral，不抛异常）。"""
    return GRADE_MAP.get(judge, "neutral")


def scan_forbidden(text: str) -> List[str]:
    """扫描禁用词，返回命中的词列表。"""
    if not text:
        return []
    return [w for w in FORBIDDEN_WORDS if w in text]


def scan_terms(text: str) -> List[str]:
    """扫描命理术语（十神名 + 术语词），用于校验 action/basis 是否零术语。"""
    if not text:
        return []
    hits = [w for w in SHISHEN_NAMES if w in text]
    hits += [w for w in TERM_WORDS if w in text]
    return hits


def parse_pillars(sizhu_str: str) -> Dict[str, Dict[str, str]]:
    """把 bazi_data 的「四柱」字符串（"庚午 丙子 乙巳 庚辰"）解析为算盘可用的四柱结构。"""
    names = ["年", "月", "日", "时"]
    pillars: Dict[str, Dict[str, str]] = {}
    parts = [p for p in (sizhu_str or "").split() if len(p) >= 2]
    for i, name in enumerate(names):
        if i < len(parts):
            pillars[name] = {"tian": parts[i][0], "di": parts[i][1]}
    return pillars


def _calc_age(birth_date: str, date_str: str) -> Optional[int]:
    """按出生日期算周岁（数据缺失时返回 None）。"""
    try:
        by, bm, bd = (int(x) for x in birth_date.split("-"))
        dy, dm, dd = (int(x) for x in date_str.split("-"))
        age = dy - by - ((dm, dd) < (bm, bd))
        return age
    except Exception:
        return None


def _pick_dayun_ganzhi(bazi_data: Dict[str, Any], year: int) -> str:
    """取该年份所处的大运干支：优先按年份在大运列表里匹配，兜底用「当前大运」。"""
    for d in bazi_data.get("大运列表") or []:
        try:
            if int(d.get("start_year")) <= year <= int(d.get("end_year")):
                return str(d.get("ganzhi") or "")
        except (TypeError, ValueError):
            continue
    current = str(bazi_data.get("当前大运") or "").strip()
    return current.split()[0] if current else ""


def build_fortune_context(
    bazi_data: Dict[str, Any], date_str: str,
) -> Dict[str, Any]:
    """从档案 azi_data 算出当日运势所需的全部算法事实（source 权威基准）。"""
    pillars = parse_pillars(bazi_data.get("四柱", ""))
    if "日" not in pillars:
        raise ValueError("档案排盘数据缺少四柱信息，无法计算流日")

    day_tian = pillars["日"]["tian"]
    yongshen = str(bazi_data.get("用神") or "")
    jishen = str(bazi_data.get("忌神") or "")
    wangshuai = str(bazi_data.get("旺衰结论") or "")
    is_strong = wangshuai.startswith("身旺") or wangshuai.startswith("身偏旺")

    y, m, _d = (int(x) for x in date_str.split("-"))

    # 流月：1 月（丑月）属上一流年，用上一年的年干推寅月天干
    month_base_year = y - 1 if m == 1 else y
    liuyue_list = analyze_liuyue(
        liunian_ganzhi=year_to_ganzhi(month_base_year),
        day_tian=day_tian,
        pillars=pillars,
        yongshen=yongshen,
        jishen=jishen,
        is_strong=is_strong,
    )
    liuyue_ganzhi = ""
    for item in liuyue_list:
        if item.get("solar_month") == m:
            liuyue_ganzhi = item.get("month_ganzhi", "")
            break

    dayun_ganzhi = _pick_dayun_ganzhi(bazi_data, y)

    liuri = analyze_liuri(
        date_str=date_str,
        day_tian=day_tian,
        pillars=pillars,
        yongshen=yongshen,
        jishen=jishen,
        dayun_ganzhi=dayun_ganzhi,
        liuyue_ganzhi=liuyue_ganzhi,
        is_strong=is_strong,
    )

    return {
        "day_tian": day_tian,
        "day_wuxing": liuri["tian_wuxing"],
        "liuri": liuri,
        "liuyue_ganzhi": liuyue_ganzhi,
        "dayun_ganzhi": dayun_ganzhi,
        "yongshen": yongshen,
        "jishen": jishen,
    }


# ============================================================
# Prompt
# ============================================================

_SYSTEM_PROMPT = """你是「趣算算」的今日建议文案助手。你只做一件事：把算法已经算好的当日命理事实，翻译成用户当天能执行的一句小行动。

【绝对红线】
1. 十神名称、干支、用神/忌神必须严格引用下方【算法事实】给出的名称，禁止自行推演、改写或新增任何命理数据。算法没给的，一个字都不许写。
2. 禁止出现下列表达：{forbidden}
3. 不做命理预测、不构成任何医疗/投资/法律建议。

【三段文案（各司其职，尺寸硬限制）】
- action：用户第一眼看到的行动句。≤20字，动词开头、一行、句号收尾，当天可完成。**不含任何命理词汇**（不得出现干支字、十神名、五行字、用神/忌神/流日/流月/大运等术语）。
- basis：为什么是这条建议。≤30字，一行，白话（能量/状态视角），同样不出现命理术语。
- chart_ref：依据行。≤20字，一行，术语仅允许出现在这一行，且**每个干支/十神必须与【算法事实】逐字一致**。

【宜忌标签】
- yi：2~3 个，每个 ≤4 字，动词或动宾短语（如「谈事」「学习」）。
- ji：1~2 个，每个 ≤4 字。
- 标签同样禁止命理术语与禁用词。

【压力指数】
- pressure_level：0~100 的整数，只表达当日紧绷程度，不得写成预测或收益数字。

【边界规则】
- 若【算法事实】标注「忌神日」，禁止给出启动类行动（启动、推进、开业、谈判签约、投资、远行起步），宜写收敛、整理、蓄力类行动。
- 未成年档案（年龄 < 18）禁止出现婚姻、恋爱、投资类建议。

【自检】
输出前逐项核对：长度达标、action 零术语、chart_ref 与算法事实一致、无禁用词。任一项不达标就改写，不要输出不合格内容。

只输出一个 JSON 对象，不要解释、不要 Markdown 代码块：
{{"action": "...", "basis": "...", "chart_ref": "...", "yi": ["..."], "ji": ["..."], "pressure_level": 50}}"""


def _build_user_payload(ctx: Dict[str, Any], age: Optional[int], date_str: str) -> str:
    liuri = ctx["liuri"]
    shishen_tian = liuri["shishen_tian"] or "（算法未给出）"
    shishen_di = liuri["shishen_di"] or "（算法未给出）"
    age_line = f"{age}岁" if age is not None else "未知"

    return (
        f"【日期】{date_str}\n"
        f"【档案年龄】{age_line}\n"
        f"【算法事实】（严格引用，禁止自行推演）\n"
        f"日主天干：{ctx['day_tian']}（{ctx['day_wuxing']}）\n"
        f"当日干支（流日）：{liuri['ganzhi']}\n"
        f"当日天干十神：{shishen_tian}\n"
        f"当日地支十神：{shishen_di}\n"
        f"当月流月干支：{ctx['liuyue_ganzhi'] or '（无）'}\n"
        f"当前大运干支：{ctx['dayun_ganzhi'] or '（未起运）'}\n"
        f"用神五行：{ctx['yongshen'] or '（未给出）'}\n"
        f"忌神五行：{ctx['jishen'] or '（未给出）'}\n"
        f"当日用忌神：{'忌神日' if liuri['is_jishen'] else ('用神日' if liuri['is_yongshen'] else '平平日')}\n"
        f"冲合情况：{'；'.join(liuri['interactions']) or '无明显冲合'}\n"
        f"算法结论：{liuri['reason']}\n"
    )


# ============================================================
# 生成
# ============================================================

def _strip_code_fence(text: str) -> str:
    """剥掉模型可能多写的 ```json 代码块围栏。"""
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _validate_advice(data: Dict[str, Any]) -> Tuple[bool, str]:
    """按验收清单校验 LLM 输出，返回 (是否合格, 不合格原因)。"""
    advice = data.get("advice", {})
    action = str(advice.get("action") or "").strip()
    basis = str(advice.get("basis") or "").strip()
    chart_ref = str(advice.get("chart_ref") or "").strip()

    if not action or not basis or not chart_ref:
        return False, "三段文案为空"
    if len(action) > 20:
        return False, f"action 超长({len(action)})"
    if len(basis) > 30:
        return False, f"basis 超长({len(basis)})"
    if len(chart_ref) > 20:
        return False, f"chart_ref 超长({len(chart_ref)})"
    if len(action) + len(basis) + len(chart_ref) > 60:
        return False, "主卡合计超长"

    # action / basis 必须零术语
    for field_name, text in (("action", action), ("basis", basis)):
        terms = scan_terms(text)
        if terms:
            return False, f"{field_name} 出现命理术语: {terms}"

    # 禁用词全文扫描（含宜忌标签）
    all_text = action + basis + chart_ref + "".join(
        str(x) for x in (data.get("yi") or []) + (data.get("ji") or [])
    )
    banned = scan_forbidden(all_text)
    if banned:
        return False, f"命中禁用词: {banned}"

    # chart_ref 的干支/十神必须能在 source 里对账（可查、可一致）
    source = data["source"]
    source_ganzhi = [
        source["liuri_ganzhi"], source["liuyue_ganzhi"], source["dayun_ganzhi"],
    ]
    known_shishen = {source["shishen_tian"], source["shishen_di"]}
    for name in SHISHEN_NAMES:
        if name in chart_ref and name not in known_shishen:
            return False, f"chart_ref 十神与 source 不一致: {name}"
    for gz in re.findall(r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]", chart_ref):
        if gz not in source_ganzhi:
            return False, f"chart_ref 干支与 source 不一致: {gz}"

    return True, ""


def _normalize_tags(raw: Any, limit: int) -> List[str]:
    """归整宜忌标签：去空、限长、去重、限个数。"""
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for item in raw:
        tag = str(item or "").strip()
        if not tag or len(tag) > 4:
            continue
        if tag not in out:
            out.append(tag)
    return out[:limit]


def _fallback_advice(ctx: Dict[str, Any], grade: str) -> Dict[str, Any]:
    """兜底文案：全部来自算法事实与静态白话语料，不依赖 LLM。"""
    preset = FALLBACK_ADVICE.get(grade, FALLBACK_ADVICE["neutral"])
    liuri = ctx["liuri"]
    chart_ref = f"{ctx['day_tian']}{ctx['day_wuxing']}逢{liuri['shishen_tian']}日" \
        if liuri["shishen_tian"] else f"{ctx['day_tian']}{ctx['day_wuxing']}日"
    return {
        "advice": {
            "action": preset["action"],
            "basis": preset["basis"],
            "chart_ref": chart_ref[:20],
        },
        "yi": list(preset["yi"]),
        "ji": list(preset["ji"]),
        "pressure_level": preset["pressure_level"],
    }


def _clamp_pressure(raw: Any, grade: str) -> int:
    """压力指数：非法值/越界值按档位兜底。"""
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return int(FALLBACK_ADVICE[grade]["pressure_level"])
    return max(0, min(100, v))


async def _call_llm(system_prompt: str, user_payload: str) -> Optional[Dict[str, Any]]:
    """调用模型池生成文案 JSON，失败返回 None。"""
    if not model_pool:
        logger.warning("[日运] 模型池为空，无法生成文案")
        return None
    model_config = model_pool[0]
    client = await get_client(model_config)
    resp = await client.chat.completions.create(
        model=model_config.name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.7,
        max_tokens=600,
        response_format={"type": "json_object"},
        timeout=30,
        extra_body=build_llm_extra_body(model_config.name),
    )
    content = _strip_code_fence(resp.choices[0].message.content or "")
    return json.loads(content) if content else None


async def generate_daily_fortune(
    bazi_data: Dict[str, Any], date_str: str, birth_date: str = "",
) -> Dict[str, Any]:
    """生成某日运势（含今日建议）。

    返回结构与接口契约一致（第十节命名契约：全英文 snake_case）。
    LLM 调用失败或文案自检不通过时，降级为算法驱动的兜底文案，不抛异常。
    """
    ctx = build_fortune_context(bazi_data, date_str)
    liuri = ctx["liuri"]
    grade = map_grade(liuri["judge"])
    age = _calc_age(birth_date, date_str) if birth_date else None

    source = {
        "liuri_ganzhi": liuri["ganzhi"],
        "liuyue_ganzhi": ctx["liuyue_ganzhi"],
        "dayun_ganzhi": ctx["dayun_ganzhi"],
        "shishen_tian": liuri["shishen_tian"],
        "shishen_di": liuri["shishen_di"],
    }

    payload = {
        "source": source,
        "advice": {},
        "yi": [],
        "ji": [],
        "pressure_level": 0,
    }

    try:
        system_prompt = _SYSTEM_PROMPT.format(forbidden="、".join(FORBIDDEN_WORDS))
        raw = await _call_llm(system_prompt, _build_user_payload(ctx, age, date_str))
        if raw:
            payload["advice"] = raw.get("advice") or {
                "action": raw.get("action"),
                "basis": raw.get("basis"),
                "chart_ref": raw.get("chart_ref"),
            }
            payload["yi"] = _normalize_tags(raw.get("yi"), 3)
            payload["ji"] = _normalize_tags(raw.get("ji"), 2)
            payload["pressure_level"] = raw.get("pressure_level")
            ok, why = _validate_advice(payload)
            if not ok:
                logger.warning(f"[日运] 文案自检不通过，降级兜底: {why}")
                payload.update(_fallback_advice(ctx, grade))
        else:
            logger.warning("[日运] LLM 未返回内容，降级兜底")
            payload.update(_fallback_advice(ctx, grade))
    except Exception as e:
        logger.warning(f"[日运] 文案生成失败，降级兜底: {type(e).__name__}: {str(e)[:150]}")
        payload.update(_fallback_advice(ctx, grade))

    payload["pressure_level"] = _clamp_pressure(payload.get("pressure_level"), grade)
    if not payload["yi"]:
        payload["yi"] = list(FALLBACK_ADVICE[grade]["yi"])
    if not payload["ji"]:
        payload["ji"] = list(FALLBACK_ADVICE[grade]["ji"])

    return {
        "date": date_str,
        "advice": payload["advice"],
        "source": source,
        "grade": grade,
        "yi": payload["yi"],
        "ji": payload["ji"],
        "pressure_level": payload["pressure_level"],
    }
