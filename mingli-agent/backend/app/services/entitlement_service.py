from datetime import datetime, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import V3APIError
from app.models.person import Person
from app.models.subscription import Subscription
from app.models.usage_counter import UsageCounter
from app.models.user import User
from app.schemas.entitlement_schema import (
    EntitlementSnapshot,
    PlanDefinition,
    UsageAllowance,
    UsageResult,
)


REPORT_TYPES = {
    "base_report",
    "monthly_brief",
    "annual_brief",
    "relation_report",
    "qa_reading",
}

PLAN_CATALOG: Dict[str, Dict[str, Any]] = {
    "free": {
        "name": "免费",
        "monthly_price_yuan": 0,
        "annual_price_yuan": 0,
        "profile_limit": 1,
        "qa_daily_limit": 3,
        "persona_session_monthly_limit": 3,
        "persona_turn_limit": 20,
        "report_access": {
            "base_report": True,
            "monthly_brief": False,
            "annual_brief": False,
            "relation_report": False,
            "qa_reading": False,
        },
        "highlights": ["1 份档案", "基础解读", "每日 3 次解盘问答", "每月 3 次人格会话"],
    },
    "light": {
        "name": "轻享",
        "monthly_price_yuan": 28,
        "annual_price_yuan": 198,
        "profile_limit": 3,
        "qa_daily_limit": None,
        "persona_session_monthly_limit": 30,
        "persona_turn_limit": 20,
        "report_access": {
            "base_report": True,
            "monthly_brief": True,
            "annual_brief": False,
            "relation_report": True,
            "qa_reading": True,
        },
        "highlights": ["最多 3 份档案", "月运与关系视角", "解盘问答不限", "每月 30 次人格会话"],
    },
    "full": {
        "name": "全享",
        "monthly_price_yuan": 58,
        "annual_price_yuan": 398,
        "profile_limit": None,
        "qa_daily_limit": None,
        "persona_session_monthly_limit": None,
        "persona_turn_limit": 20,
        "report_access": {report_type: True for report_type in REPORT_TYPES},
        "highlights": ["档案不限", "全部报告含年报", "解盘问答不限", "人格会话不限"],
    },
}

_PLAN_RANK = {"free": 0, "light": 1, "full": 2}
_SHANGHAI = ZoneInfo("Asia/Shanghai")


def list_plan_definitions() -> list[PlanDefinition]:
    return [
        PlanDefinition(plan_code=plan_code, **definition)
        for plan_code, definition in PLAN_CATALOG.items()
    ]


def _utc_naive(now: Optional[datetime]) -> datetime:
    if now is None:
        return datetime.utcnow()
    if now.tzinfo is None:
        return now
    return now.astimezone(timezone.utc).replace(tzinfo=None)


def _local_now(now: datetime) -> datetime:
    return now.replace(tzinfo=timezone.utc).astimezone(_SHANGHAI)


def _period_key(metric: str, now: datetime) -> str:
    local = _local_now(now)
    if metric == "qa_daily":
        return local.strftime("%Y-%m-%d")
    if metric == "persona_session_monthly":
        return local.strftime("%Y-%m")
    raise ValueError(f"Unsupported usage metric: {metric}")


async def _current_subscription(
    db: AsyncSession,
    user_id: int,
    now: datetime,
) -> Optional[Subscription]:
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.starts_at <= now,
        )
    )
    candidates = [
        subscription
        for subscription in result.scalars().all()
        if subscription.expires_at is None or subscription.expires_at > now
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            _PLAN_RANK.get(item.plan_code, 0),
            item.expires_at or datetime.max,
            item.id or 0,
        ),
    )


async def _usage_count(
    db: AsyncSession,
    user_id: int,
    metric: str,
    period_key: str,
    scope_id: str = "",
) -> int:
    result = await db.execute(
        select(UsageCounter.count).where(
            UsageCounter.user_id == user_id,
            UsageCounter.metric == metric,
            UsageCounter.period_key == period_key,
            UsageCounter.scope_id == scope_id,
        )
    )
    return result.scalar_one_or_none() or 0


def _allowance(limit: Optional[int], used: int) -> UsageAllowance:
    return UsageAllowance(
        limit=limit,
        used=used,
        remaining=None if limit is None else max(limit - used, 0),
    )


