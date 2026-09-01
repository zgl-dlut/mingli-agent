"""LLM 评分器：分层评分（硬性错误一票否决 + 软性质量补充）。

核心设计：
- 第一层 硬性检查（代码层，快）：结构/叙事性/命盘数据违规 → 一票否决
- 第二层 软性评分（LLM，仅硬性通过时执行）：叙事性/通顺性/故事性/加粗合理性/术语通俗化

评分制：1-100 分（与现有反馈服务一致），软性评分门槛 70 分。
"""
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


async def evaluate_report(
    report: dict,
    user_question: str,
    chart_data: dict,
    is_first_reading: bool = False,
) -> dict:
    """分层评分主入口：硬性检查 → 软性评分。

    Args:
        report: 追问报告 JSON
        user_question: 用户原始问题
        chart_data: 命盘数据 dict
        is_first_reading: 是否首次报告

    Returns:
        {
            "overall_pass": bool,
            "hard_check": {"passed": bool, "violations": [...], "blocked_by": str},
            "soft_score": {"叙事性": 85, ...} | None,
            "fabrication": {...} | None,
            "avg_soft_score": float | None,
            "skip_reason": str | None
        }
    """
    # ===== 第一层：硬性检查（代码层，不调用 LLM）=====
    from app.services.eval.structure_checker import check_structure
    from app.services.eval.narrative_checker import check_narrative
    from app.services.eval.chart_usage_checker import check_chart_usage

    structure_violations = check_structure(report, user_question)
    narrative_violations = check_narrative(report, is_first_reading)
    chart_usage_violations = check_chart_usage(report, chart_data)

    all_hard_violations = structure_violations + narrative_violations + chart_usage_violations
    hard_passed = len(all_hard_violations) == 0

    # 确定被哪类硬性检查拦截
    blocked_by = None
    if not hard_passed:
        if structure_violations:
            blocked_by = "structure"
        elif narrative_violations:
            blocked_by = "narrative"
        elif chart_usage_violations:
            blocked_by = "chart_usage"

    hard_check = {
        "passed": hard_passed,
        "violations": all_hard_violations,
        "blocked_by": blocked_by,
        "structure_count": len(structure_violations),
        "narrative_count": len(narrative_violations),
        "chart_usage_count": len(chart_usage_violations),
    }

    # ===== 第二层：软性评分（无论硬性检查是否通过都执行）=====
    soft_score = await llm_score_narrative(report, user_question)
    # 把 user_question + birth_year 透传：编造检测要提取"用户问题涉及年份"来共用基准
    birth_year = None
    try:
        sizu = chart_data.get("四柱", "") if isinstance(chart_data, dict) else ""
    except Exception:
        sizu = ""
    fabrication = await llm_check_fabrication(report, chart_data, user_question=user_question, birth_year=birth_year)

    # 编造检测有 high 严重程度 → 也判定不合格
    fab_blocked = (
        fabrication.get("编造") is True
        and fabrication.get("严重程度") == "high"
    )

    # 软性评分门槛：各维度平均分 >= 70（1-100 分制）
    scores = [v for k, v in soft_score.items() if k not in ("问题",) and isinstance(v, (int, float))]
    avg_score = sum(scores) / len(scores) if scores else 0

    # 总体通过条件：硬性检查通过 + 编造未触发 + 软性评分达标
    overall_pass = hard_passed and (not fab_blocked) and (avg_score >= 70)

    # 如果硬性检查未通过，记录原因但保留软性评分结果
    skip_reason = None
    if not hard_passed:
        skip_reason = f"硬性检查未通过(blocked_by={blocked_by})，但软性评分已执行"

    return {
        "overall_pass": overall_pass,
        "hard_check": hard_check,
        "soft_score": soft_score,
        "fabrication": fabrication,
        "avg_soft_score": round(avg_score, 2),
        "skip_reason": skip_reason,
    }


async def llm_score_narrative(report: dict, user_question: str) -> dict:
    """用 qwen-flash 对报告打分（1-100 分），仅在硬性检查通过后调用。"""
    prompt = f"""请对以下命理追问报告评分（1-100 分），评估维度：
1. 叙事性：是否像给朋友讲故事，有起承转合
2. 通顺性：语句是否流畅自然
3. 故事性：是否有故事感，不堆砌术语
4. 加粗合理性：**加粗**是否用在关键词上，不滥用
5. 术语通俗化：命理术语是否用括号/= /也就是紧跟解释

注意：结构/术语/命盘数据等硬性错误已由代码检查器覆盖，你只需评估软性质量。

用户问题：{user_question}
报告：{json.dumps(report, ensure_ascii=False)[:3000]}

输出 JSON：{{"叙事性": 85, "通顺性": 90, "故事性": 75, "加粗合理性": 88, "术语通俗化": 82, "问题": ["..."]}}
"""
    return await _call_llm(prompt)


