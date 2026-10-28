import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.user import DeleteAccountRequest, delete_account
from app.db.base import Base
from app.models.content_unlock import ContentUnlock
from app.models.message import ChatMessage
from app.models.person import Person
from app.models.persona import Persona
from app.models.persona_conversation import PersonaConversation
from app.models.persona_memory import PersonaMemory
from app.models.persona_message import PersonaMessage
from app.models.report import Report
from app.models.safety_event import SafetyEvent
from app.models.session import ChatSession
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.usage_counter import UsageCounter
from app.models.user import User


@pytest.mark.asyncio
async def test_account_deletion_removes_all_v3_private_data_but_keeps_finance():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(phone="wx_temp_account", name="待注销用户", points=80)
        db.add(user)
        await db.flush()
        person = Person(
            user_id=user.id,
            name="本人",
            gender="female",
            birth_date="1990-01-01",
            birth_time="10:30",
            birth_location="大连",
            birth_lat=38.914,
            birth_lng=121.614,
            is_self=True,
            relationship_type="self",
        )
        db.add(person)
        await db.flush()
        session = ChatSession(person_id=person.id, bazi_data_json={}, astro_data_json={}, title="旧会话")
        db.add(session)
        await db.flush()
        message = ChatMessage(session_id=session.id, role="assistant", content="旧内容")
        db.add(message)
        persona = Persona(
            user_id=user.id,
            person_id=person.id,
            name="命局人格",
            avatar_key="jia-wood",
            profile_json={},
        )
        db.add(persona)
        await db.flush()
        conversation = PersonaConversation(persona_id=persona.id, user_id=user.id, title="人格会话")
        db.add(conversation)
        await db.flush()
        db.add_all(
            [
                PersonaMessage(
                    conversation_id=conversation.id,
                    user_id=user.id,
                    role="user",
                    content="隐私消息",
                ),
                PersonaMemory(
                    persona_id=persona.id,
                    user_id=user.id,
                    enabled=True,
                    summary_json={"stage_summary": "隐私摘要"},
                ),
                SafetyEvent(
                    user_id=user.id,
                    persona_id=persona.id,
                    conversation_id=conversation.id,
                    category="crisis",
                    action="role_exited",
                ),
                Report(
                    identity_key=f"base:{user.id}:{person.id}",
                    user_id=user.id,
                    primary_person_id=person.id,
                    report_type="base_report",
                    status="ready",
                    title="基础解读",
                    prompt_version="test",
                ),
                Subscription(user_id=user.id, plan_code="light", status="active"),
                UsageCounter(
                    user_id=user.id,
                    metric="qa_daily",
                    period_key="2026-10-28",
                    scope_id="",
                    count=1,
                ),
                Transaction(
                    user_id=user.id,
                    type="bonus",
                    points=80,
                    description="依法保留的财务流水",
                    biz_type="bonus",
                ),
            ]
        )
        await db.flush()
        db.add(ContentUnlock(user_id=user.id, message_id=message.id, unlock_type="points"))
        await db.commit()

        result = await delete_account(DeleteAccountRequest(), user, db)
        assert result["message"] == "账号已注销"

        for model in (
            Person,
            ChatSession,
            ChatMessage,
            ContentUnlock,
            Report,
            Persona,
            PersonaConversation,
            PersonaMessage,
            PersonaMemory,
            SafetyEvent,
            Subscription,
            UsageCounter,
        ):
            count = (await db.execute(select(func.count(model.id)))).scalar_one()
            assert count == 0, model.__name__
        finance_count = (
            await db.execute(select(func.count(Transaction.id)))
        ).scalar_one()
        assert finance_count == 1
        await db.refresh(user)
        assert user.name == "已注销用户"
        assert user.points == 0
        assert user.phone.startswith("deleted_")
    await engine.dispose()
