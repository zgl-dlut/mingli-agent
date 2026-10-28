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
from app.models.report import Report
from app.models.subscription import Subscription
from app.models.user import User


@pytest_asyncio.fixture
async def report_client(monkeypatch):
    monkeypatch.setattr(settings, "V3_ENABLED", True)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.utcnow()
    async with factory() as db:
        user = User(phone="13700000001", name="接口报告用户", points=0)
        db.add(user)
        await db.flush()
        db.add(
            Person(
                user_id=user.id,
                name="本人",
                gender="female",
                birth_date="1992-08-08",
                birth_time="10:30",
                birth_location="大连",
                birth_lat=38.914,
                birth_lng=121.614,
                bazi_data_json={"四柱": "壬申 戊申 庚申 辛巳", "日主": "庚金"},
                is_self=True,
                relationship_type="self",
            )
        )
        db.add(
            Subscription(
                user_id=user.id,
                plan_code="light",
                status="active",
                source="mock",
                starts_at=now - timedelta(days=1),
                expires_at=now + timedelta(days=30),
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

    scheduled = []
    monkeypatch.setattr(
        "app.api.report.schedule_report_generation",
        lambda report_id: scheduled.append(report_id),
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, factory, scheduled, user_id
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_report_api_is_idempotent_and_enforces_plan(report_client):
    client, factory, scheduled, user_id = report_client
    payload = {
        "report_type": "monthly_brief",
        "primary_person_id": 1,
        "period_key": "2026-11",
    }
    first = await client.post("/api/reports", json=payload)
    second = await client.post("/api/reports", json=payload)
    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["report_id"] == second.json()["report_id"]
    assert scheduled == [first.json()["report_id"]]

    annual = await client.post(
        "/api/reports",
        json={
            "report_type": "annual_brief",
            "primary_person_id": 1,
            "period_key": "2027",
        },
    )
    assert annual.status_code == 403
    assert annual.json()["required_plan"] == "full"

    async with factory() as db:
        count = (await db.execute(select(func.count(Report.id)))).scalar_one()
        assert count == 1
        db.add(
            Subscription(
                user_id=user_id,
                plan_code="full",
                status="active",
                source="mock",
                starts_at=datetime.utcnow() - timedelta(days=1),
                expires_at=datetime.utcnow() + timedelta(days=30),
            )
        )
        await db.commit()

    full_annual = await client.post(
        "/api/reports",
        json={
            "report_type": "annual_brief",
            "primary_person_id": 1,
            "period_key": "2027",
        },
    )
    assert full_annual.status_code == 202
    assert full_annual.json()["report_type"] == "annual_brief"
