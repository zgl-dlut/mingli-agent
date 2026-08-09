import asyncio
import time
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
from app.db.session import get_db, async_session
from app.models.message import ChatMessage
from app.models.session import ChatSession
from app.models.user import User
from app.services.ai_service import generate_first_reading
from app.services.followup_structured import generate_followup_structured
from app.services.payment_service import deduct_points
from app.services.skill_prompts import validate_user_question
from app.services.format_normalizer import normalize_output  # 首次报告仍用

router = APIRouter(prefix="/api/chat", tags=["chat"])

# 追问生成的后台任务表：session_id -> asyncio.Task
# 任务独立于 SSE 连接运行，客户端断开（刷新）后任务继续，完成后存库并从表中移除
_generating_tasks: "dict[int, asyncio.Task]" = {}
# 任务开始时间戳：用于超时兜底，防止任务卡住导致用户永远无法发新问题
_generating_start: "dict[int, float]" = {}
# 超时阈值（秒）：超过此时间认为任务卡住，允许新请求强制清理
_GENERATING_TIMEOUT = 900
# 任务异常时存错误信息，供 generating-status 接口返回给前端提示
_generating_errors: "dict[int, str]" = {}


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

    # 重试判定：上一条消息是相同内容的 user 消息（中断后重问），免重复扣费、不存重复 user 消息
    last_msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    )
    last_msg = last_msg_result.scalar_one_or_none()
    is_retry_unanswered = (
        last_msg is not None
        and last_msg.role == "user"
        and (last_msg.content or "").strip() == (request.content or "").strip()
    )

    if not is_retry_unanswered:
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
    # else: 重试未回答的上一条问题，不扣费、不存重复 user 消息，直接用已有消息生成

    history_result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    history_messages = history_result.scalars().all()

    history_list = [{
        "role": msg.role,
        "content": msg.content,
    } for msg in history_messages]

    # 结构化追问：LLM 输出 JSON，前端直渲染（不走 Markdown 中间层）
    # 任务化：后台任务独立运行，SSE 断开（刷新）不影响生成，完成后存库并从任务表移除
    # 如果该 session 正在生成，拒绝新请求；超时兜底防止任务卡住导致用户永远无法发新问题
    if session_id in _generating_tasks:
        old_task = _generating_tasks[session_id]
        start = _generating_start.get(session_id, 0)
        if old_task.done() or (time.time() - start > _GENERATING_TIMEOUT):
            # 任务已完成但未清理（异常）或超时卡住，强制清理，允许新请求
            if not old_task.done():
                old_task.cancel()
            _generating_tasks.pop(session_id, None)
            _generating_start.pop(session_id, None)
            _generating_errors.pop(session_id, None)
        else:
            # 正在生成且未超时，拒绝新请求
            raise HTTPException(status_code=409, detail="正在生成中，请稍候完成后再发送新问题")
    # 提取 ORM 属性到普通变量，避免后台任务访问已关闭的请求级 session
    bazi_data = session.bazi_data_json
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(
        _generate_and_save(
            session_id=session_id,
            bazi_data=bazi_data,
            gender=person.gender,
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            location=person.birth_location,
            question=request.content,
            history=history_list,
            queue=queue,
            longitude=person.birth_lng,
            latitude=person.birth_lat,
        )
    )
    _generating_tasks[session_id] = task
    _generating_start[session_id] = time.time()

    async def stream_response() -> AsyncGenerator[str, None]:
        # 从队列读 chunk 推送给前端；客户端断开后任务继续，队列堆积直到任务完成
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    return StreamingResponse(stream_response(), media_type="text/event-stream")


async def _generate_and_save(
    session_id: int,
    bazi_data,
    gender: str,
    birth_date: str,
    birth_time: str,
    location: str,
    question: str,
    history: list,
    queue: asyncio.Queue,
    longitude: float,
    latitude: float,
) -> None:
    """后台生成追问报告并存库，独立于 SSE 连接。客户端断开后任务继续运行。"""
    import traceback
    print(f"[_generate_and_save] 开始 session_id={session_id} question={question[:30]}", flush=True)
    try:
        # 独立 db session，不依赖请求级 session（请求结束后请求级 session 会关闭）
        async with async_session() as db:
            full_json = ""
            async for chunk in generate_followup_structured(
                analysis_data=bazi_data,
                gender=gender,
                birth_date=birth_date,
                birth_time=birth_time,
                location=location,
                user_question=question,
                history=history,
                longitude=longitude,
                latitude=latitude,
            ):
                full_json += chunk
                await queue.put(chunk)
            # 存库：content 存 JSON 字符串（前端解析后用 React 组件渲染）
            assistant_message = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=full_json,
            )
            db.add(assistant_message)
            await db.commit()
            await queue.put("\n\n__SAVED__")  # 存库完成标记，前端收到后拉取消息
            print(f"[_generate_and_save] 完成 session_id={session_id} json_len={len(full_json)}", flush=True)
    except Exception as e:
        print(f"[_generate_and_save] 异常 session_id={session_id} {type(e).__name__}: {e}\n{traceback.format_exc()}", flush=True)
        _generating_errors[session_id] = f"{type(e).__name__}: {e}"
        await queue.put(f"\n\n__ERROR__:{type(e).__name__}: {e}")
    finally:
        await queue.put(None)  # 结束标记，stream_response 收到后停止
        _generating_tasks.pop(session_id, None)
        _generating_start.pop(session_id, None)
        print(f"[_generate_and_save] 结束 session_id={session_id}", flush=True)


@router.get("/sessions/{session_id}/generating-status")
async def get_generating_status(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """查询该会话是否正在后台生成追问报告（用于刷新后恢复进度条）。"""
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise ResourceNotFound("会话不存在")
    from app.models.person import Person
    person_result = await db.execute(select(Person).where(Person.id == session.person_id))
    person = person_result.scalar_one_or_none()
    if not person or person.user_id != current_user.id:
        raise PermissionDenied("无权访问")
    # 任务异常时返回 error（一次性 pop，前端轮询发现后显示提示）
    error = _generating_errors.pop(session_id, None)
    return {"generating": session_id in _generating_tasks, "error": error}


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
