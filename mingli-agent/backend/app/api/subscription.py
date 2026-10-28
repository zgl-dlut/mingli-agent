from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.config import settings
from app.core.exceptions import V3APIError
from app.db.session import get_db
from app.models.subscription import Subscription
from app.models.user import User
from app.services.entitlement_service import (
    get_entitlement,
    list_plan_definitions,
)


router = APIRouter(tags=["subscriptions"])


class MockActivateRequest(BaseModel):
    plan_code: Literal["light", "full"]
    billing_cycle: Literal["monthly", "annual"] = "monthly"


@router.get("/api/subscriptions/plans")
async def get_plans():
    return [plan.model_dump(mode="json") for plan in list_plan_definitions()]


@router.get("/api/subscriptions/current")
async def get_current_subscription(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return (await get_entitlement(db, current_user.id)).model_dump(mode="json")


@router.get("/api/entitlements/me")
async def get_my_entitlement(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return (await get_entitlement(db, current_user.id)).model_dump(mode="json")


@router.post("/api/subscriptions/mock-activate")
async def mock_activate(
    request: MockActivateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    if not settings.V3_ENABLED:
        raise V3APIError(403, "feature_disabled", "V3 功能尚未开放")
    if not settings.SUBSCRIPTION_MOCK_ENABLED:
        raise V3APIError(403, "feature_disabled", "模拟订阅仅供内部测试")
    now = datetime.utcnow()
    active = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status == "active",
        )
    )
    for subscription in active.scalars().all():
        subscription.status = "expired"
        subscription.expires_at = min(subscription.expires_at or now, now)

    duration = timedelta(days=365 if request.billing_cycle == "annual" else 30)
    subscription = Subscription(
        user_id=current_user.id,
        plan_code=request.plan_code,
        status="active",
        source="mock",
        billing_cycle=request.billing_cycle,
        starts_at=now,
        expires_at=now + duration,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    entitlement = await get_entitlement(db, current_user.id)
    return {
        "subscription_id": subscription.id,
        "entitlement": entitlement.model_dump(mode="json"),
    }


@router.post("/api/subscriptions/mock-expire")
async def mock_expire(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    if not settings.V3_ENABLED:
        raise V3APIError(403, "feature_disabled", "V3 功能尚未开放")
    if not settings.SUBSCRIPTION_MOCK_ENABLED:
        raise V3APIError(403, "feature_disabled", "模拟订阅仅供内部测试")
    now = datetime.utcnow()
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status == "active",
            Subscription.source == "mock",
        )
    )
    subscriptions = result.scalars().all()
    if not subscriptions:
        raise V3APIError(404, "subscription_not_found", "没有可到期的模拟订阅")
    for subscription in subscriptions:
        subscription.status = "expired"
        subscription.expires_at = now
    await db.commit()
    return (await get_entitlement(db, current_user.id)).model_dump(mode="json")
