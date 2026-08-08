from datetime import datetime, timedelta
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.config import settings
from app.core.exceptions import PermissionDenied, ResourceNotFound
from app.db.session import get_db
from app.models.message import ChatMessage
from app.models.session import ChatSession
from app.models.user import User
from app.services.ai_service import generate_first_reading
from app.services.followup_structured import generate_followup_structured
from app.services.payment_service import deduct_points
from app.services.skill_prompts import validate_user_question
from app.services.format_normalizer import normalize_output  # 首次报告仍用

router = APIRouter(prefix="/api/chat", tags=["chat"])


class MessageRequest(BaseModel):
    content: str


@router.get("/sessions")
async def get_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    from app.models.person import Person
    
    result = await db.execute(
        select(ChatSession).join(Person, ChatSession.person_id == Person.id).where(Person.user_id == current_user.id)
    )
    sessions = result.scalars().all()
    
    session_list = []
    for session in sessions:
        person_result = await db.execute(select(Person).where(Person.id == session.person_id))
        person = person_result.scalar_one_or_none()
        
        session_list.append({
            "id": session.id,
            "person_id": session.person_id,
            "person_name": person.name if person else "",
            "title": session.title,
            "bazi_data": session.bazi_data_json,
            "astro_data": session.astro_data_json,
            "updated_at": session.updated_at.isoformat(),
        })
    
    return session_list


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise ResourceNotFound("会话不存在")
    
    from app.models.person import Person
    person_result = await db.execute(select(Person).where(Person.id == session.person_id))
    person = person_result.scalar_one_or_none()
    
    if not person or person.user_id != current_user.id:
        raise PermissionDenied("无权访问")
    
    message_result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    messages = message_result.scalars().all()
    
    return [{
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "created_at": msg.created_at.isoformat(),
    } for msg in messages]


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    request: MessageRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise ResourceNotFound("会话不存在")
    
    from app.models.person import Person
    person_result = await db.execute(select(Person).where(Person.id == session.person_id))
    person = person_result.scalar_one_or_none()
    
    if not person or person.user_id != current_user.id:
        raise PermissionDenied("无权访问")
    
    # 验证用户问题是否有效
    is_valid, error_msg = validate_user_question(request.content)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    await deduct_points(
        db, current_user.id, settings.POINTS_FOLLOW_UP,
        f"追问: {request.content[:30]}..."
    )

    # 去重检查：10秒内相同的用户消息不重复保存（防止前端双击/竞态重复提交）
    # 超过10秒后允许用户合法重复追问相同问题，避免吞掉用户消息导致前端不显示
    dedup_cutoff = datetime.utcnow() - timedelta(seconds=10)
    recent_user_msg = await db.execute(
        select(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "user",
            ChatMessage.content == request.content,
            ChatMessage.created_at > dedup_cutoff,
        ).order_by(ChatMessage.created_at.desc()).limit(1)
    )
    existing_msg = recent_user_msg.scalar_one_or_none()
    if not existing_msg:
        user_message = ChatMessage(
            session_id=session_id,
            role="user",
            content=request.content,
        )
        db.add(user_message)
        await db.commit()

    history_result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    history_messages = history_result.scalars().all()

    history_list = [{
        "role": msg.role,
        "content": msg.content,
    } for msg in history_messages]

    # 结构化追问：LLM 输出 JSON，前端直渲染（不走 Markdown 中间层）
    async def stream_response() -> AsyncGenerator[str, None]:
        # 二次去重检查：防止并发请求生成重复的AI回复
        recent_assistant = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "assistant",
            ).order_by(ChatMessage.created_at.desc()).limit(1)
        )
        last_assistant = recent_assistant.scalar_one_or_none()
        if last_assistant and last_assistant.content:
            pass  # 正常情况下不会触发，仅防止极端并发

        full_json = ""
        async for chunk in generate_followup_structured(
            analysis_data=session.bazi_data_json,
            gender=person.gender,
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            location=person.birth_location,
            user_question=request.content,
            history=history_list,
        ):
            full_json += chunk
            yield chunk

        # 存库：content 存 JSON 字符串（前端解析后用 React 组件渲染）
        assistant_message = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=full_json,
        )
        db.add(assistant_message)
        await db.commit()
        yield "\n\n__SAVED__"  # 存库完成标记，前端收到后拉取消息
    
    return StreamingResponse(stream_response(), media_type="text/event-stream")


@router.get("/sessions/{session_id}/first-reading")
async def get_first_reading(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise ResourceNotFound("会话不存在")
    
    from app.models.person import Person
    person_result = await db.execute(select(Person).where(Person.id == session.person_id))
    person = person_result.scalar_one_or_none()
    
    if not person or person.user_id != current_user.id:
        raise PermissionDenied("无权访问")

    # 确保命盘信息用户消息存在（首次报告的"发送内容"）
    existing_user_msg = await db.execute(
        select(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "user"
        ).limit(1)
    )
    if not existing_user_msg.scalar_one_or_none():
        calendar_label = "公历" if person.calendar_type == "solar" else "农历"
        user_content = f"出生时间：{person.birth_date} {person.birth_time}({calendar_label})\n出生地点：{person.birth_location}\n性别：{'男' if person.gender == 'male' else '女'}"
        user_message = ChatMessage(
            session_id=session_id,
            role="user",
            content=user_content,
        )
        db.add(user_message)
        await db.commit()

    message_result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "assistant"
        ).order_by(ChatMessage.created_at)
    )
    assistant_messages = message_result.scalars().all()
    
    if assistant_messages:
        return {"content": assistant_messages[0].content}
    
    async def stream_response() -> AsyncGenerator[str, None]:
        # 二次检查：防止并发请求绕过首次检查（第227行）导致重复生成
        recheck = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "assistant"
            ).limit(1)
        )
        if recheck.scalar_one_or_none():
            return  # 已有 assistant 消息，不再生成

        full_content = ""
        async for chunk in generate_first_reading(
            session.bazi_data_json,
            session.astro_data_json,
            person.gender,
            f"{person.birth_date} {person.birth_time}",
            person.birth_location,
            person.birth_lng,
            person.birth_lat,
        ):
            full_content += chunk
            # SSE流中实时移除【】（字符串替换，非正则，确保流期间也不显示【】）
            yield chunk.replace('【', '').replace('】', '')

        # 格式归一化：在保存前确保格式合规（首次报告保留 ### 标题，不转换为加粗）
        normalized_content = normalize_output(full_content, preserve_h3=True)
        
        assistant_message = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=normalized_content,
        )
        db.add(assistant_message)
        await db.commit()
        yield "\n\n__SAVED__"  # 存库完成标记，前端收到后拉取消息
    
    return StreamingResponse(stream_response(), media_type="text/event-stream")
