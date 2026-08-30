"""
评测中心 API：评测结果查询、badcase 管理、排盘回归测试、人工审核、Prompt 优化闭环
"""
import json
from typing import Annotated, Optional, List
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.eval_result import EvalResult
from app.models.badcase import BadCase
from app.models.prompt_review import PromptReview, PromptVersion

router = APIRouter(prefix="/api/admin", tags=["admin-eval"])

# 评测集路径
EVAL_DATASET_PATH = Path(__file__).parent.parent.parent / "tests" / "eval_dataset.json"


# ============================================================
# Pydantic Schemas
# ============================================================

class PromptReviewCreate(BaseModel):
    """提交人工审核请求"""
    eval_result_id: Optional[int] = None
    badcase_id: Optional[int] = None
    report_data: Optional[str] = None  # JSON string
    user_question: Optional[str] = None
    reviewer_id: Optional[int] = None
    review_result: str  # pass / improve / fail
    review_comment: Optional[str] = None
    problem_tags: Optional[List[str]] = None
    auto_add_to_dataset: bool = False


class RuleInjectRequest(BaseModel):
    """注入规则请求"""
    rule: str  # 提炼的规则文本
    rule_category: str  # 术语/结构/命盘数据/叙事性/时间因果
    confirm: bool = True


class PromptVersionRollback(BaseModel):
    """回滚请求"""
    confirm: bool = True


class EvalDatasetAddRequest(BaseModel):
    """添加用例到评测集"""
    description: str
    user_question: str
    report_data: Optional[str] = None  # JSON string
    expected_pass: bool = False
    expected_violations: List[str] = []
    review_comment: Optional[str] = None


