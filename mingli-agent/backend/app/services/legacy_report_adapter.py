import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import ChatMessage
from app.models.person import Person
from app.models.report import Report
from app.models.session import ChatSession
from app.schemas.report_v3_schema import LegacyImportResponse, ReportContent
from app.services.chart_snapshot_service import get_or_create_chart_snapshot
from app.services.report_service import REPORT_PROMPT_VERSION, build_identity_key


def _parse_json(content: str) -> Optional[dict[str, Any]]:
    try:
        parsed = json.loads(content)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_legacy_content(raw: str) -> tuple[Optional[dict], Optional[str]]:
    parsed = _parse_json(raw)
    if not parsed:
        return None, None
    if parsed.get("kind") == "outline":
        detail = parsed.get("detail")
        if isinstance(detail, dict):
            return detail, "qa_reading"
        return None, None
    try:
        ReportContent.model_validate(parsed)
    except Exception:
        return None, None
    return parsed, "base_report"


async def import_legacy_reports(db: AsyncSession, user_id: int) -> LegacyImportResponse:
    rows = (
        await db.execute(
            select(ChatMessage, ChatSession, Person)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .join(Person, Person.id == ChatSession.person_id)
            .where(Person.user_id == user_id, ChatMessage.role == "assistant")
            .order_by(ChatSession.id, ChatMessage.created_at, ChatMessage.id)
        )
    ).all()
    first_assistant_by_session: set[int] = set()
    imported = 0
    existing = 0
    scanned = 0
    for message, session, person in rows:
        scanned += 1
        content, detected_type = _extract_legacy_content(message.content)
        if not content or not detected_type:
            continue
        if detected_type == "base_report":
            if session.id in first_assistant_by_session:
                continue
            first_assistant_by_session.add(session.id)
        identity = build_identity_key(
            detected_type,
            user_id,
            person.id,
            source_message_id=message.id,
        )
        found = (
            await db.execute(
                select(Report.id).where(
                    (Report.identity_key == identity)
                    | (Report.source_message_id == message.id)
                )
            )
        ).scalar_one_or_none()
        if found:
            existing += 1
            continue
        snapshot = await get_or_create_chart_snapshot(db, person)
        report = Report(
            identity_key=identity,
            user_id=user_id,
            primary_person_id=person.id,
            report_type=detected_type,
            status="ready",
            title="基础解读" if detected_type == "base_report" else "历史问答深度解读",
            preview_json={"subtitle": person.name, "legacy": True},
            content_json=content,
            chart_snapshot_json=snapshot.model_dump(mode="json"),
            prompt_version=REPORT_PROMPT_VERSION,
            source_message_id=message.id,
            generated_at=message.created_at,
        )
        try:
            async with db.begin_nested():
                db.add(report)
                await db.flush()
            imported += 1
        except IntegrityError:
            existing += 1
    await db.commit()
    return LegacyImportResponse(imported=imported, existing=existing, scanned=scanned)
