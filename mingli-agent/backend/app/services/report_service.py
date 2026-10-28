from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDenied, ResourceNotFound
from app.models.person import Person
from app.models.report import Report
from app.schemas.report_v3_schema import (
    ReportAccess,
    ReportCreateRequest,
    ReportListResponse,
    ReportResponse,
)
from app.services.chart_snapshot_service import get_or_create_chart_snapshot
from app.services.entitlement_service import get_entitlement, require_report_access


REPORT_PROMPT_VERSION = "v3-report-1"
GENERATING_TIMEOUT = timedelta(minutes=15)
REPORT_TITLES = {
    "base_report": "基础解读",
    "monthly_brief": "月度节律简报",
    "annual_brief": "年度趋势报告",
    "relation_report": "关系视角",
    "qa_reading": "问答深度解读",
}


def build_identity_key(
    report_type: str,
    user_id: int,
    primary_person_id: int,
    secondary_person_id: Optional[int] = None,
    period_key: Optional[str] = None,
    source_message_id: Optional[int] = None,
) -> str:
    if report_type == "base_report":
        return f"base:{user_id}:{primary_person_id}"
    if report_type == "monthly_brief":
        return f"month:{user_id}:{primary_person_id}:{period_key}"
    if report_type == "annual_brief":
        return f"year:{user_id}:{primary_person_id}:{period_key}"
    if report_type == "relation_report":
        first, second = sorted((primary_person_id, int(secondary_person_id or 0)))
        return f"relation:{user_id}:{first}:{second}"
    if report_type == "qa_reading":
        return f"qa:{user_id}:{source_message_id}"
    raise ValueError(f"Unsupported report type: {report_type}")


async def get_owned_person(db: AsyncSession, person_id: int, user_id: int) -> Person:
    person = await db.get(Person, person_id)
    if not person:
        raise ResourceNotFound("档案不存在")
    if person.user_id != user_id:
        raise PermissionDenied("无权访问该档案")
    return person


async def create_or_get_report(
    db: AsyncSession,
    user_id: int,
    request: ReportCreateRequest,
) -> Tuple[Report, bool]:
    primary = await get_owned_person(db, request.primary_person_id, user_id)
    secondary = None
    if request.secondary_person_id:
        secondary = await get_owned_person(db, request.secondary_person_id, user_id)
    await require_report_access(db, user_id, request.report_type)

    identity_key = build_identity_key(
        request.report_type,
        user_id,
        request.primary_person_id,
        request.secondary_person_id,
        request.period_key,
    )
    existing = (
        await db.execute(select(Report).where(Report.identity_key == identity_key))
    ).scalar_one_or_none()
    if existing:
        if existing.status == "failed":
            claimed = await db.execute(
                update(Report)
                .where(Report.id == existing.id, Report.status == "failed")
                .values(
                    status="pending",
                    failure_code=None,
                    failure_message=None,
                    updated_at=datetime.utcnow(),
                )
                .execution_options(synchronize_session=False)
            )
            await db.commit()
            await db.refresh(existing)
            return existing, claimed.rowcount == 1
        if (
            existing.status == "generating"
            and existing.updated_at < datetime.utcnow() - GENERATING_TIMEOUT
        ):
            cutoff = datetime.utcnow() - GENERATING_TIMEOUT
            claimed = await db.execute(
                update(Report)
                .where(
                    Report.id == existing.id,
                    Report.status == "generating",
                    Report.updated_at < cutoff,
                )
                .values(
                    status="pending",
                    failure_code="generation_timeout",
                    failure_message="上次生成超时，已允许重试",
                    updated_at=datetime.utcnow(),
                )
                .execution_options(synchronize_session=False)
            )
            await db.commit()
            await db.refresh(existing)
            return existing, claimed.rowcount == 1
        return existing, False

    snapshot = await get_or_create_chart_snapshot(db, primary)
    if secondary is not None:
        await get_or_create_chart_snapshot(db, secondary)
    report = Report(
        identity_key=identity_key,
        user_id=user_id,
        primary_person_id=request.primary_person_id,
        secondary_person_id=request.secondary_person_id,
        report_type=request.report_type,
        period_key=request.period_key,
        status="pending",
        title=REPORT_TITLES[request.report_type],
        preview_json={"subtitle": primary.name},
        chart_snapshot_json=snapshot.model_dump(mode="json"),
        prompt_version=REPORT_PROMPT_VERSION,
    )
    try:
        async with db.begin_nested():
            db.add(report)
            await db.flush()
    except IntegrityError:
        existing = (
            await db.execute(select(Report).where(Report.identity_key == identity_key))
        ).scalar_one()
        return existing, False
    await db.commit()
    return report, True


async def get_owned_report(db: AsyncSession, report_id: int, user_id: int) -> Report:
    report = await db.get(Report, report_id)
    if not report:
        raise ResourceNotFound("报告不存在")
    if report.user_id != user_id:
        raise PermissionDenied("无权访问该报告")
    return report


async def report_to_response(
    db: AsyncSession,
    report: Report,
    include_content: bool = True,
) -> ReportResponse:
    entitlement = await get_entitlement(db, report.user_id)
    allowed = bool(entitlement.report_access.get(report.report_type))
    if report.source_message_id is not None:
        allowed = True
    required_plan = None
    if not allowed:
        required_plan = "full" if report.report_type == "annual_brief" else "light"
    return ReportResponse(
        report_id=report.id,
        report_type=report.report_type,
        status=report.status,
        primary_person_id=report.primary_person_id,
        secondary_person_id=report.secondary_person_id,
        period_key=report.period_key,
        title=report.title,
        preview=report.preview_json,
        content=report.content_json if include_content and allowed else None,
        chart_snapshot=report.chart_snapshot_json if include_content and allowed else None,
        prompt_version=report.prompt_version,
        source_message_id=report.source_message_id,
        generated_at=report.generated_at,
        failure_code=report.failure_code,
        failure_message=report.failure_message,
        access=ReportAccess(allowed=allowed, required_plan=required_plan),
    )


async def list_reports(
    db: AsyncSession,
    user_id: int,
    person_id: Optional[int],
    report_type: Optional[str],
    status: Optional[str],
    page: int,
    page_size: int,
) -> ReportListResponse:
    predicates = [Report.user_id == user_id]
    if person_id:
        predicates.append(Report.primary_person_id == person_id)
    if report_type:
        predicates.append(Report.report_type == report_type)
    if status:
        predicates.append(Report.status == status)
    total = (
        await db.execute(select(func.count(Report.id)).where(*predicates))
    ).scalar_one()
    rows = (
        await db.execute(
            select(Report)
            .where(*predicates)
            .order_by(Report.created_at.desc(), Report.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    items = [await report_to_response(db, row, include_content=False) for row in rows]
    return ReportListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )
