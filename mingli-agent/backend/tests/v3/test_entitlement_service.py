from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.core.exceptions import V3APIError
from app.db.base import Base
from app.models.person import Person
from app.models.subscription import Subscription
from app.models.user import User
from app.services.entitlement_service import (
    consume_usage,
    get_entitlement,
    require_profile_slot,
    require_report_access,
)


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(User(phone="13800000000", name="测试用户", points=120))
        await session.commit()
        yield session
    await engine.dispose()


def _person(user_id: int, index: int = 1) -> Person:
    return Person(
        user_id=user_id,
        name=f"档案{index}",
        gender="female",
        birth_date=f"1992-08-{index:02d}",
        birth_time="10:30",
        birth_location="大连",
        birth_lat=38.914,
        birth_lng=121.614,
        is_self=index == 1,
        relationship_type="self" if index == 1 else "other",
    )


@pytest.mark.asyncio
async def test_free_plan_limits_profiles_and_daily_questions(db):
    db.add(_person(user_id=1))
    await db.commit()

    with pytest.raises(V3APIError) as profile_error:
        await require_profile_slot(db, user_id=1)
    assert profile_error.value.status_code == 403
    assert profile_error.value.payload["metric"] == "profile_count"

    for expected in (1, 2, 3):
        usage = await consume_usage(db, user_id=1, metric="qa_daily")
        assert usage.used == expected
    with pytest.raises(V3APIError) as qa_error:
        await consume_usage(db, user_id=1, metric="qa_daily")
    assert qa_error.value.payload["remaining"] == 0


@pytest.mark.asyncio
async def test_light_plan_limits_profiles_persona_and_annual_report(db):
    now = datetime(2026, 10, 28, 4, 0, 0)
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
    db.add_all([_person(1, 1), _person(1, 2), _person(1, 3)])
    await db.commit()

    entitlement = await get_entitlement(db, 1, now)
    assert entitlement.plan_code == "light"
    assert entitlement.profile.limit == 3
    assert entitlement.qa_daily.limit is None

    with pytest.raises(V3APIError):
        await require_profile_slot(db, 1, now)
    with pytest.raises(V3APIError) as report_error:
        await require_report_access(db, 1, "annual_brief", now)
    assert report_error.value.payload["required_plan"] == "full"

    for _ in range(30):
        await consume_usage(db, 1, "persona_session_monthly", now=now)
    with pytest.raises(V3APIError):
        await consume_usage(db, 1, "persona_session_monthly", now=now)


@pytest.mark.asyncio
async def test_full_plan_is_unlimited_and_expiry_downgrades_without_deletion(db):
    now = datetime(2026, 10, 28, 4, 0, 0)
    subscription = Subscription(
        user_id=1,
        plan_code="full",
        status="active",
        source="mock",
        starts_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=30),
    )
    db.add(subscription)
    db.add_all([_person(1, 1), _person(1, 2), _person(1, 3), _person(1, 4)])
    await db.commit()

    entitlement = await get_entitlement(db, 1, now)
    assert entitlement.profile.limit is None
    assert entitlement.persona_session_monthly.limit is None
    await require_profile_slot(db, 1, now)
    await require_report_access(db, 1, "annual_brief", now)
    for _ in range(35):
        await consume_usage(db, 1, "persona_session_monthly", now=now)

    subscription.expires_at = now - timedelta(seconds=1)
    await db.commit()
    downgraded = await get_entitlement(db, 1, now)
    assert downgraded.plan_code == "free"
    assert downgraded.profile.used == 4


@pytest.mark.asyncio
async def test_recharge_api_is_gone_when_flag_disabled(monkeypatch):
    from app.api.payment import CreateWechatOrderRequest, create_wechat_order

    monkeypatch.setattr(settings, "POINTS_RECHARGE_ENABLED", False)
    with pytest.raises(V3APIError) as exc_info:
        await create_wechat_order(
            request=None,
            body=CreateWechatOrderRequest(points=100),
            db=None,
            current_user=User(id=1, phone="13800000000", name="测试用户"),
        )

    assert exc_info.value.status_code == 410
    assert exc_info.value.payload["code"] == "points_recharge_disabled"
