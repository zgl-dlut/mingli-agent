import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.person import Person
from app.services.person_profile_service import (
    ensure_self_profile_available,
    resolve_profile_relationship,
)


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def _person(user_id: int, name: str, is_self: bool) -> Person:
    return Person(
        user_id=user_id,
        name=name,
        gender="female",
        birth_date="1992-08-08",
        birth_time="10:30",
        birth_location="大连",
        birth_lat=38.914,
        birth_lng=121.614,
        is_self=is_self,
        relationship_type="self" if is_self else "other",
    )


@pytest.mark.asyncio
async def test_first_legacy_profile_defaults_to_self(db):
    is_self, relation, consent_at = await resolve_profile_relationship(
        db=db,
        user_id=1,
        requested_is_self=None,
        relationship_type=None,
        consent_confirmed=None,
    )
    assert is_self is True
    assert relation == "self"
    assert consent_at is None


@pytest.mark.asyncio
async def test_second_self_profile_is_rejected(db):
    db.add(_person(user_id=1, name="本人", is_self=True))
    await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await ensure_self_profile_available(db, user_id=1)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "self_profile_exists"


@pytest.mark.asyncio
async def test_explicit_other_profile_requires_consent(db):
    db.add(_person(user_id=1, name="本人", is_self=True))
    await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await resolve_profile_relationship(
            db=db,
            user_id=1,
            requested_is_self=False,
            relationship_type="partner",
            consent_confirmed=False,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "consent_required"


@pytest.mark.asyncio
async def test_other_profile_records_relationship_and_consent(db):
    db.add(_person(user_id=1, name="本人", is_self=True))
    await db.commit()

    is_self, relation, consent_at = await resolve_profile_relationship(
        db=db,
        user_id=1,
        requested_is_self=False,
        relationship_type="partner",
        consent_confirmed=True,
    )

    assert is_self is False
    assert relation == "partner"
    assert consent_at is not None
