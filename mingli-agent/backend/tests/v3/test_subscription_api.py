import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.auth import get_current_user
from app.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.transaction import Transaction
from app.models.user import User


@pytest_asyncio.fixture
async def api_client(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as setup_db:
        user = User(phone="13900000000", name="接口用户", points=120)
        setup_db.add(user)
        await setup_db.flush()
        setup_db.add(
            Transaction(
                user_id=user.id,
                type="bonus",
                points=120,
                description="历史赠送积分",
                biz_type="register_bonus",
            )
        )
        await setup_db.commit()
        user_id = user.id

    async def override_db():
        async with session_factory() as session:
            yield session

    async def override_user():
        async with session_factory() as session:
            return await session.get(User, user_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    monkeypatch.setattr(settings, "POINTS_RECHARGE_ENABLED", False)
    monkeypatch.setattr(settings, "V3_ENABLED", True)
    monkeypatch.setattr(settings, "SUBSCRIPTION_MOCK_ENABLED", True)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_subscription_activation_expiry_and_points_compatibility(api_client):
    plans = await api_client.get("/api/subscriptions/plans")
    assert plans.status_code == 200
    assert [item["plan_code"] for item in plans.json()] == ["free", "light", "full"]

    current = await api_client.get("/api/entitlements/me")
    assert current.status_code == 200
    assert current.json()["plan_code"] == "free"

    activated = await api_client.post(
        "/api/subscriptions/mock-activate",
        json={"plan_code": "light", "billing_cycle": "monthly"},
    )
    assert activated.status_code == 200
    assert activated.json()["entitlement"]["plan_code"] == "light"
    assert activated.json()["entitlement"]["persona_session_monthly"]["limit"] == 30

    expired = await api_client.post("/api/subscriptions/mock-expire")
    assert expired.status_code == 200
    assert expired.json()["plan_code"] == "free"

    recharge = await api_client.post(
        "/api/payment/create-wechat-order",
        json={"points": 100, "pay_type": "native"},
    )
    assert recharge.status_code == 410
    assert recharge.json()["code"] == "points_recharge_disabled"

    history = await api_client.get("/api/user/transactions")
    assert history.status_code == 200
    assert len(history.json()["items"]) == 1
    assert history.json()["items"][0]["description"] == "历史赠送积分"
