"""生产监控：智能采样 + 三层检测体系

策略说明：
- 第一层：规则检测（100% 覆盖，零成本）—— 术语黑名单、凶年启动等
- 第二层：轻量指标（100% 覆盖，低成本）—— 字数、格式、耗时等
- 第三层：LLM 深度评测（智能抽样）—— 高风险必检 + 异常触发 + 随机兜底

采样决策逻辑：
1. 高风险必检（100%）：敏感话题、首次报告、负面情绪
2. 异常触发（100%）：规则违规、指标异常
3. 随机兜底（比例由环境变量 EVAL_SAMPLE_RATE 控制，默认1.0全量）：发现未知问题
"""
import json
import logging
import os
import random
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── 敏感话题关键词 ───
SENSITIVE_KEYWORDS = [
    # 健康类
    "健康", "疾病", "手术", "住院", "癌症", "肿瘤", "死亡", "寿命", "寿命长短",
    "身体", "体检", "慢性病", "重病", "大病",
    # 法律类
    "法律", "诉讼", "官司", "坐牢", "犯罪", "违法", "纠纷", "仲裁",
    # 投资类
    "投资", "借贷", "贷款", "炒股", "基金", "理财", "创业", "开店", "加盟",
    # 心理类（负面情绪）
    "焦虑", "害怕", "恐惧", "绝望", "抑郁", "想不开", "撑不下去", "撑不住",
    "崩溃", "无助", "痛苦", "难过", "伤心", "担心", "忧虑",
]

# ─── 轻量指标阈值 ───
MIN_WORD_COUNT = 300          # 报告最低字数
MIN_BLOCK_COUNT = 1           # 最少 keyword block 数
MAX_GENERATION_TIME = 600     # 最长生成时间（秒）
MIN_GENERATION_TIME = 3       # 最短生成时间（秒，低于可能质量差）


def _count_chinese_chars(text: str) -> int:
    """统计中文字符数"""
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def _extract_report_text(report: Dict) -> str:
    """从报告中提取所有叙事文本"""
    texts = []
    subtopics = report.get("subtopics", [])
    for st in subtopics:
        for block in st.get("blocks", []):
            narrative = block.get("narrative", "")
            if narrative:
                texts.append(narrative)
    summary = report.get("summary", {})
    if summary:
        for item in summary.get("items", []):
            text = item.get("text", "")
            if text:
                texts.append(text)
        closing = summary.get("closing", "")
        if closing:
            texts.append(closing)
    opening = report.get("opening", {})
    if opening:
        verdict = opening.get("verdict", "")
        if verdict:
            texts.append(verdict)
    return "".join(texts)


def _check_sensitive_topic(user_question: str) -> Tuple[bool, str]:
    """检测是否涉及敏感话题"""
    for kw in SENSITIVE_KEYWORDS:
        if kw in user_question:
            return True, f"包含敏感词: {kw}"
    return False, ""


def _check_negative_emotion(user_question: str) -> Tuple[bool, str]:
    """检测用户是否表达负面情绪"""
    negative_patterns = [
        r"怎么办", r"好烦", r"好累", r"受不了", r"受不了了",
        r"撑不住", r"撑不下去", r"想不开", r"不想活",
        r"完了", r"完蛋", r"没救了", r"没希望",
    ]
    for pattern in negative_patterns:
        if re.search(pattern, user_question):
            return True, f"负面情绪: {pattern}"
    return False, ""


def _check_light_metrics(report: Dict, generation_time: float) -> List[str]:
    """第二层：轻量指标检测，返回异常信号列表"""
    signals = []

    # 字数检测
    full_text = _extract_report_text(report)
    word_count = _count_chinese_chars(full_text)
    if word_count < MIN_WORD_COUNT:
        signals.append(f"字数过少: {word_count}字 < {MIN_WORD_COUNT}")

    # block 数量检测
    block_count = 0
    for st in report.get("subtopics", []):
        block_count += len(st.get("blocks", []))
    if block_count < MIN_BLOCK_COUNT:
        signals.append(f"block 过少: {block_count} < {MIN_BLOCK_COUNT}")

    # 生成耗时检测
    if generation_time < MIN_GENERATION_TIME:
        signals.append(f"生成过快: {generation_time:.1f}s < {MIN_GENERATION_TIME}s")
    if generation_time > MAX_GENERATION_TIME:
        signals.append(f"生成过慢: {generation_time:.1f}s > {MAX_GENERATION_TIME}s")

    return signals


