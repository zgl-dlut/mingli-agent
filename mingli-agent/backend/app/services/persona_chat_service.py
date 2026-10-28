from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import PermissionDenied, ResourceNotFound, V3APIError
from app.models.person import Person
from app.models.persona import Persona
from app.models.persona_conversation import PersonaConversation
from app.models.persona_memory import PersonaMemory
from app.models.persona_message import PersonaMessage
from app.services.ai_service import generate_ai_response
from app.services.chart_snapshot_service import get_or_create_chart_snapshot
from app.services.entitlement_service import consume_usage
from app.services.persona_memory_service import get_or_create_memory, update_memory_summary
from app.services.persona_profile_service import PERSONA_PROMPT_VERSION
from app.services.persona_prompt_service import build_persona_prompt
from app.services.safety_service import (
    CRISIS_REPLY,
    detect_input_safety,
    filter_persona_output,
    record_safety_event,
)


PERSONA_TURN_LIMIT = 20


async def require_persona_enabled() -> None:
    if not settings.V3_ENABLED:
        raise V3APIError(403, "feature_disabled", "V3 功能尚未开放")
    if not settings.PERSONA_ENABLED:
        raise V3APIError(403, "feature_disabled", "命局人格尚未开放")


async def get_owned_persona(
    db: AsyncSession,
    persona_id: int,
    user_id: int,
) -> Persona:
    persona = await db.get(Persona, persona_id)
    if not persona:
        raise ResourceNotFound("命局人格不存在")
    if persona.user_id != user_id:
        raise PermissionDenied("无权访问该命局人格")
    return persona


async def get_owned_conversation(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
) -> PersonaConversation:
    conversation = await db.get(PersonaConversation, conversation_id)
    if not conversation:
        raise ResourceNotFound("人格会话不存在")
    if conversation.user_id != user_id:
        raise PermissionDenied("无权访问该会话")
    return conversation


async def create_conversation(
    db: AsyncSession,
    persona: Persona,
    title: str | None,
) -> PersonaConversation:
    await consume_usage(
        db,
        persona.user_id,
        "persona_session_monthly",
        scope_id="",
    )
    conversation = PersonaConversation(
        persona_id=persona.id,
        user_id=persona.user_id,
        title=(title or "新的对话").strip()[:120] or "新的对话",
    )
    db.add(conversation)
    await db.commit()
    return conversation


def rest_reminder_required(conversation: PersonaConversation) -> bool:
    return datetime.utcnow() - conversation.started_at >= timedelta(hours=2)


async def handle_crisis_message(
    db: AsyncSession,
    conversation: PersonaConversation,
    content: str,
) -> tuple[PersonaMessage, PersonaMessage]:
    user_message = PersonaMessage(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
        role="user",
        content=content,
        safety_category="crisis",
        prompt_version=PERSONA_PROMPT_VERSION,
    )
    assistant_message = PersonaMessage(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
        role="assistant",
        content=CRISIS_REPLY,
        safety_category="crisis",
        prompt_version=PERSONA_PROMPT_VERSION,
    )
    db.add_all([user_message, assistant_message])
    await record_safety_event(
        db,
        conversation.user_id,
        category="crisis",
        action="role_exited",
        persona_id=conversation.persona_id,
        conversation_id=conversation.id,
        metadata={"input_stored": True, "llm_called": False},
    )
    conversation.last_message_at = datetime.utcnow()
    await db.commit()
    return user_message, assistant_message


async def prepare_normal_message(
    db: AsyncSession,
    conversation: PersonaConversation,
    content: str,
) -> tuple[Persona, Person, PersonaMessage, PersonaMemory, list[dict], bool]:
    now = datetime.utcnow()
    turn_update = await db.execute(
        update(PersonaConversation)
        .where(
            PersonaConversation.id == conversation.id,
            PersonaConversation.user_id == conversation.user_id,
            PersonaConversation.closed_at.is_(None),
            PersonaConversation.user_turn_count < PERSONA_TURN_LIMIT,
        )
        .values(
            user_turn_count=PersonaConversation.user_turn_count + 1,
            last_message_at=now,
        )
    )
    if turn_update.rowcount != 1:
        await db.refresh(conversation)
        if conversation.closed_at is not None:
            raise V3APIError(409, "conversation_closed", "当前会话已结束")
        raise V3APIError(
            409,
            "conversation_turn_limit",
            "本次会话已达到 20 个用户回合，请新建会话继续",
            metric="persona_turn",
            remaining=0,
        )
    await db.refresh(conversation)
    persona = await get_owned_persona(db, conversation.persona_id, conversation.user_id)
    person = await db.get(Person, persona.person_id)
    if not person:
        raise ResourceNotFound("本人档案不存在")
    memory = await get_or_create_memory(db, persona.id, persona.user_id)
    user_message = PersonaMessage(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
        role="user",
        content=content,
        prompt_version=PERSONA_PROMPT_VERSION,
    )
    db.add(user_message)
    if conversation.user_turn_count == 1 and conversation.title == "新的对话":
        conversation.title = content.strip().replace("\n", " ")[:28] or "新的对话"
    await db.flush()
    recent_rows = (
        await db.execute(
            select(PersonaMessage)
            .where(PersonaMessage.conversation_id == conversation.id)
            .order_by(PersonaMessage.created_at.desc(), PersonaMessage.id.desc())
            .limit(12)
        )
    ).scalars().all()
    recent_messages = [
        {"role": message.role, "content": message.content}
        for message in reversed(recent_rows)
        if message.safety_category is None
    ]
    await db.commit()
    return (
        persona,
        person,
        user_message,
        memory,
        recent_messages,
        rest_reminder_required(conversation),
    )


async def generate_and_save_reply(
    db: AsyncSession,
    conversation: PersonaConversation,
    persona: Persona,
    person: Person,
    memory: PersonaMemory,
    recent_messages: list[dict],
) -> tuple[PersonaMessage, bool]:
    snapshot = await get_or_create_chart_snapshot(db, person)
    memory_summary = memory.summary_json if memory.enabled else None
    system_prompt = build_persona_prompt(
        snapshot.model_dump(mode="json"),
        persona.profile_json,
        memory_summary,
    )
    full_answer = ""
    async for chunk in generate_ai_response(
        system_prompt,
        recent_messages,
        stream=True,
    ):
        full_answer += chunk
    full_answer = full_answer.strip() or "我暂时没有组织好回答。我们可以换一个更具体的角度继续聊。"
    filtered_answer, violation = filter_persona_output(full_answer)
    assistant_message = PersonaMessage(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
        role="assistant",
        content=filtered_answer,
        safety_category=violation,
        prompt_version=PERSONA_PROMPT_VERSION,
    )
    db.add(assistant_message)
    if violation:
        await record_safety_event(
            db,
            conversation.user_id,
            category=violation,
            action="filtered",
            persona_id=persona.id,
            conversation_id=conversation.id,
            metadata={"original_retained": False},
        )
    if conversation.user_turn_count % 6 == 0:
        await update_memory_summary(
            db,
            persona.id,
            conversation.user_id,
            conversation.id,
        )
    conversation.last_message_at = datetime.utcnow()
    await db.commit()
    return assistant_message, bool(violation)


def is_crisis_message(content: str) -> bool:
    return detect_input_safety(content) == "crisis"
