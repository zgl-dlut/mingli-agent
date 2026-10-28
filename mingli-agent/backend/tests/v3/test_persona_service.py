from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.core.exceptions import V3APIError
from app.db.base import Base
from app.models.person import Person
from app.models.persona_conversation import PersonaConversation
from app.models.persona_memory import PersonaMemory
from app.models.safety_event import SafetyEvent
from app.models.user import User
from app.services.persona_chat_service import (
    create_conversation,
    handle_crisis_message,
    prepare_normal_message,
    rest_reminder_required,
)
from app.services.persona_memory_service import clear_memory, get_or_create_memory
from app.services.persona_profile_service import create_or_get_persona
from app.services.persona_prompt_service import build_persona_prompt


def _person(user_id: int, person_id: int, birth_date: str, is_self: bool) -> Person:
    return Person(
        id=person_id,
        user_id=user_id,
        name="本人" if is_self else "朋友",
        gender="female",
        birth_date=birth_date,
        birth_time="10:30",
        birth_location="大连",
        birth_lat=38.914,
        birth_lng=121.614,
        bazi_data_json={"四柱": "壬申 戊申 庚申 辛巳", "日主": "庚金"},
        is_self=is_self,
        relationship_type="self" if is_self else "friend",
    )


@pytest_asyncio.fixture
async def db(monkeypatch):
    monkeypatch.setattr(settings, "V3_ENABLED", True)
    monkeypatch.setattr(settings, "PERSONA_ENABLED", True)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(id=1, phone="13600000001", name="人格用户", points=0))
        session.add_all(
            [
                _person(1, 1, "1990-01-01", True),
                _person(1, 2, "1991-01-01", False),
                _person(1, 3, f"{datetime.utcnow().year - 12}-01-01", True),
            ]
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_only_adult_self_profile_can_create_one_persona(db):
    persona, created = await create_or_get_persona(db, 1, 1)
    repeated, repeated_created = await create_or_get_persona(db, 1, 1)
    assert created is True
    assert repeated_created is False
    assert repeated.id == persona.id
    assert persona.avatar_key == "geng-metal"

    with pytest.raises(V3APIError) as other_error:
        await create_or_get_persona(db, 1, 2)
    assert other_error.value.payload["code"] == "self_profile_required"

    with pytest.raises(V3APIError) as minor_error:
        await create_or_get_persona(db, 1, 3)
    assert minor_error.value.payload["code"] == "minor_not_allowed"


@pytest.mark.asyncio
async def test_crisis_exits_role_without_incrementing_turn_or_extra_usage(db):
    persona, _ = await create_or_get_persona(db, 1, 1)
    conversation = await create_conversation(db, persona, None)
    assert conversation.user_turn_count == 0

    _, assistant = await handle_crisis_message(db, conversation, "我不想活了")
    await db.refresh(conversation)
    assert conversation.user_turn_count == 0
    assert "退出命局人格" in assistant.content
    events = (
        await db.execute(select(func.count(SafetyEvent.id)))
    ).scalar_one()
    assert events == 1


@pytest.mark.asyncio
async def test_twenty_turn_limit_and_two_hour_reminder(db):
    persona, _ = await create_or_get_persona(db, 1, 1)
    conversation = PersonaConversation(
        persona_id=persona.id,
        user_id=1,
        title="达到上限",
        user_turn_count=20,
        started_at=datetime.utcnow() - timedelta(hours=2, minutes=1),
        last_message_at=datetime.utcnow(),
    )
    db.add(conversation)
    await db.commit()
    assert rest_reminder_required(conversation) is True
    with pytest.raises(V3APIError) as error:
        await prepare_normal_message(db, conversation, "继续聊")
    assert error.value.payload["code"] == "conversation_turn_limit"


@pytest.mark.asyncio
async def test_memory_can_be_disabled_and_physically_cleared(db):
    persona, _ = await create_or_get_persona(db, 1, 1)
    memory = await get_or_create_memory(db, persona.id, 1)
    memory.summary_json = {
        "preferred_name": "小玲",
        "current_context": ["准备转岗"],
        "preferences": [],
        "important_relationships": [],
        "stage_summary": "正在处理职业选择。",
    }
    memory.enabled = False
    await db.commit()

    prompt = build_persona_prompt({}, persona.profile_json, None if not memory.enabled else memory.summary_json)
    assert "结构化记忆" not in prompt
    await clear_memory(db, persona.id, 1)
    await db.commit()
    remaining = (
        await db.execute(
            select(func.count(PersonaMemory.id)).where(PersonaMemory.persona_id == persona.id)
        )
    ).scalar_one()
    assert remaining == 0
    audit = (
        await db.execute(
            select(SafetyEvent).where(SafetyEvent.action == "memory_cleared")
        )
    ).scalar_one()
    assert audit.metadata_json["content_retained"] is False