def _check_rule_violations(report: Dict) -> List[str]:
    """第一层：规则检测（复用已有检测逻辑的简化版）"""
    violations = []
    full_text = _extract_report_text(report)

    # 术语黑名单检测
    forbidden_terms = [
        "杀印相生", "伤官见官", "卯酉相冲", "寅午半合火局",
        "卯辰相害", "破印", "气暗动", "天干透出", "地支联动",
    ]
    for term in forbidden_terms:
        if term in full_text:
            violations.append(f"术语违规: {term}")

    # 干支纪时写法检测
    if re.search(r'[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥](月|流年)', full_text):
        violations.append("干支纪时写法违规")

    return violations


def should_deep_eval(
    report: Dict,
    user_question: str,
    is_first_report: bool = False,
    generation_time: float = 0,
    rule_violations: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """判断是否需要深度 LLM 评测。

    Args:
        report: 报告 JSON 数据
        user_question: 用户原始问题
        is_first_report: 是否首次报告
        generation_time: 生成耗时（秒）
        rule_violations: 第一层规则检测发现的违规列表

    Returns:
        (是否需要深度评测, 触发原因)
    """
    logger.info(
        f"[ProductionMonitor] 采样决策开始: "
        f"question={user_question[:50]}, first={is_first_report}, "
        f"gen_time={generation_time:.1f}s"
    )

    # ── 1. 高风险必检 ──
    sensitive, reason = _check_sensitive_topic(user_question)
    if sensitive:
        logger.info(f"[ProductionMonitor] 触发: 敏感话题 - {reason}")
        return True, f"sensitive_topic:{reason}"

    negative, reason = _check_negative_emotion(user_question)
    if negative:
        logger.info(f"[ProductionMonitor] 触发: 负面情绪 - {reason}")
        return True, f"negative_emotion:{reason}"

    if is_first_report:
        logger.info(f"[ProductionMonitor] 触发: 首次报告（高风险）")
        return True, "first_report"

    # ─── 2. 异常触发 ───
    # 2a. 规则检测违规
    if rule_violations:
        logger.info(f"[ProductionMonitor] 触发: 规则违规 - {rule_violations}")
        return True, f"rule_violation:{';'.join(rule_violations)}"

    # 2b. 轻量指标异常
    light_signals = _check_light_metrics(report, generation_time)
    if light_signals:
        logger.info(f"[ProductionMonitor] 触发: 轻量指标异常 - {light_signals}")
        return True, f"light_metric:{';'.join(light_signals)}"

    # ─── 3. 随机兜底（比例可配置：EVAL_SAMPLE_RATE，默认1.0全量评测） ───
    sample_rate = float(os.getenv("EVAL_SAMPLE_RATE", "1.0"))
    if random.random() < sample_rate:
        logger.info(f"[ProductionMonitor] 触发: 随机采样（比例{sample_rate:.0%}）")
        return True, f"random_sample(rate={sample_rate:.0%})"

    logger.info(f"[ProductionMonitor] 未触发深度评测，跳过")
    return False, ""


def build_monitor_detail(
    report: Dict,
    user_question: str,
    trigger_reason: str,
    is_first_report: bool = False,
    generation_time: float = 0,
    eval_detail: Optional[Dict] = None,
) -> Dict:
    """构建监控记录详情。

    新增 L2 格式完成指标：从 eval_detail 的 hard_check 中提取
    structure_count / narrative_count / chart_usage_count。
    """
    full_text = _extract_report_text(report)
    word_count = _count_chinese_chars(full_text)

    block_count = 0
    for st in report.get("subtopics", []):
        block_count += len(st.get("blocks", []))

    # 提取系统回复预览（opening.lead + verdict）
    opening = report.get("opening", {})
    response_parts = []
    if opening.get("lead"):
        response_parts.append(opening["lead"][:200])
    if opening.get("verdict"):
        response_parts.append(opening["verdict"][:200])
    response_preview = " | ".join(response_parts)[:400] if response_parts else ""

    detail: Dict = {
        "trigger_reason": trigger_reason,
        "is_first_report": is_first_report,
        "generation_time": round(generation_time, 1),
        "word_count": word_count,
        "block_count": block_count,
        "subtopic_count": len(report.get("subtopics", [])),
        "question_preview": user_question[:100],
        "response_preview": response_preview,
        # 完整报告 JSON：供人工查看全貌、定位违规段落（detail 列为 MEDIUMTEXT）
        "report": report,
    }

    # L2 格式完成：从硬性检查结果中提取各层级违规数
    if eval_detail:
        hard_check = eval_detail.get("hard_check", {})
        detail["l2_format"] = {
            "structure_violations": hard_check.get("structure_count", 0),
            "narrative_violations": hard_check.get("narrative_count", 0),
            "chart_usage_violations": hard_check.get("chart_usage_count", 0),
            "total_violations": len(hard_check.get("violations", [])),
            "passed": hard_check.get("passed", False),
            "blocked_by": hard_check.get("blocked_by"),
            # 违规明细：每项含 type/detail/location/reason，便于人工定位具体内容
            "violations": hard_check.get("violations", []),
        }

    # 问题归因字段（人工标注）
    detail["root_cause"] = {
        "category": None,       # prompt_issue / code_bug / rule_too_strict / edge_case
        "note": "",             # 人工备注
        "fixed_in_version": None,
    }

    return detail


async def run_deep_eval(
    report: Dict,
    user_question: str,
    chart_data: Dict,
    is_first_report: bool = False,
) -> Dict:
    """执行 LLM 深度评测（第三层），调用 llm_scorer.evaluate_report。

    Args:
        report: 报告 JSON
        user_question: 用户问题
        chart_data: 命盘数据
        is_first_report: 是否首次报告

    Returns:
        {
            "passed": bool,
            "avg_soft_score": float | None,
            "hard_check": {...},
            "soft_score": {...},
            "violations": [...],
            "error": str | None
        }
    """
    try:
        from app.services.eval.llm_scorer import evaluate_report
        result = await evaluate_report(report, user_question, chart_data, is_first_report)
        # 统一格式：提取所有 violations
        all_violations = []
        hard_check = result.get("hard_check", {})
        if hard_check.get("violations"):
            all_violations.extend(hard_check["violations"])
        logger.info(
            f"[ProductionMonitor] LLM 深度评测完成: "
            f"overall_pass={result.get('overall_pass')}, "
            f"avg_soft_score={result.get('avg_soft_score')}, "
            f"hard_violations={len(hard_check.get('violations', []))}, "
            f"skip_reason={result.get('skip_reason')}"
        )
        return {
            "passed": result.get("overall_pass", False),
            "avg_soft_score": result.get("avg_soft_score"),
            "hard_check": hard_check,
            "soft_score": result.get("soft_score"),
            "fabrication": result.get("fabrication"),
            "violations": all_violations,
            "skip_reason": result.get("skip_reason"),
            "error": None,
        }
    except Exception as e:
        logger.error(f"[ProductionMonitor] LLM 深度评测异常: {e}")
        return {
            "passed": False,
            "avg_soft_score": None,
            "violations": [],
            "error": str(e),
        }


async def save_monitor_result(
    report: Dict,
    user_question: str,
    user_id: int,
    session_id: int,
    trigger_reason: str,
    is_first_report: bool = False,
    generation_time: float = 0,
    chart_data: Optional[Dict] = None,
    eval_detail: Optional[Dict] = None,
    prompt_version: str = "",
) -> None:
    """保存生产监控结果到数据库。

    存储完整的 L1/L2/L3/LLM 四层指标：
    - L1 技术完成：能走到这里说明 JSON 解析 + Pydantic 校验通过
    - L2 格式完成：结构/叙事/命盘使用检查的违规数（代码层）
    - L3 质量完成：硬性检查的通过状态 + 被哪类拦截
    - LLM 软性评分：叙事性/通顺性等（仅硬性通过时才有）
    - prompt_version：生成该报告时的 prompt/检测器版本，用于精确归因
    """
    try:
        from app.db.session import async_session
        from app.models.eval_result import EvalResult

        # 如果触发了深度评测但还没有 eval_detail，执行 LLM 评测
        # 当 trigger_reason == "no_trigger" 时跳过深度评测（仅记录轻量监控）
        if eval_detail is None and chart_data and trigger_reason != "no_trigger":
            logger.info(f"[ProductionMonitor] 开始 LLM 深度评测...")
            eval_detail = await run_deep_eval(report, user_question, chart_data, is_first_report)

        # 先构建 monitor_detail（传入 eval_detail 以包含 L2 指标）
        monitor_detail = build_monitor_detail(
            report, user_question, trigger_reason, is_first_report, generation_time, eval_detail
        )
        # prompt/检测器版本标记（生成报告时的版本，用于精确归因与跨版本对比）
        monitor_detail["prompt_version"] = prompt_version

        # 用户与命盘标识：便于生产监控列表区分用户
        monitor_detail["user_id"] = user_id
        monitor_detail["session_id"] = session_id
        if chart_data:
            monitor_detail["bazi"] = chart_data.get("四柱", "")

        # 完整存储四层指标
        if eval_detail:
            hard_check = eval_detail.get("hard_check", {})
            monitor_detail["eval_result"] = {
                # 总体
                "passed": eval_detail.get("passed"),
                "skip_reason": eval_detail.get("skip_reason"),
                "error": eval_detail.get("error"),
                # L1 技术完成（能走到这里说明 JSON 解析 + Pydantic 校验通过）
                "l1_technical": True,
                # L2 格式完成（代码层检查）
                "l2_format": monitor_detail.get("l2_format"),
                # L3 质量完成（硬性检查通过状态）
                "l3_quality": {
                    "passed": hard_check.get("passed", False),
                    "blocked_by": hard_check.get("blocked_by"),
                    "total_violations": len(hard_check.get("violations", [])),
                },
                # 违规明细（type/detail/location/reason），供人工归因定位
                "violations": eval_detail.get("violations", []),
                # LLM 软性评分（仅硬性通过时才有）
                "llm_soft_score": eval_detail.get("avg_soft_score"),
                "llm_soft_details": eval_detail.get("soft_score"),
                # 编造检测
                "fabrication": eval_detail.get("fabrication"),
            }

        # 统计违规分布
        violation_dist = {}
        if eval_detail:
            for v in eval_detail.get("violations", []):
                vtype = v.get("type", "unknown")
                violation_dist[vtype] = violation_dist.get(vtype, 0) + 1

        async with async_session() as db:
            # 联查 person 获取生辰信息（性别+出生时间+出生地）
            try:
                from sqlalchemy import select
                from app.models.session import ChatSession
                from app.models.person import Person
                session_row = (await db.execute(select(ChatSession).where(ChatSession.id == session_id))).scalar_one_or_none()
                if session_row:
                    person_row = (await db.execute(select(Person).where(Person.id == session_row.person_id))).scalar_one_or_none()
                    if person_row:
                        monitor_detail["gender"] = person_row.gender
                        monitor_detail["birth_date"] = person_row.birth_date
                        monitor_detail["birth_time"] = person_row.birth_time
                        monitor_detail["birth_location"] = person_row.birth_location or ""
            except Exception:
                pass  # 联查失败不阻断主流程

            record = EvalResult(
                dataset_id=f"monitor_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                eval_type="production_monitor",
                total=1,
                passed=1 if not eval_detail or eval_detail.get("passed", True) else 0,
                failed=0 if not eval_detail or eval_detail.get("passed", True) else 1,
                pass_rate=1.0 if not eval_detail or eval_detail.get("passed", True) else 0.0,
                detail=json.dumps([monitor_detail], ensure_ascii=False),
                violation_distribution=violation_dist if violation_dist else None,
                created_at=datetime.utcnow(),
            )
            db.add(record)
            await db.commit()
            logger.info(
                f"[ProductionMonitor] 监控记录已保存: "
                f"user_id={user_id}, session_id={session_id}, "
                f"trigger={trigger_reason}, passed={record.passed}"
            )
    except Exception as e:
        logger.error(f"[ProductionMonitor] 保存监控记录失败: {e}")
