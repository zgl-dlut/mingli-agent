from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.report_v3_schema import (
    LegacyImportResponse,
    ReportCreateRequest,
    ReportListResponse,
    ReportResponse,
    ReportStatus,
    ReportType,
)
from app.services.entitlement_service import require_report_access
from app.services.legacy_report_adapter import import_legacy_reports
from app.services.report_generation_service import schedule_report_generation
from app.services.report_service import (
    create_or_get_report,
    get_owned_report,
    list_reports,
    report_to_response,
)
from app.services.feature_flag_service import require_v3_enabled


router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
    dependencies=[Depends(require_v3_enabled)],
)


@router.get("", response_model=ReportListResponse)
async def get_reports(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    person_id: Optional[int] = None,
    report_type: Optional[ReportType] = None,
    status: Optional[ReportStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return await list_reports(
        db,
        current_user.id,
        person_id,
        report_type,
        status,
        page,
        page_size,
    )


@router.post("", response_model=ReportResponse)
async def create_report(
    request: ReportCreateRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    report, should_generate = await create_or_get_report(db, current_user.id, request)
    if should_generate:
        schedule_report_generation(report.id)
        response.status_code = 202
    else:
        response.status_code = 200
    return await report_to_response(db, report)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    report = await get_owned_report(db, report_id, current_user.id)
    if report.source_message_id is None:
        await require_report_access(db, current_user.id, report.report_type)
    return await report_to_response(db, report)


@router.get("/{report_id}/status", response_model=ReportResponse)
async def get_report_status(
    report_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    report = await get_owned_report(db, report_id, current_user.id)
    return await report_to_response(db, report, include_content=False)


@router.post("/import-legacy", response_model=LegacyImportResponse)
async def import_legacy(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await import_legacy_reports(db, current_user.id)