async def llm_check_fabrication(
    report: dict,
    chart_data: dict,
    user_question: str = "",
    birth_year: Optional[int] = None,
) -> dict:
    """用 LLM 判断输出是否编造了命盘未提供的信息（语义层补充）。

    关键：基准与报告生成时注入 prompt 的「命盘权威基准」完全一致
    （build_authoritative_chart_basis），避免"生成者拿了2027流月、检测器只看
    chart_data前2000字没写2027→误判编造"的系统性误报。
    """
    try:
        from app.services.skill_prompts import build_authoritative_chart_basis
        basis = build_authoritative_chart_basis(
            chart_data or {}, user_question or "", int(birth_year) if birth_year else 0
        )
    except Exception:
        basis = json.dumps(chart_data, ensure_ascii=False)[:2000]

    prompt = f"""命盘数据（权威来源，与报告生成者共用同一份）：
{basis}

LLM 生成的报告：
{json.dumps(report, ensure_ascii=False)[:3000]}

请按以下标准检查报告是否"编造"（必须严格区分"真编造"与"现实演绎"，演绎不算编造）：

【算编造，必须标记】
1. 命盘数据编造：报告提到的大运/流年/十神/用神忌神，与命盘不一致或命盘未列出（如命盘是戊申大运，报告写乙卯大运）
2. 与命盘完全矛盾：命盘标注凶月的月份，报告说成吉/平/适合行动（如12月大凶却说"最稳妥入职月"）
3. 无任何命盘依据的具体数字/事件：薪资倍数(1.3倍)、融资轮次(B轮)、涨幅百分比(30%)、具体日期(几号入职)、具体人物故事("表哥借钱不还")——命盘永远算不出这些

【不算编造·合理现实演绎，不要标记】
基于命盘吉凶/十神/五行做的现实场景化演绎属于合理演绎，不算编造：
- ✅ 劫财→同辈助力、竞争者退场（十神劫财演绎）
- ✅ 火土帮身→实业收益、务实型企业（五行帮身演绎）
- ✅ 冲主变动→换组换领导、岗位调整（冲合演绎）
- ✅ 吉月帮身→谈判筹码充足、薪资趋势向好、调薪通道顺畅（吉凶演绎）
- ✅ 喜用神→行业方向（内容/教育/文化）（用神演绎）
- ✅ 身强/比劫→话语权较大、能主导（身强弱演绎）

【团队/公司画像分情况】
话语权/中小团队/成长型企业/扁平化管理等团队画像，按有无命盘依据链区分：
- 该画像前后文能找到命盘依据链（如"火土帮身利实业→务实型成长企业"、"身强比劫旺→话语权较大"）→ 算演绎，不标记
- 完全孤立出现、前文无任何命盘依据链、纯凑话 → 算编造，标 medium

严重程度：命盘数据编造(类型1)/与命盘矛盾(类型2)/无依据数字事件(类型3)=high；纯凑话团队画像=medium

输出 JSON：{{"编造": true/false, "编造内容": ["..."], "严重程度": "high/medium/low"}}
"""
    return await _call_llm(prompt)


def _build_fabrication_basis(chart_data: dict, user_question: str = "", birth_year: Optional[int] = None) -> str:
    """同步导出的编造检测基准构建函数（与prompt注入基准同源），
    专供单元测试 / 离线调试使用，确保两边信息完全一致。"""
    try:
        from app.services.skill_prompts import build_authoritative_chart_basis
        return build_authoritative_chart_basis(
            chart_data or {}, user_question or "", int(birth_year) if birth_year else 0
        )
    except Exception:
        return json.dumps(chart_data, ensure_ascii=False)[:2000]


async def _call_llm(prompt: str) -> dict:
    """调用 qwen-flash，复用 model_pool。"""
    try:
        from app.services.ai_service import model_pool, get_client, build_llm_extra_body
        if not model_pool:
            return {"error": "model_pool 为空"}
        # 优先用 flash 模型，没有就用主模型
        flash_models = [m for m in model_pool if "flash" in m.name]
        model_config = flash_models[0] if flash_models else model_pool[0]
        client = await get_client(model_config)
        response = await client.chat.completions.create(
            model=model_config.name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"},
            timeout=30,
            extra_body=build_llm_extra_body(model_config.name),
        )
        raw = response.choices[0].message.content or ""
        return json.loads(raw)
    except Exception as e:
        logger.error(f"[LLM 评分] 调用失败：{e}")
        return {"error": str(e)}
