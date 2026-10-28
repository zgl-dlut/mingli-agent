import asyncio
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.auth import get_current_user
from app.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.person import Person
from app.models.message import ChatMessage
from app.models.persona_memory import PersonaMemory
from app.models.persona_message import PersonaMessage
from app.models.persona_conversation import PersonaConversation
from app.models.safety_event import SafetyEvent
from app.models.usage_counter import UsageCounter
from app.models.user import User


@pytest_asyncio.fixture
async def persona_client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "V3_ENABLED", True)
    monkeypatch.setattr(settings, "PERSONA_ENABLED", True)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'persona_api.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(phone="13500000001", name="人格接口用户", points=0)
        db.add(user)
        await db.flush()
        db.add(
            Person(
                user_id=user.id,
                name="本人",
                gender="female",
                birth_date="1990-01-01",
                birth_time="10:30",
                birth_location="大连",
                birth_lat=38.914,
                birth_lng=121.614,
                bazi_data_json={"四柱": "壬申 戊申 庚申 辛巳", "日主": "庚金"},
                is_self=True,
                relationship_type="self",
            )
        )
        await db.commit()
        user_id = user.id

    async def override_db():
        async with factory() as db:
            yield db

    async def override_user():
        async with factory() as db:
            return await db.get(User, user_id)

    async def forbidden_llm(*args, **kwargs):
        raise AssertionError("crisis input must not call LLM")
        yield ""

    monkeypatch.setattr(
        "app.services.persona_chat_service.generate_ai_response",
        forbidden_llm,
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_crisis_sse_skips_llm_and_does_not_consume_another_session(persona_client):
    client, factory = persona_client
    created = await client.post("/api/personas", json={"person_id": 1})
    assert created.status_code == 201
    persona_id = created.json()["persona_id"]

    conversation = await client.post(
        f"/api/personas/{persona_id}/conversations",
        json={},
    )
    assert conversation.status_code == 200
    conversation_id = conversation.json()["conversation_id"]

    crisis = await client.post(
        f"/api/persona-conversations/{conversation_id}/messages",
        json={"content": "我不想活了"},
    )
    assert crisis.status_code == 200
    assert "event: meta" in crisis.text
    assert '"safety_category": "crisis"' in crisis.text
    assert "退出命局人格" in crisis.text
    assert '"user_turn_count": 0' in crisis.text

    async with factory() as db:
        usage = (
            await db.execute(select(UsageCounter))
        ).scalar_one()
        assert usage.metric == "persona_session_monthly"
        assert usage.count == 1
        event_count = (
            await db.execute(select(func.count(SafetyEvent.id)))
        ).scalar_one()
        assert event_count == 1


@pytest.mark.asyncio
async def test_normal_messages_stay_in_persona_domain_and_refresh_memory_every_six_turns(
    persona_client,
    monkeypatch,
):
    client, factory = persona_client

    async def fake_llm(*args, **kwargs):
        yield "我会先和你一起把眼前的事实理清。"

    monkeypatch.setattr(
        "app.services.persona_chat_service.generate_ai_response",
        fake_llm,
    )
    persona_id = (
        await client.post("/api/personas", json={"person_id": 1})
    ).json()["persona_id"]
    conversation_id = (
        await client.post(f"/api/personas/{persona_id}/conversations", json={})
    ).json()["conversation_id"]

    for turn in range(1, 7):
        response = await client.post(
            f"/api/persona-conversations/{conversation_id}/messages",
            json={"content": f"这是第{turn}轮，我正在准备转岗"},
        )
        assert response.status_code == 200
        assert "event: done" in response.text

    async with factory() as db:
        persona_message_count = (
            await db.execute(select(func.count(PersonaMessage.id)))
        ).scalar_one()
        legacy_message_count = (
            await db.execute(select(func.count(ChatMessage.id)))
        ).scalar_one()
        memory = (
            await db.execute(select(PersonaMemory))
        ).scalar_one()
        assert persona_message_count == 12
        assert legacy_message_count == 0
        assert "准备转岗" in memory.summary_json["stage_summary"]


@pytest.mark.asyncio
async def test_concurrent_twentieth_turn_only_accepts_one_message(persona_client, monkeypatch):
    client, factory = persona_client

    async def fake_llm(*args, **kwargs):
        yield "收到。"

    monkeypatch.setattr(
        "app.services.persona_chat_service.generate_ai_response",
        fake_llm,
    )
    persona_id = (
        await client.post("/api/personas", json={"person_id": 1})
    ).json()["persona_id"]
    conversation_id = (
        await client.post(f"/api/personas/{persona_id}/conversations", json={})
    ).json()["conversation_id"]
    async with factory() as db:
        conversation = await db.get(PersonaConversation, conversation_id)
        conversation.user_turn_count = 19
        await db.commit()

    responses = await asyncio.gather(
        client.post(
            f"/api/persona-conversations/{conversation_id}/messages",
            json={"content": "并发消息 A"},
        ),
        client.post(
            f"/api/persona-conversations/{conversation_id}/messages",
            json={"content": "并发消息 B"},
        ),
    )
    assert sorted(response.status_code for response in responses) == [200, 409]
    async with factory() as db:
        conversation = await db.get(PersonaConversation, conversation_id)
        assert conversation.user_turn_count == 20
        message_count = (
            await db.execute(
                select(func.count(PersonaMessage.id)).where(
                    PersonaMessage.conversation_id == conversation_id
                )
            )
        ).scalar_one()
        assert message_count == 2


@pytest.mark.asyncio
async def test_reopened_two_hour_conversation_returns_rest_reminder(persona_client):
    client, factory = persona_client
    persona_id = (
        await client.post("/api/personas", json={"person_id": 1})
    ).json()["persona_id"]
    conversation_id = (
        await client.post(f"/api/personas/{persona_id}/conversations", json={})
    ).json()["conversation_id"]
    async with factory() as db:
        conversation = await db.get(PersonaConversation, conversation_id)
        conversation.started_at = datetime.utcnow() - timedelta(hours=2, minutes=1)
        await db.commit()

    response = await client.get(
        f"/api/persona-conversations/{conversation_id}/messages"
    )
    assert response.status_code == 200
    assert response.json()["conversation"]["rest_reminder_required"] is True