@router.get("/eval-results")
async def list_eval_results(
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    dataset_id: Optional[str] = None,
    eval_type: Optional[str] = Query(None, description="评测类型筛选: report_quality/chart_accuracy/badcase_eval/production_monitor"),
):
    """评测结果列表"""
    conditions = []
    if dataset_id:
        conditions.append(EvalResult.dataset_id == dataset_id)
    if eval_type:
        conditions.append(EvalResult.eval_type == eval_type)

    total = (
        await db.execute(select(func.count()).select_from(EvalResult).where(*conditions))
    ).scalar() or 0

    rows = (
        await db.execute(
            select(EvalResult)
            .where(*conditions)
            .order_by(EvalResult.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    items = []
    for r in rows:
        # 使用持久化的指标，如果不存在则从detail计算
        if r.match_count is not None and r.match_rate is not None:
            match_count = r.match_count
            match_rate = r.match_rate
        else:
            detail = json.loads(r.detail) if r.detail else []
            match_count = sum(1 for case in detail if case.get("match", False))
            match_rate = match_count / len(detail) if detail else 0
        
        items.append({
            "id": r.id,
            "dataset_id": r.dataset_id,
            "eval_type": r.eval_type or "report_quality",  # 默认类型
            "total": r.total,
            "passed": r.passed,
            "failed": r.failed,
            "pass_rate": r.pass_rate,
            "format_pass_rate": r.format_pass_rate,
            "match_count": match_count,
            "match_rate": round(match_rate, 4),
            "task_completion_rate": r.task_completion_rate,
            "accuracy_rate": r.accuracy_rate,
            "soft_score": r.soft_score,
            "violation_distribution": r.violation_distribution,
            "created_at": r.created_at.isoformat(),
        })

    return {
        "total": total,
        "items": items,
    }


@router.get("/eval-results/{result_id}")
async def get_eval_result_detail(
    result_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """评测结果详情（含每条 case 的违规明细和匹配情况）"""
    r = await db.get(EvalResult, result_id)
    if not r:
        return {"error": "not found"}
    import json
    
    detail = json.loads(r.detail) if r.detail else []
    
    # 使用持久化的指标，如果不存在则从detail计算
    if r.match_count is not None and r.match_rate is not None:
        match_count = r.match_count
        match_rate = r.match_rate
    else:
        match_count = sum(1 for case in detail if case.get("match", False))
        match_rate = match_count / len(detail) if detail else 0
    
    return {
        "id": r.id,
        "dataset_id": r.dataset_id,
        "eval_type": r.eval_type or "report_quality",
        "total": r.total,
        "passed": r.passed,
        "failed": r.failed,
        "pass_rate": r.pass_rate,
        "format_pass_rate": r.format_pass_rate,
        "match_count": match_count,
        "match_rate": round(match_rate, 4),
        "task_completion_rate": r.task_completion_rate,
        "accuracy_rate": r.accuracy_rate,
        "soft_score": r.soft_score,
        "violation_distribution": r.violation_distribution,
        "detail": detail,
        "created_at": r.created_at.isoformat(),
    }


@router.get("/badcases")
async def list_badcases(
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    reviewed: Optional[int] = None,
    violation_type: Optional[str] = None,
):
    """badcase 列表"""
    conditions = []
    if reviewed is not None:
        conditions.append(BadCase.reviewed == reviewed)
    if violation_type:
        conditions.append(BadCase.violation_type.contains(violation_type))

    total = (
        await db.execute(select(func.count()).select_from(BadCase).where(*conditions))
    ).scalar() or 0

    rows = (
        await db.execute(
            select(BadCase)
            .where(*conditions)
            .order_by(BadCase.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": b.id,
                "person_id": b.person_id,
                "question": b.question,
                "chart_fingerprint": b.chart_fingerprint,
                "violation_type": b.violation_type,
                "violation_detail": b.violation_detail,
                "retry_count": b.retry_count,
                "final_status": b.final_status,
                "reviewed": b.reviewed,
                "extracted_rule": b.extracted_rule,
                "rule_category": b.rule_category,
                "created_at": b.created_at.isoformat(),
            }
            for b in rows
        ],
    }


@router.get("/badcases/{badcase_id}")
async def get_badcase_detail(
    badcase_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """badcase 详情（含 LLM 原始输出）"""
    b = await db.get(BadCase, badcase_id)
    if not b:
        return {"error": "not found"}
    import json
    return {
        "id": b.id,
        "person_id": b.person_id,
        "question": b.question,
        "chart_fingerprint": json.loads(b.chart_fingerprint) if b.chart_fingerprint else None,
        "violation_type": b.violation_type,
        "violation_detail": json.loads(b.violation_detail) if b.violation_detail else None,
        "raw_output": json.loads(b.raw_output) if b.raw_output else None,
        "retry_count": b.retry_count,
        "final_status": b.final_status,
        "reviewed": b.reviewed,
        "extracted_rule": b.extracted_rule,
        "rule_category": b.rule_category,
        "created_at": b.created_at.isoformat(),
    }


@router.put("/badcases/{badcase_id}")
async def update_badcase(
    badcase_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    reviewed: Optional[int] = None,
    extracted_rule: Optional[str] = None,
    rule_category: Optional[str] = None,
):
    """更新 badcase 审核状态和提炼规则"""
    b = await db.get(BadCase, badcase_id)
    if not b:
        return {"error": "not found"}
    if reviewed is not None:
        b.reviewed = reviewed
    if extracted_rule is not None:
        b.extracted_rule = extracted_rule
    if rule_category is not None:
        b.rule_category = rule_category
    await db.commit()
    return {"ok": True}


@router.get("/eval-chart-rules")
async def get_eval_chart_rules():
    """获取已审核提炼的规则列表（供 prompt 注入用）"""
    from app.db.session import SessionLocal
    from sqlalchemy import select
    from app.models.badcase import BadCase

    db = SessionLocal()
    try:
        rows = db.execute(
            select(BadCase.extracted_rule, BadCase.rule_category)
            .where(BadCase.reviewed == 2, BadCase.extracted_rule.isnot(None))
        ).all()
        return {
            "rules": [
                {"category": r.rule_category, "rule": r.extracted_rule}
                for r in rows
            ]
        }
    finally:
        db.close()


@router.get("/eval-compare")
async def compare_eval_results(
    db: Annotated[AsyncSession, Depends(get_db)],
    baseline_id: int = Query(..., description="基准版本ID"),
    current_id: int = Query(..., description="当前版本ID"),
):
    """
    迭代前后评测结果对比
    
    对比维度：
    - 总览：通过率变化、L2格式完成率变化
    - 用例级：新增通过/新增失败的用例列表
    - 违规分布：各违规类型的增减
    """
    import json
    
    # 获取两个版本的评测结果
    baseline = await db.get(EvalResult, baseline_id)
    current = await db.get(EvalResult, current_id)
    
    if not baseline or not current:
        return {"error": "评测结果不存在"}
    
    # 解析详细数据
    baseline_detail = json.loads(baseline.detail) if baseline.detail else []
    current_detail = json.loads(current.detail) if current.detail else []
    
    # 构建用例ID映射
    baseline_cases = {c.get("case_id"): c for c in baseline_detail}
    current_cases = {c.get("case_id"): c for c in current_detail}
    
    # 计算用例级变化
    improved = []  # 新增通过
    regressed = []  # 新增失败
    
    for case_id, case in current_cases.items():
        baseline_case = baseline_cases.get(case_id)
        if baseline_case:
            baseline_pass = baseline_case.get("pass", False)
            current_pass = case.get("pass", False)
            if not baseline_pass and current_pass:
                improved.append(case_id)
            elif baseline_pass and not current_pass:
                regressed.append(case_id)
    
    # 计算违规分布变化
    baseline_violations = {}
    current_violations = {}
    
    for case in baseline_detail:
        for v in case.get("violations", []):
            vtype = v.get("type", "unknown")
            baseline_violations[vtype] = baseline_violations.get(vtype, 0) + 1
    
    for case in current_detail:
        for v in case.get("violations", []):
            vtype = v.get("type", "unknown")
            current_violations[vtype] = current_violations.get(vtype, 0) + 1
    
    # 计算违规变化
    all_vtypes = set(baseline_violations.keys()) | set(current_violations.keys())
    violation_delta = {
        vtype: {
            "baseline": baseline_violations.get(vtype, 0),
            "current": current_violations.get(vtype, 0),
            "delta": current_violations.get(vtype, 0) - baseline_violations.get(vtype, 0),
        }
        for vtype in all_vtypes
    }
    
    # 计算L2格式完成率变化
    baseline_format_rate = baseline.format_pass_rate or 0.0
    current_format_rate = current.format_pass_rate or 0.0

    # 解析 task_completion_rate（L1-L4），JSON 列自动反序列化
    baseline_tcr = baseline.task_completion_rate if isinstance(baseline.task_completion_rate, dict) else None
    current_tcr = current.task_completion_rate if isinstance(current.task_completion_rate, dict) else None

    return {
        "baseline": {
            "id": baseline.id,
            "dataset_id": baseline.dataset_id,
            "total": baseline.total,
            "passed": baseline.passed,
            "failed": baseline.failed,
            "pass_rate": baseline.pass_rate,
            "format_pass_rate": baseline_format_rate,
            "task_completion_rate": baseline_tcr,
            "created_at": baseline.created_at.isoformat(),
        },
        "current": {
            "id": current.id,
            "dataset_id": current.dataset_id,
            "total": current.total,
            "passed": current.passed,
            "failed": current.failed,
            "pass_rate": current.pass_rate,
            "format_pass_rate": current_format_rate,
            "task_completion_rate": current_tcr,
            "created_at": current.created_at.isoformat(),
        },
        "delta": {
            "pass_rate": (current.pass_rate or 0) - (baseline.pass_rate or 0),
            "format_pass_rate": current_format_rate - baseline_format_rate,
            "passed_count": (current.passed or 0) - (baseline.passed or 0),
            "l1_technical": (current_tcr.get("l1_technical", 0) - baseline_tcr.get("l1_technical", 0)) if current_tcr and baseline_tcr else None,
            "l2_format": (current_tcr.get("l2_format", 0) - baseline_tcr.get("l2_format", 0)) if current_tcr and baseline_tcr else None,
            "l3_quality": (current_tcr.get("l3_quality", 0) - baseline_tcr.get("l3_quality", 0)) if current_tcr and baseline_tcr else None,
            "l4_satisfaction": (current_tcr.get("l4_satisfaction", 0) - baseline_tcr.get("l4_satisfaction", 0)) if current_tcr and baseline_tcr else None,
        },
        "case_level": {
            "improved": improved,  # 新增通过的用例
            "regressed": regressed,  # 新增失败的用例
            "improved_count": len(improved),
            "regressed_count": len(regressed),
        },
        "violation_distribution": violation_delta,
    }


@router.get("/eval-dataset")
async def get_eval_dataset():
    """获取评测集内容"""
    if not EVAL_DATASET_PATH.exists():
        return {"error": "评测集文件不存在"}
    
    with open(EVAL_DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    
    return {
        "total": len(dataset),
        "items": dataset,
    }


@router.get("/eval-trend")
async def get_eval_trend(
    db: Annotated[AsyncSession, Depends(get_db)],
    eval_type: Optional[str] = Query(None, description="评测类型"),
    metric_name: str = Query("match_rate", description="指标名称: match_rate/pass_rate/format_pass_rate"),
    limit: int = Query(10, ge=1, le=100),
):
    """获取指定评测类型的指标趋势"""
    conditions = []
    if eval_type:
        conditions.append(EvalResult.eval_type == eval_type)
    
    rows = (
        await db.execute(
            select(EvalResult)
            .where(*conditions)
            .order_by(EvalResult.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    
    # 反转顺序，让时间从早到晚
    rows = list(reversed(rows))
    
    trend_data = []
    for r in rows:
        # 根据指标名称获取对应的值
        if metric_name == "match_rate":
            value = r.match_rate if r.match_rate is not None else 0
        elif metric_name == "pass_rate":
            value = r.pass_rate if r.pass_rate is not None else 0
        elif metric_name == "format_pass_rate":
            value = r.format_pass_rate if r.format_pass_rate is not None else 0
        else:
            value = 0
        
        trend_data.append({
            "version_id": r.id,
            "version_name": f"v{r.id}",
            "value": round(value, 4),
            "created_at": r.created_at.isoformat(),
        })
    
    return {
        "metric_name": metric_name,
        "eval_type": eval_type,
        "trend": trend_data,
    }


@router.get("/eval-types")
async def get_eval_types(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取所有评测类型及其统计信息"""
    # 查询每种评测类型的数量和最新评测时间
    result = await db.execute(
        select(
            EvalResult.eval_type,
            func.count(EvalResult.id).label("count"),
            func.max(EvalResult.created_at).label("latest_time"),
        ).group_by(EvalResult.eval_type)
    )
    
    type_stats = {}
    for row in result:
        eval_type = row.eval_type or "report_quality"
        type_stats[eval_type] = {
            "count": row.count,
            "latest_time": row.latest_time.isoformat() if row.latest_time else None,
        }
    
    # 定义评测类型元数据
    type_metadata = {
        "report_quality": {
            "label": "报告质量评测",
            "description": "评估报告结构、术语、叙事性",
            "metrics": ["检测准确率", "L2格式完成率", "违规分布"],
        },
        "chart_accuracy": {
            "label": "排盘正确性评测",
            "description": "评估排盘算法准确性",
            "metrics": ["四柱准确率", "十神准确率", "大运准确率"],
        },
        "badcase_eval": {
            "label": "Badcase动态评测",
            "description": "验证违规修复效果",
            "metrics": ["修复率", "未修复数量"],
        },
        "production_monitor": {
            "label": "生产环境监控",
            "description": "监控线上报告质量",
            "metrics": ["L1技术完成率", "L2格式完成率", "L3质量完成率", "L4满意度"],
        },
    }
    
    # 合并统计信息和元数据
    result_types = []
    for eval_type, metadata in type_metadata.items():
        stats = type_stats.get(eval_type, {"count": 0, "latest_time": None})
        result_types.append({
            "type": eval_type,
            "label": metadata["label"],
            "description": metadata["description"],
            "metrics": metadata["metrics"],
            "count": stats["count"],
            "latest_time": stats["latest_time"],
        })
    
    return {
        "types": result_types,
    }


# ============================================================
# 人工审核 API
# ============================================================

@router.post("/prompt-review")
async def submit_prompt_review(
    review: PromptReviewCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """提交人工审核意见"""
    # 1. 保存审核记录
    db_review = PromptReview(
        eval_result_id=review.eval_result_id,
        badcase_id=review.badcase_id,
        report_data=review.report_data,
        user_question=review.user_question,
        reviewer_id=review.reviewer_id,
        review_result=review.review_result,
        review_comment=review.review_comment,
        problem_tags=review.problem_tags,
        auto_add_to_dataset=1 if review.auto_add_to_dataset else 0,
    )
    db.add(db_review)
    await db.commit()
    await db.refresh(db_review)

    # 2. 如果 review_result == "fail"，自动创建/更新 badcase
    if review.review_result == "fail" and review.badcase_id is None:
        # 创建新的 badcase
        db_badcase = BadCase(
            question=review.user_question or "未知问题",
            violation_type=",".join(review.problem_tags or []),
            violation_detail=json.dumps({"review_comment": review.review_comment}, ensure_ascii=False),
            raw_output=review.report_data,
            reviewed=1,  # 已审核
        )
        db.add(db_badcase)
        await db.commit()
        await db.refresh(db_badcase)

        # 更新 review 记录的 badcase_id
        db_review.badcase_id = db_badcase.id
        await db.commit()
        await db.refresh(db_review)

    # 3. 如果 auto_add_to_dataset == True，自动加入评测集
    if review.auto_add_to_dataset:
        await auto_add_to_eval_dataset(
            report_data=review.report_data,
            user_question=review.user_question or "未知问题",
            violation_types=review.problem_tags or [],
            review_comment=review.review_comment or "",
        )

    return {
        "id": db_review.id,
        "badcase_id": db_review.badcase_id,
        "review_result": db_review.review_result,
        "auto_added_to_dataset": review.auto_add_to_dataset,
    }


@router.get("/prompt-reviews")
async def list_prompt_reviews(
    db: Annotated[AsyncSession, Depends(get_db)],
    review_result: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
):
    """获取审核记录列表"""
    conditions = []
    if review_result:
        conditions.append(PromptReview.review_result == review_result)

    total = (
        await db.execute(select(func.count()).select_from(PromptReview).where(*conditions))
    ).scalar() or 0

    rows = (
        await db.execute(
            select(PromptReview)
            .where(*conditions)
            .order_by(PromptReview.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "eval_result_id": r.eval_result_id,
                "badcase_id": r.badcase_id,
                "user_question": r.user_question,
                "review_result": r.review_result,
                "review_comment": r.review_comment,
                "problem_tags": r.problem_tags,
                "auto_add_to_dataset": r.auto_add_to_dataset,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.post("/prompt-review/{review_id}/extract-rule")
async def extract_rule_with_llm(
    review_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """使用 LLM 辅助提炼规则"""
    # 1. 读取审核记录
    review = await db.get(PromptReview, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="审核记录不存在")

    # 2. 读取关联的 badcase（如果有）
    badcase = None
    if review.badcase_id:
        badcase = await db.get(BadCase, review.badcase_id)

    # 3. 构建 prompt
    prompt = f"""你是一个命理 AI 产品的评测专家。

用户问题：{review.user_question or "未知"}

审核意见：{review.review_comment or "无"}

问题标签：{", ".join(review.problem_tags or [])}

{"违规详情：" + (badcase.violation_detail or "") if badcase else ""}

{"LLM 输出（节选）：" + (badcase.raw_output or "")[:500] if badcase else ""}

请提炼一条精简规则（50-150 字），用于防止此类违规再次发生。
规则应该：
1. 明确指出什么是不允许的
2. 给出正确的做法示例
3. 简洁明了，可直接注入 prompt

规则："""

    # 4. 调用 LLM（简化版本，实际应该调用 ai_service）
    # 这里返回 prompt，前端可以调用 LLM API
    return {
        "prompt": prompt,
        "suggestion": "请调用 LLM API 生成规则建议",
    }


@router.post("/prompt-review/{review_id}/inject-prompt")
async def inject_rule_to_prompt(
    review_id: int,
    rule_request: RuleInjectRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """确认规则并注入 prompt"""
    if not rule_request.confirm:
        return {"error": "需要确认"}

    # 1. 读取审核记录
    review = await db.get(PromptReview, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="审核记录不存在")

    # 2. 更新 badcase 的 extracted_rule 和 reviewed=2
    if review.badcase_id:
        badcase = await db.get(BadCase, review.badcase_id)
        if badcase:
            badcase.extracted_rule = rule_request.rule
            badcase.rule_category = rule_request.rule_category
            badcase.reviewed = 2  # 已提炼规则
            await db.commit()

    # 3. 备份当前 prompt 到 prompt_versions 表
    # 读取当前 prompt（从 followup_structured.py）
    from app.services.followup_structured import FOLLOWUP_PROMPT_TEMPLATE
    current_prompt = FOLLOWUP_PROMPT_TEMPLATE

    # 创建版本记录
    version = PromptVersion(
        version=f"v{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        prompt_content=current_prompt,
        change_summary=f"注入规则：{rule_request.rule[:50]}...",
        changed_rules=[{"category": rule_request.rule_category, "rule": rule_request.rule}],
        related_badcases=[review.badcase_id] if review.badcase_id else [],
        created_by=str(review.reviewer_id or "unknown"),
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)

    # 4. 注入规则到 prompt 模板（动态注入，不需要重启）
    # 规则已经存储在 badcase 表中，followup_structured.py 会动态读取
    # 这里只需要标记 badcase.reviewed = 3（已注入）
    if review.badcase_id:
        badcase = await db.get(BadCase, review.badcase_id)
        if badcase:
            badcase.reviewed = 3  # 已注入
            await db.commit()

    return {
        "version_id": version.id,
        "version": version.version,
        "rule_injected": True,
        "badcase_updated": review.badcase_id is not None,
    }


@router.get("/prompt-versions")
async def list_prompt_versions(
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
):
    """获取 prompt 版本历史"""
    total = (
        await db.execute(select(func.count()).select_from(PromptVersion))
    ).scalar() or 0

    rows = (
        await db.execute(
            select(PromptVersion)
            .order_by(PromptVersion.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": v.id,
                "version": v.version,
                "change_summary": v.change_summary,
                "changed_rules": v.changed_rules,
                "related_badcases": v.related_badcases,
                "created_by": v.created_by,
                "created_at": v.created_at.isoformat(),
            }
            for v in rows
        ],
    }


@router.post("/prompt-versions/{version_id}/rollback")
async def rollback_prompt_version(
    version_id: int,
    rollback: PromptVersionRollback,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """回滚到指定 prompt 版本"""
    if not rollback.confirm:
        return {"error": "需要确认"}

    version = await db.get(PromptVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")

    # 回滚操作：将 prompt_content 写回 followup_structured.py
    # 注意：这是危险操作，需要谨慎
    # 实际实现应该备份当前文件，然后写入旧版本

    return {
        "version_id": version.id,
        "version": version.version,
        "rollback_initiated": True,
        "warning": "请手动将 prompt_content 写回 followup_structured.py",
    }


@router.post("/eval-dataset/add")
async def add_to_eval_dataset(
    request: EvalDatasetAddRequest,
):
    """添加用例到评测集"""
    return await auto_add_to_eval_dataset(
        report_data=request.report_data,
        user_question=request.user_question,
        violation_types=request.expected_violations,
        review_comment=request.review_comment,
        description=request.description,
    )


class RootCauseUpdateRequest(BaseModel):
    """更新问题归因请求"""
    category: str  # prompt_issue / code_bug / rule_too_strict / edge_case
    note: Optional[str] = None
    fixed_in_version: Optional[str] = None


@router.put("/eval-results/{result_id}/root-cause")
async def update_eval_result_root_cause(
    result_id: int,
    request: RootCauseUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """更新评测结果的问题归因"""
    r = await db.get(EvalResult, result_id)
    if not r:
        raise HTTPException(status_code=404, detail="评测结果不存在")

    detail = json.loads(r.detail) if r.detail else []

    # 更新第一条 detail 的 root_cause（生产监控每条只有一个 detail）
    if detail and isinstance(detail, list) and len(detail) > 0:
        if "root_cause" not in detail[0]:
            detail[0]["root_cause"] = {}
        detail[0]["root_cause"]["category"] = request.category
        detail[0]["root_cause"]["note"] = request.note or ""
        detail[0]["root_cause"]["fixed_in_version"] = request.fixed_in_version

        r.detail = json.dumps(detail, ensure_ascii=False)
        await db.commit()

        return {
            "ok": True,
            "result_id": result_id,
            "root_cause": detail[0]["root_cause"],
        }
    else:
        raise HTTPException(status_code=400, detail="无法更新归因信息")


class ExportBadcaseRequest(BaseModel):
    """导出 badcase 到评测集请求"""
    eval_result_id: int
    description: Optional[str] = None
    expected_violations: Optional[List[str]] = None


@router.post("/eval-results/export-badcase")
async def export_production_monitor_to_badcase(
    request: ExportBadcaseRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """将生产监控的未通过报告导出到评测集"""
    r = await db.get(EvalResult, request.eval_result_id)
    if not r:
        raise HTTPException(status_code=404, detail="评测结果不存在")

    if r.eval_type != "production_monitor":
        raise HTTPException(status_code=400, detail="仅支持生产监控类型的导出")

    detail = json.loads(r.detail) if r.detail else []
    if not detail or not isinstance(detail, list):
        raise HTTPException(status_code=400, detail="无有效详情数据")

    monitor_detail = detail[0]

    # 提取用户问题和报告数据
    user_question = monitor_detail.get("question_preview", "")
    response_preview = monitor_detail.get("response_preview", "")

    # 提取违规类型
    eval_result = monitor_detail.get("eval_result", {})
    violations = []
    if eval_result.get("l2_format", {}).get("total_violations", 0) > 0:
        violations.append("structure")
    if eval_result.get("l3_quality", {}).get("total_violations", 0) > 0:
        violations.append("narrative")

    # 使用请求中指定的违规类型（如果有）
    if request.expected_violations:
        violations = request.expected_violations

    # 生成描述
    description = request.description or f"生产监控-{monitor_detail.get('trigger_reason', 'unknown')}-{user_question[:30]}"

    # 调用已有的添加到评测集函数
    result = await auto_add_to_eval_dataset(
        report_data=None,  # 生产监控不存储完整报告，只存预览
        user_question=user_question,
        violation_types=violations,
        review_comment=f"生产监控ID: {r.id}, 触发原因: {monitor_detail.get('trigger_reason', '')}",
        description=description,
    )

    return {
        "ok": True,
        "badcase_id": result.get("case_id"),
        "message": f"已导出到评测集，用例ID: {result.get('case_id')}",
    }


@router.get("/failure-analysis")
async def get_failure_analysis(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(7, ge=1, le=90, description="分析最近多少天的数据"),
    min_occurrences: int = Query(2, ge=1, description="高频模式最少出现次数阈值"),
):
    """失败模式分析：统计最近 N 天生产监控数据中的高频违规模式，输出归因分布与改进建议"""
    from app.services.eval.failure_analyzer import analyze_failure_patterns

    return await analyze_failure_patterns(db, days=days, min_occurrences=min_occurrences)


class LayerReviewRequest(BaseModel):
    """分层人工复核请求"""
    layer: str  # l1 / l2 / l3 / llm
    verdict: str  # agree / disagree
    note: Optional[str] = None


VALID_LAYERS = {"l1", "l2", "l3", "llm"}


@router.put("/eval-results/{result_id}/layer-review")
async def update_eval_result_layer_review(
    result_id: int,
    request: LayerReviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """人工分层复核标注：对 L1/L2/L3/LLM 评分逐层标注认同或不认同"""
    if request.layer not in VALID_LAYERS:
        raise HTTPException(status_code=400, detail=f"无效层级，可选：{', '.join(sorted(VALID_LAYERS))}")
    if request.verdict not in ("agree", "disagree"):
        raise HTTPException(status_code=400, detail="verdict 仅支持 agree / disagree")

    r = await db.get(EvalResult, result_id)
    if not r:
        raise HTTPException(status_code=404, detail="评测结果不存在")

    detail = json.loads(r.detail) if r.detail else []
    if detail and isinstance(detail, list) and len(detail) > 0:
        if "layer_reviews" not in detail[0]:
            detail[0]["layer_reviews"] = {}
        detail[0]["layer_reviews"][request.layer] = {
            "verdict": request.verdict,
            "note": request.note or "",
            "reviewed_at": datetime.utcnow().isoformat(),
        }
        r.detail = json.dumps(detail, ensure_ascii=False)
        await db.commit()
        return {
            "ok": True,
            "result_id": result_id,
            "layer_reviews": detail[0]["layer_reviews"],
        }
    raise HTTPException(status_code=400, detail="无法更新分层复核信息")


# ============================================================
# 辅助函数
# ============================================================

async def auto_add_to_eval_dataset(
    report_data: Optional[str],
    user_question: str,
    violation_types: List[str],
    review_comment: str,
    description: Optional[str] = None,
) -> dict:
    """自动将审核不合格的 case 加入评测集"""
    # 1. 读取现有评测集
    if not EVAL_DATASET_PATH.exists():
        dataset = []
    else:
        with open(EVAL_DATASET_PATH, "r", encoding="utf-8") as f:
            dataset = json.load(f)

    # 2. 生成新 case ID
    new_id = f"review_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    # 3. 构建新 case
    new_case = {
        "id": new_id,
        "description": description or f"人工审核-{violation_types[0] if violation_types else '未知'}",
        "user_question": user_question,
        "report": json.loads(report_data) if report_data else None,
        "expected_pass": False,
        "expected_violations": violation_types,
        "review_comment": review_comment,
        "created_at": datetime.utcnow().isoformat(),
    }

    # 4. 追加到评测集
    dataset.append(new_case)

    # 5. 写回文件
    with open(EVAL_DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    return {
        "case_id": new_id,
        "added": True,
        "total_cases": len(dataset),
    }
