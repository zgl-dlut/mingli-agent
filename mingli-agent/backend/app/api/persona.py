from __future__ import annotations

import asyncio
import json
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.persona import Persona
from app.models.persona_conversation import PersonaConversation
from app.models.persona_memory import PersonaMemory
from app.models.persona_message import PersonaMessage
from app.models.user import User
from app.schemas.persona_schema import (
    ConversationCreateRequest,
    ConversationResponse,
    MemorySettingsRequest,
    PersonaCreateRequest,
    PersonaMemoryResponse,
    PersonaMessageListResponse,
    PersonaMessageRequest,
    PersonaMessageResponse,
    PersonaResponse,
)
from app.services.persona_chat_service import (
    PERSONA_TURN_LIMIT,
    create_conversation,
    generate_and_save_reply,
    get_owned_conversation,
    get_owned_persona,
    handle_crisis_message,
    is_crisis_message,
    prepare_normal_message,
    require_persona_enabled,
    rest_reminder_required,
)
from app.services.persona_memory_service import (
    EMPTY_MEMORY,
    clear_memory,
    get_or_create_memory,
)
from app.services.persona_profile_service import create_or_get_persona


router = APIRouter(tags=["persona"])


def _persona_response(persona: Persona) -> PersonaResponse:
    return PersonaResponse(
        persona_id=persona.id,
        person_id=persona.person_id,
        name=persona.name,
        avatar_key=persona.avatar_key,
        profile=persona.profile_json,
        prompt_version=persona.prompt_version,
        created_at=persona.created_at,
    )


def _conversation_response(conversation: PersonaConversation) -> ConversationResponse:
    return ConversationResponse(
        conversation_id=conversation.id,
        persona_id=conversation.persona_id,
        title=conversation.title,
        user_turn_count=conversation.user_turn_count,
        remaining_turns=max(PERSONA_TURN_LIMIT - conversation.user_turn_count, 0),
        started_at=conversation.started_at,
        last_message_at=conversation.last_message_at,
        closed_at=conversation.closed_at,
        rest_reminder_required=rest_reminder_required(conversation),
    )


def _message_response(message: PersonaMessage) -> PersonaMessageResponse:
    return PersonaMessageResponse(
        message_id=message.id,
        role=message.role,
        content=message.content,
        safety_category=message.safety_category,
        created_at=message.created_at,
    )


def _memory_response(memory: PersonaMemory | None) -> PersonaMemoryResponse:
    data = dict(EMPTY_MEMORY)
    if memory:
        data.update(memory.summary_json or {})
    return PersonaMemoryResponse(
        enabled=memory.enabled if memory else True,
        updated_at=memory.updated_at if memory else None,
        **data,
    )


@router.post("/api/personas", response_model=PersonaResponse)
async def create_persona(
    request: PersonaCreateRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    persona, created = await create_or_get_persona(
        db,
        current_user.id,
        request.person_id,
        request.name,
    )
    response.status_code = 201 if created else 200
    return _persona_response(persona)


@router.get("/api/personas", response_model=list[PersonaResponse])
async def list_personas(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await require_persona_enabled()
    personas = (
        await db.execute(
            select(Persona)
            .where(Persona.user_id == current_user.id)
            .order_by(Persona.updated_at.desc())
        )
    ).scalars().all()
    return [_persona_response(persona) for persona in personas]


@router.get("/api/personas/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    persona_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await require_persona_enabled()
    return _persona_response(await get_owned_persona(db, persona_id, current_user.id))


@router.post("/api/personas/{persona_id}/conversations", response_model=ConversationResponse)
async def start_conversation(
    persona_id: int,
    request: ConversationCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await require_persona_enabled()
    persona = await get_owned_persona(db, persona_id, current_user.id)
    return _conversation_response(await create_conversation(db, persona, request.title))


@router.get("/api/personas/{persona_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    persona_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await require_persona_enabled()
    await get_owned_persona(db, persona_id, current_user.id)
    conversations = (
        await db.execute(
            select(PersonaConversation)
            .where(
                PersonaConversation.persona_id == persona_id,
                PersonaConversation.user_id == current_user.id,
            )
            .order_by(PersonaConversation.last_message_at.desc())
        )
    ).scalars().all()
    return [_conversation_response(item) for item in conversations]


@router.get(
    "/api/persona-conversations/{conversation_id}/messages",
    response_model=PersonaMessageListResponse,
)
async def list_messages(
    conversation_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await require_persona_enabled()
    conversation = await get_owned_conversation(db, conversation_id, current_user.id)
    messages = (
        await db.execute(
            select(PersonaMessage)
            .where(PersonaMessage.conversation_id == conversation_id)
            .order_by(PersonaMessage.created_at, PersonaMessage.id)
        )
    ).scalars().all()
    return PersonaMessageListResponse(
        items=[_message_response(message) for message in messages],
        conversation=_conversation_response(conversation),
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/api/persona-conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: int,
    request: PersonaMessageRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await require_persona_enabled()
    conversation = await get_owned_conversation(db, conversation_id, current_user.id)
    content = request.content.strip()

    if is_crisis_message(content):
        user_message, assistant_message = await handle_crisis_message(db, conversation, content)

        async def crisis_stream() -> AsyncGenerator[str, None]:
            yield _sse(
                "meta",
                {
                    "message_id": user_message.id,
                    "rest_reminder_required": rest_reminder_required(conversation),
                    "safety_category": "crisis",
                },
            )
            yield _sse(
                "done",
                {
                    "text": assistant_message.content,
                    "user_turn_count": conversation.user_turn_count,
                    "remaining_turns": max(PERSONA_TURN_LIMIT - conversation.user_turn_count, 0),
                },
            )

        return StreamingResponse(crisis_stream(), media_type="text/event-stream")

    persona, person, user_message, memory, recent, rest_required = await prepare_normal_message(
        db,
        conversation,
        content,
    )

    async def response_stream() -> AsyncGenerator[str, None]:
        yield _sse(
            "meta",
            {
                "message_id": user_message.id,
                "rest_reminder_required": rest_required,
            },
        )
        assistant_message, _ = await generate_and_save_reply(
            db,
            conversation,
            persona,
            person,
            memory,
            recent,
        )
        for index in range(0, len(assistant_message.content), 12):
            yield _sse("delta", {"text": assistant_message.content[index:index + 12]})
            await asyncio.sleep(0.01)
        yield _sse(
            "done",
            {
                "user_turn_count": conversation.user_turn_count,
                "remaining_turns": max(PERSONA_TURN_LIMIT - conversation.user_turn_count, 0),
            },
        )

    return StreamingResponse(
        response_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/personas/{persona_id}/memory", response_model=PersonaMemoryResponse)
async def get_memory(
    persona_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await require_persona_enabled()
    await get_owned_persona(db, persona_id, current_user.id)
    memory = await get_or_create_memory(db, persona_id, current_user.id)
    await db.commit()
    return _memory_response(memory)


@router.patch("/api/personas/{persona_id}/memory-settings", response_model=PersonaMemoryResponse)
async def update_memory_settings(
    persona_id: int,
    request: MemorySettingsRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await require_persona_enabled()
    await get_owned_persona(db, persona_id, current_user.id)
    memory = await get_or_create_memory(db, persona_id, current_user.id)
    memory.enabled = request.enabled
    await db.commit()
    return _memory_response(memory)


@router.delete("/api/personas/{persona_id}/memory", status_code=204)
async def delete_memory(
    persona_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await require_persona_enabled()
    await get_owned_persona(db, persona_id, current_user.id)
    await clear_memory(db, persona_id, current_user.id)
    await db.commit()
