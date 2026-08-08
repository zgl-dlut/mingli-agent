"""
反馈管理 API - 标签管理、人工打分、模型自评、Prompt反哺
"""
import asyncio
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.feedback_service import (
    save_feedback,
    get_feedback,
    list_feedback,
    get_feedback_stats,
    update_feedback_score,
    delete_feedback,
    auto_tag_question,
    get_tag_label,
    model_self_score,
    TAG_LABELS,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class SaveFeedbackRequest(BaseModel):
    question: str
    answer: str
    person_name: str = ""
    model_name: str = ""
    is_first_reading: bool = False


class UpdateScoreRequest(BaseModel):
    human_score: Optional[int] = None
    human_comment: Optional[str] = None


@router.post("/")
async def create_feedback(req: SaveFeedbackRequest):
    """保存反馈记录（带自动标签）"""
    tag = auto_tag_question(req.question)
    record_id = save_feedback(
        question=req.question,
        answer=req.answer,
        person_name=req.person_name,
        model_name=req.model_name,
        is_first_reading=req.is_first_reading,
    )
    return {"id": record_id, "tag": tag, "tag_label": get_tag_label(tag)}


@router.get("/")
async def query_feedback(
    tag: Optional[str] = None,
    min_model_score: Optional[int] = None,
    max_model_score: Optional[int] = None,
    min_human_score: Optional[int] = None,
    max_human_score: Optional[int] = None,
    keyword: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """查询反馈列表（支持多条件筛选）"""
    return list_feedback(
        tag=tag,
        min_model_score=min_model_score,
        max_model_score=max_model_score,
        min_human_score=min_human_score,
        max_human_score=max_human_score,
        keyword=keyword,
        offset=offset,
        limit=limit,
    )


@router.get("/{record_id}")
async def get_feedback_detail(record_id: int):
    """获取单条反馈详情"""
    result = get_feedback(record_id)
    if not result:
        raise HTTPException(status_code=404, detail="记录不存在")
    return result


@router.put("/{record_id}")
async def update_feedback(record_id: int, req: UpdateScoreRequest):
    """更新人工打分和评论"""
    result = update_feedback_score(
        record_id=record_id,
        human_score=req.human_score,
        human_comment=req.human_comment,
    )
    if not result:
        raise HTTPException(status_code=400, detail="无有效更新内容")
    return {"success": True, "id": record_id}


@router.delete("/{record_id}")
async def remove_feedback(record_id: int):
    """删除反馈记录"""
    result = delete_feedback(record_id)
    return {"success": True}


@router.get("/stats/overview")
async def get_stats():
    """获取统计概览"""
    return get_feedback_stats()


@router.post("/{record_id}/model-score")
async def trigger_model_score(record_id: int):
    """触发模型自评打分"""
    record = get_feedback(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    result = await model_self_score(
        question=record["question"],
        answer=record["answer"],
    )

    # 更新模型打分
    conn_result = update_feedback_score(
        record_id=record_id,
    )
    # 直接更新 model_score
    import sqlite3
    conn = sqlite3.connect("feedback.db")
    conn.execute(
        "UPDATE feedback_records SET model_score = ?, model_reason = ? WHERE id = ?",
        (result["score"], result["reason"], record_id),
    )
    conn.commit()
    conn.close()

    return {"id": record_id, "model_score": result["score"], "reason": result["reason"]}


@router.get("/tags/list")
async def list_tags():
    """获取所有可用标签"""
    tags = []
    for key, label in TAG_LABELS.items():
        tags.append({"key": key, "label": label})
    return {"tags": tags}


@router.post("/{record_id}/auto-model-score")
async def auto_score_existing(record_id: int):
    """对已存记录自动评分（后台任务）"""
    record = get_feedback(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    if record.get("model_score") is not None:
        return {"id": record_id, "model_score": record["model_score"], "reason": "已有打分"}

    # 异步执行
    async def _do_score():
        result = await model_self_score(record["question"], record["answer"])
        import sqlite3
        conn = sqlite3.connect("feedback.db")
        conn.execute(
            "UPDATE feedback_records SET model_score = ?, model_reason = ? WHERE id = ?",
            (result["score"], result["reason"], record_id),
        )
        conn.commit()
        conn.close()

    asyncio.create_task(_do_score())
    return {"id": record_id, "status": "scoring"}