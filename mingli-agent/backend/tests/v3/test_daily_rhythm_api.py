import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import daily as daily_api
from app.api.auth import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.person import Person
from app.models.user import User
from app.config import settings


@pytest_asyncio.fixture
async def rhythm_client(monkeypatch):
    monkeypatch.setattr(settings, "V3_ENABLED", True)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(phone="13400000001", name="节律用户", points=0)
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

    async def fake_daily_fortune(**kwargs):
        return {
            "date": "2026-10-28",
            "advice": {
                "action": "今天宜先完成最重要的一件事。",
                "basis": "今天整体节奏偏顺，适合主动一点。",
                "chart_ref": "庚金逢忌神日",
            },
            "source": {
                "liuri_ganzhi": "壬申",
                "liuyue_ganzhi": "戊戌",
                "dayun_ganzhi": "癸卯",
                "shishen_tian": "食神",
                "shishen_di": "比肩",
                "day_master": "庚金",
            },
            "grade": "good",
            "yi": ["沟通", "推进"],
            "ji": ["拖延"],
            "pressure_level": 35,
        }

    monkeypatch.setattr(daily_api, "generate_daily_fortune", fake_daily_fortune)
    daily_api._CACHE.clear()

    async def override_db():
        async with factory() as db:
            yield db

    async def override_user():
        async with factory() as db:
            return await db.get(User, user_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()
    daily_api._CACHE.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_rhythm_contract_hides_legacy_grade_and_labels(rhythm_client):
    response = await rhythm_client.get(
        "/api/daily/rhythm",
        params={"person_id": 1, "date": "2026-10-28"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["energy_state"] == "smooth"
    assert body["suitable"] == ["沟通", "推进"]
    assert body["notice"] == ["拖延"]
    assert body["action"] == "今天先稳住节奏，完成计划内最重要的一件事。"
    assert body["chart_ref"] == "基于当日节奏与命盘关系"
    assert not any(term in str(body) for term in ("吉", "凶", "宜", "忌", "改运", "化解"))
    assert "grade" not in body
    assert "yi" not in body
    assert "ji" not in body
