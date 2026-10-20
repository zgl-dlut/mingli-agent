"""AI 深度解读 API（两段式第二段）

- GET  /api/deep-reading/{message_id}         查看某条大纲消息：框架 + 是否已解锁 + 正文
- PATCH /api/deep-reading/{message_id}        修改大纲（仅未解锁时允许）
- POST /api/deep-reading/{message_id}/unlock  扣积分解锁正文（幂等：已解锁直接返回，不重复扣费）

契约（与前端 src/api/deepReading.ts 对齐）：
- 字段全英文 snake_case
- 大纲消息 content 结构：{"kind":"outline","question","verdict","subtopics":[{title,lead}],["detail":FollowupReport]}
- 解锁即把 detail 写入该消息 content，并在 content_unlocks 落一条付费记录
"""

import json
import logging
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.config import settings
from app.core.exceptions import PermissionDenied, ResourceNotFound
from app.db.session import async_session, get_db
from app.models.content_unlock import ContentUnlock
from app.models.message import ChatMessage
from app.models.person import Person
from app.models.session import ChatSession
from app.models.usage_log import AiUsageLog
from app.models.user import User
from app.services.followup_structured import generate_followup_structured
from app.services.payment_service import check_points, deduct_points
from app.skills.orchestrator import generate_full_analysis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/deep-reading", tags=["deep-reading"])


# ============================================================
# 请求 / 响应模型
# ============================================================

class OutlineItem(BaseModel):
    title: str
    lead: str = ""


class UpdateOutlineRequest(BaseModel):
    subtopics: List[OutlineItem]


class DeepReadingResponse(BaseModel):
    message_id: int
    session_id: int
    person_id: int
    person_name: str = ""
    question: str = ""
    verdict: str = ""
    subtopics: List[OutlineItem] = []
    unlocked: bool = False
    report: Optional[Dict[str, Any]] = None   # 已解锁时为完整 FollowupReport
    unlock_points: int = 0                     # 解锁所需积分（供前端展示）


# ============================================================
# 工具
# ============================================================

async def _load_owned(db: AsyncSession, message_id: int, user: User):
    """加载消息并校验归属，返回 (message, session, person)。"""
    result = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise ResourceNotFound("消息不存在")

    s_result = await db.execute(select(ChatSession).where(ChatSession.id == msg.session_id))
    session = s_result.scalar_one_or_none()
    if not session:
        raise ResourceNotFound("会话不存在")

    p_result = await db.execute(select(Person).where(Person.id == session.person_id))
    person = p_result.scalar_one_or_none()
    if not person or person.user_id != user.id:
        raise PermissionDenied("无权访问")

    return msg, session, person


def _parse_outline(content: str) -> Optional[Dict[str, Any]]:
    """解析大纲消息 content；非大纲消息返回 None。"""
    if not content or not content.strip().startswith("{"):
        return None
    try:
        data = json.loads(content)
    except (TypeError, ValueError):
        return None
    if isinstance(data, dict) and data.get("kind") == "outline":
        return data
    return None


def _to_response(message_id: int, session: ChatSession, person: Person, outline: Dict[str, Any]) -> DeepReadingResponse:
    detail = outline.get("detail")
    return DeepReadingResponse(
        message_id=message_id,
        session_id=session.id,
        person_id=person.id,
        person_name=person.name or "",
        question=str(outline.get("question") or ""),
        verdict=str(outline.get("verdict") or ""),
        subtopics=[OutlineItem(**it) for it in (outline.get("subtopics") or []) if isinstance(it, dict)],
        unlocked=isinstance(detail, dict),
        report=detail if isinstance(detail, dict) else None,
        unlock_points=settings.POINTS_DEEP_READING,
    )


# ============================================================
# 查看大纲
# ============================================================

