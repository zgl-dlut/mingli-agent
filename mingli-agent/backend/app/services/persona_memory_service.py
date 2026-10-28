import re
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona_memory import PersonaMemory
from app.models.persona_message import PersonaMessage
from app.services.safety_service import record_safety_event


EMPTY_MEMORY = {
    "preferred_name": None,
    "current_context": [],
    "preferences": [],
    "important_relationships": [],
    "stage_summary": "",
}


async def get_or_create_memory(
    db: AsyncSession,
    persona_id: int,
    user_id: int,
) -> PersonaMemory:
    memory = (
        await db.execute(
            select(PersonaMemory).where(
                PersonaMemory.persona_id == persona_id,
                PersonaMemory.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if memory:
        return memory
    memory = PersonaMemory(
        persona_id=persona_id,
        user_id=user_id,
        enabled=True,
        summary_json=dict(EMPTY_MEMORY),
    )
    try:
        async with db.begin_nested():
            db.add(memory)
            await db.flush()
        return memory
    except IntegrityError:
        return (
            await db.execute(
                select(PersonaMemory).where(
                    PersonaMemory.persona_id == persona_id,
                    PersonaMemory.user_id == user_id,
                )
            )
        ).scalar_one()


async def update_memory_summary(
    db: AsyncSession,
    persona_id: int,
    user_id: int,
    conversation_id: int,
) -> PersonaMemory:
    memory = await get_or_create_memory(db, persona_id, user_id)
    if not memory.enabled:
        return memory
    messages = (
        await db.execute(
            select(PersonaMessage)
            .where(
                PersonaMessage.conversation_id == conversation_id,
                PersonaMessage.user_id == user_id,
                PersonaMessage.role == "user",
                PersonaMessage.safety_category.is_(None),
            )
            .order_by(PersonaMessage.created_at.desc(), PersonaMessage.id.desc())
            .limit(6)
        )
    ).scalars().all()
    texts = [message.content.strip() for message in reversed(messages) if message.content.strip()]
    existing = dict(memory.summary_json or EMPTY_MEMORY)
    preferred_name = existing.get("preferred_name")
    for text in texts:
        matched = re.search(r"(?:叫我|称呼我)([\u4e00-\u9fa5A-Za-z0-9_]{1,12})", text)
        if matched:
            preferred_name = matched.group(1)
    memory.summary_json = {
        "preferred_name": preferred_name,
        "current_context": [text[:80] for text in texts[-3:]],
        "preferences": existing.get("preferences", []),
        "important_relationships": existing.get("important_relationships", []),
        "stage_summary": "；".join(text[:60] for text in texts[-3:])[:240],
    }
    memory.updated_at = datetime.utcnow()
    await db.flush()
    return memory


async def clear_memory(
    db: AsyncSession,
    persona_id: int,
    user_id: int,
) -> None:
    await db.execute(
        delete(PersonaMemory).where(
            PersonaMemory.persona_id == persona_id,
            PersonaMemory.user_id == user_id,
        )
    )
    await record_safety_event(
        db,
        user_id,
        category="dependency",
        action="memory_cleared",
        persona_id=persona_id,
        metadata={"content_retained": False},
    )
