import hashlib
import json
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.exceptions import V3APIError
from app.db.base import Base
from app.models.message import ChatMessage
from app.models.person import Person
from app.models.report import Report
from app.models.session import ChatSession
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.report_v3_schema import ReportContent, ReportCreateRequest
from app.services.legacy_report_adapter import import_legacy_reports
from app.services.report_service import build_identity_key, create_or_get_report


def _content(payload=None):
    return {
        "opening": {"lead": "先看整体节奏。", "verdict": "保持稳定推进。"},
        "subtopics": [
            {
                "title": "行动重点",
                "blocks": [
                    {
                        "type": "keyword",
                        "keyword": "节奏",
                        "narrative": "先完成关键事项，再扩展范围。",
                    }
                ],
            }
        ],
        "summary": {
            "title": "总结：稳定推进",
            "items": [{"keyword": "本期", "text": "聚焦一件重要事项。"}],
        },
        "suggested_questions": ["下一步适合关注什么？"],
        "payload": payload or {},
    }


def _person(user_id=1, person_id=None, name="本人"):
    return Person(
        id=person_id,
        user_id=user_id,
        name=name,
        gender="female",
        birth_date="1992-08-08",
        birth_time="10:30",
        birth_location="大连",
        birth_lat=38.914,
        birth_lng=121.614,
        bazi_data_json={"四柱": "壬申 戊申 庚申 辛巳", "日主": "庚金"},
        is_self=name == "本人",
        relationship_type="self" if name == "本人" else "friend",
    )


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(id=1, phone="13800000001", name="报告用户", points=0))
        session.add_all([_person(person_id=1), _person(person_id=2, name="朋友")])
        await session.commit()
        yield session
    await engine.dispose()


def test_all_five_report_types_share_one_content_contract():
    for report_type in (
        "base_report",
        "monthly_brief",
        "annual_brief",
        "relation_report",
        "qa_reading",
    ):
        parsed = ReportContent.model_validate(_content({"report_type": report_type}))
        assert parsed.payload["report_type"] == report_type


def test_identity_keys_cache_periods_and_order_relations():
    assert build_identity_key("monthly_brief", 1, 8, period_key="2026-11") == "month:1:8:2026-11"
    assert build_identity_key("annual_brief", 1, 8, period_key="2027") == "year:1:8:2027"
    assert build_identity_key("relation_report", 1, 8, 3) == "relation:1:3:8"
    assert build_identity_key("relation_report", 1, 3, 8) == "relation:1:3:8"


@pytest.mark.parametrize(
    ("report_type", "period_key"),
    [
        ("monthly_brief", "2026-00"),
        ("monthly_brief", "2026-13"),
        ("monthly_brief", "abcdefg"),
        ("annual_brief", "abcd"),
        ("annual_brief", "2200"),
    ],
)
def test_report_period_key_rejects_invalid_calendar_values(report_type, period_key):
    with pytest.raises(ValueError):
        ReportCreateRequest(
            report_type=report_type,
            primary_person_id=1,
            period_key=period_key,
        )


@pytest.mark.asyncio
async def test_same_request_is_idempotent_and_light_cannot_create_annual(db):
    now = datetime.utcnow()
    db.add(
        Subscription(
            user_id=1,
            plan_code="light",
            status="active",
            source="mock",
            starts_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=30),
        )
    )
    await db.commit()

    request = ReportCreateRequest(
        report_type="monthly_brief",
        primary_person_id=1,
        period_key="2026-11",
    )
    first, first_created = await create_or_get_report(db, 1, request)
    second, second_created = await create_or_get_report(db, 1, request)
    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    count = (await db.execute(select(func.count(Report.id)))).scalar_one()
    assert count == 1

    with pytest.raises(V3APIError) as error:
        await create_or_get_report(
            db,
            1,
            ReportCreateRequest(
                report_type="annual_brief",
                primary_person_id=1,
                period_key="2027",
            ),
        )
    assert error.value.status_code == 403
    assert error.value.payload["required_plan"] == "full"


@pytest.mark.asyncio
async def test_full_plan_can_create_annual_report(db):
    now = datetime.utcnow()
    db.add(
        Subscription(
            user_id=1,
            plan_code="full",
            status="active",
            source="mock",
            starts_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=30),
        )
    )
    await db.commit()
    report, created = await create_or_get_report(
        db,
        1,
        ReportCreateRequest(
            report_type="annual_brief",
            primary_person_id=1,
            period_key="2027",
        ),
    )
    assert created is True
    assert report.identity_key == "year:1:1:2027"


@pytest.mark.asyncio
async def test_failed_report_retry_is_claimed_once(db):
    now = datetime.utcnow()
    db.add(
        Subscription(
            user_id=1,
            plan_code="light",
            status="active",
            source="mock",
            starts_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=30),
        )
    )
    await db.commit()
    request = ReportCreateRequest(
        report_type="monthly_brief",
        primary_person_id=1,
        period_key="2026-12",
    )
    report, _ = await create_or_get_report(db, 1, request)
    report.status = "failed"
    report.failure_code = "test"
    await db.commit()

    claimed, should_generate = await create_or_get_report(db, 1, request)
    repeated, repeated_should_generate = await create_or_get_report(db, 1, request)
    assert claimed.id == repeated.id
    assert should_generate is True
    assert repeated_should_generate is False
    assert repeated.status == "pending"


@pytest.mark.asyncio
async def test_relation_report_prepares_both_chart_snapshots(db):
    now = datetime.utcnow()
    db.add(
        Subscription(
            user_id=1,
            plan_code="light",
            status="active",
            source="mock",
            starts_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=30),
        )
    )
    await db.commit()
    report, created = await create_or_get_report(
        db,
        1,
        ReportCreateRequest(
            report_type="relation_report",
            primary_person_id=1,
            secondary_person_id=2,
        ),
    )
    secondary = await db.get(Person, 2)
    assert created is True
    assert report.secondary_person_id == 2
    assert secondary.chart_snapshot_json


@pytest.mark.asyncio
async def test_legacy_import_is_idempotent_and_does_not_mutate_message(db):
    session = ChatSession(
        person_id=1,
        bazi_data_json={},
        astro_data_json={},
        title="首次解读",
    )
    db.add(session)
    await db.flush()
    original = json.dumps(_content(), ensure_ascii=False, sort_keys=True)
    message = ChatMessage(session_id=session.id, role="assistant", content=original)
    db.add(message)
    await db.commit()
    original_hash = hashlib.sha256(message.content.encode()).hexdigest()

    first = await import_legacy_reports(db, 1)
    second = await import_legacy_reports(db, 1)
    await db.refresh(message)
    final_hash = hashlib.sha256(message.content.encode()).hexdigest()

    assert first.imported == 1
    assert second.imported == 0
    assert second.existing == 1
    assert original_hash == final_hash
    report = (await db.execute(select(Report))).scalar_one()
    assert report.source_message_id == message.id
    assert report.content_json == json.loads(original)
