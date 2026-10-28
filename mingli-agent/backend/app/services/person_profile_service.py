from datetime import datetime
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person import Person


RELATIONSHIP_TYPES = {
    "self",
    "partner",
    "spouse",
    "child",
    "parent",
    "friend",
    "colleague",
    "other",
}


async def ensure_self_profile_available(
    db: AsyncSession,
    user_id: int,
    exclude_person_id: Optional[int] = None,
) -> None:
    query = select(Person.id).where(
        Person.user_id == user_id,
        Person.is_self.is_(True),
    )
    if exclude_person_id is not None:
        query = query.where(Person.id != exclude_person_id)
    result = await db.execute(query.limit(1))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "self_profile_exists",
                "message": "每个账号只能有一份本人档案",
            },
        )


async def resolve_profile_relationship(
    db: AsyncSession,
    user_id: int,
    requested_is_self: Optional[bool],
    relationship_type: Optional[str],
    consent_confirmed: Optional[bool],
    exclude_person_id: Optional[int] = None,
) -> Tuple[bool, str, Optional[datetime]]:
    if requested_is_self is None:
        any_person = await db.execute(
            select(Person.id).where(Person.user_id == user_id).limit(1)
        )
        is_self = any_person.scalar_one_or_none() is None
    else:
        is_self = requested_is_self

    if is_self:
        await ensure_self_profile_available(db, user_id, exclude_person_id)
        return True, "self", None

    relation = relationship_type or "other"
    if relation not in RELATIONSHIP_TYPES or relation == "self":
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_relationship_type",
                "message": "关系类型无效",
            },
        )
    if requested_is_self is False and consent_confirmed is not True:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "consent_required",
                "message": "请确认已获得该生辰信息的使用授权",
            },
        )
    confirmed_at = datetime.utcnow() if consent_confirmed else None
    return False, relation, confirmed_at
