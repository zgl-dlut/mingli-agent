from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("identity_key", name="uq_reports_identity_key"),
        UniqueConstraint("source_message_id", name="uq_reports_source_message_id"),
        Index("ix_reports_user_person", "user_id", "primary_person_id"),
        Index("ix_reports_user_type_status", "user_id", "report_type", "status"),
    )

    identity_key: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(nullable=False)
    primary_person_id: Mapped[int] = mapped_column(nullable=False)
    secondary_person_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_key: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    preview_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    content_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    chart_snapshot_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v3-report-1")
    source_message_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