@router.get("/{message_id}", response_model=DeepReadingResponse)
async def get_deep_reading(
    message_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    msg, session, person = await _load_owned(db, message_id, current_user)
    outline = _parse_outline(msg.content or "")
    if not outline:
        raise HTTPException(status_code=400, detail="该消息不是深度解读大纲")
    return _to_response(msg.id, session, person, outline)


# ============================================================
# 修改大纲（仅未解锁时）
# ============================================================

@router.patch("/{message_id}", response_model=DeepReadingResponse)
async def update_outline(
    message_id: int,
    request: UpdateOutlineRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    msg, session, person = await _load_owned(db, message_id, current_user)
    outline = _parse_outline(msg.content or "")
    if not outline:
        raise HTTPException(status_code=400, detail="该消息不是深度解读大纲")
    if isinstance(outline.get("detail"), dict):
        raise HTTPException(status_code=400, detail="正文已解锁，大纲不可再修改")

    cleaned = [
        {"title": it.title.strip()[:30], "lead": (it.lead or "").strip()[:80]}
        for it in request.subtopics if it.title and it.title.strip()
    ]
    if len(cleaned) < 1:
        raise HTTPException(status_code=400, detail="大纲至少保留一个维度")

    outline["subtopics"] = cleaned
    msg.content = json.dumps(outline, ensure_ascii=False)
    await db.commit()
    return _to_response(msg.id, session, person, outline)


# ============================================================
# 解锁正文
# ============================================================

@router.post("/{message_id}/unlock", response_model=DeepReadingResponse)
async def unlock_deep_reading(
    message_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    msg, session, person = await _load_owned(db, message_id, current_user)
    outline = _parse_outline(msg.content or "")
    if not outline:
        raise HTTPException(status_code=400, detail="该消息不是深度解读大纲")

    # 幂等：已解锁直接返回，不重复扣费
    if isinstance(outline.get("detail"), dict):
        return _to_response(msg.id, session, person, outline)

    required = settings.POINTS_DEEP_READING
    if not await check_points(db, current_user.id, required):
        raise HTTPException(status_code=400, detail={
            "code": "insufficient_points",
            "required": required,
            "message": f"积分不足，解锁深度解读需要{required}积分",
        })

    await deduct_points(
        db, current_user.id, required,
        f"深度解读解锁: {str(outline.get('question') or '')[:30]}",
        biz_type="deep_reading",
    )

    # 生成正文（严格遵循已展示的大纲标题与顺序）
    titles = [it.get("title", "") for it in (outline.get("subtopics") or []) if isinstance(it, dict)]
    question = str(outline.get("question") or "")

    bazi_data = person.bazi_data_json
    if isinstance(bazi_data, str):
        try:
            bazi_data = json.loads(bazi_data)
        except (TypeError, ValueError):
            bazi_data = None
    if not bazi_data:
        bazi_data = generate_full_analysis(
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            longitude=person.birth_lng,
            latitude=person.birth_lat,
            gender=person.gender,
            location=person.birth_location,
        )
        person.bazi_data_json = bazi_data
        await db.commit()

    # 会话历史（不含本条大纲消息），供正文生成复用上下文
    h_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id, ChatMessage.id != msg.id)
        .order_by(ChatMessage.created_at)
    )
    history = [{"role": m.role, "content": m.content} for m in h_result.scalars().all()]

    usage_holder: dict = {}
    full_json = ""
    try:
        async for chunk in generate_followup_structured(
            analysis_data=bazi_data,
            gender=person.gender,
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            location=person.birth_location,
            user_question=question,
            history=history,
            longitude=person.birth_lng,
            latitude=person.birth_lat,
            usage_holder=usage_holder,
            outline_titles=titles or None,
        ):
            if chunk.startswith("__PROGRESS__"):
                continue
            full_json += chunk
    except Exception as e:
        logger.error(f"[深度解读] 正文生成失败 message_id={message_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="深度解读正文生成失败，请稍后重试")

    try:
        detail = json.loads(full_json)
    except (TypeError, ValueError):
        raise HTTPException(status_code=500, detail="深度解读正文解析失败，请稍后重试")

    outline["detail"] = detail
    msg.content = json.dumps(outline, ensure_ascii=False)

    exists = await db.execute(
        select(ContentUnlock).where(
            ContentUnlock.user_id == current_user.id,
            ContentUnlock.message_id == msg.id,
        )
    )
    if not exists.scalar_one_or_none():
        db.add(ContentUnlock(
            user_id=current_user.id,
            message_id=msg.id,
            unlock_type="points",
            points_cost=required,
        ))
    await db.commit()

    # 用量落库（不影响主流程）
    try:
        async with async_session() as usage_db:
            usage_db.add(AiUsageLog(
                user_id=current_user.id,
                session_id=session.id,
                biz_type="deep_reading",
                input_tokens=usage_holder.get("input_tokens", 0),
                output_tokens=usage_holder.get("output_tokens", 0),
                total_tokens=usage_holder.get("total_tokens", 0),
                model=usage_holder.get("model", ""),
                success=bool(usage_holder.get("success", bool(detail))),
                duration_ms=0,
            ))
            await usage_db.commit()
    except Exception as e:
        logger.warning(f"[深度解读] 用量落库失败: {type(e).__name__}: {e}")

    return _to_response(msg.id, session, person, outline)