async def get_entitlement(
    db: AsyncSession,
    user_id: int,
    now: Optional[datetime] = None,
) -> EntitlementSnapshot:
    current = _utc_naive(now)
    subscription = await _current_subscription(db, user_id, current)
    plan_code = subscription.plan_code if subscription else "free"
    plan = PLAN_CATALOG.get(plan_code, PLAN_CATALOG["free"])

    profile_used = (
        await db.execute(
            select(func.count(Person.id)).where(Person.user_id == user_id)
        )
    ).scalar_one()
    qa_key = _period_key("qa_daily", current)
    persona_key = _period_key("persona_session_monthly", current)
    qa_used = await _usage_count(db, user_id, "qa_daily", qa_key)
    persona_used = await _usage_count(
        db,
        user_id,
        "persona_session_monthly",
        persona_key,
    )

    return EntitlementSnapshot(
        plan_code=plan_code,
        status="active" if subscription else "free",
        expires_at=subscription.expires_at if subscription else None,
        profile=_allowance(plan["profile_limit"], profile_used),
        qa_daily=_allowance(plan["qa_daily_limit"], qa_used),
        persona_session_monthly=_allowance(
            plan["persona_session_monthly_limit"],
            persona_used,
        ),
        persona_turn_limit=plan["persona_turn_limit"],
        report_access=dict(plan["report_access"]),
    )


async def require_profile_slot(
    db: AsyncSession,
    user_id: int,
    now: Optional[datetime] = None,
) -> None:
    await db.execute(
        select(User.id).where(User.id == user_id).with_for_update()
    )
    entitlement = await get_entitlement(db, user_id, now)
    if (
        entitlement.profile.limit is not None
        and entitlement.profile.used >= entitlement.profile.limit
    ):
        required = "light" if entitlement.plan_code == "free" else "full"
        raise V3APIError(
            403,
            "usage_limit_reached",
            "当前档案数量已达上限",
            required_plan=required,
            metric="profile_count",
            remaining=0,
        )


async def _ensure_counter(
    db: AsyncSession,
    user_id: int,
    metric: str,
    period_key: str,
    scope_id: str,
) -> None:
    exists = await db.execute(
        select(UsageCounter.id).where(
            UsageCounter.user_id == user_id,
            UsageCounter.metric == metric,
            UsageCounter.period_key == period_key,
            UsageCounter.scope_id == scope_id,
        )
    )
    if exists.scalar_one_or_none() is not None:
        return

    try:
        async with db.begin_nested():
            db.add(
                UsageCounter(
                    user_id=user_id,
                    metric=metric,
                    period_key=period_key,
                    scope_id=scope_id,
                    count=0,
                )
            )
            await db.flush()
    except IntegrityError:
        pass


async def consume_usage(
    db: AsyncSession,
    user_id: int,
    metric: str,
    scope_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> UsageResult:
    if metric not in {"qa_daily", "persona_session_monthly"}:
        raise ValueError(f"Unsupported usage metric: {metric}")

    current = _utc_naive(now)
    entitlement = await get_entitlement(db, user_id, current)
    allowance = (
        entitlement.qa_daily
        if metric == "qa_daily"
        else entitlement.persona_session_monthly
    )
    period_key = _period_key(metric, current)
    normalized_scope = scope_id or ""
    await _ensure_counter(
        db,
        user_id,
        metric,
        period_key,
        normalized_scope,
    )

    predicates = [
        UsageCounter.user_id == user_id,
        UsageCounter.metric == metric,
        UsageCounter.period_key == period_key,
        UsageCounter.scope_id == normalized_scope,
    ]
    if allowance.limit is not None:
        predicates.append(UsageCounter.count < allowance.limit)

    result = await db.execute(
        update(UsageCounter)
        .where(*predicates)
        .values(count=UsageCounter.count + 1, updated_at=current)
    )
    if result.rowcount != 1:
        required = "light" if entitlement.plan_code == "free" else "full"
        raise V3APIError(
            403,
            "usage_limit_reached",
            "当前用量额度已用完",
            required_plan=required,
            metric=metric,
            remaining=0,
        )

    used = await _usage_count(
        db,
        user_id,
        metric,
        period_key,
        normalized_scope,
    )
    return UsageResult(
        metric=metric,
        period_key=period_key,
        used=used,
        limit=allowance.limit,
        remaining=None if allowance.limit is None else max(allowance.limit - used, 0),
    )


async def require_report_access(
    db: AsyncSession,
    user_id: int,
    report_type: str,
    now: Optional[datetime] = None,
) -> None:
    if report_type not in REPORT_TYPES:
        raise ValueError(f"Unsupported report type: {report_type}")
    entitlement = await get_entitlement(db, user_id, now)
    if entitlement.report_access.get(report_type):
        return
    required = "full" if report_type == "annual_brief" else "light"
    raise V3APIError(
        403,
        "entitlement_required",
        "当前权益不足",
        required_plan=required,
        metric=report_type,
        remaining=0,
    )
