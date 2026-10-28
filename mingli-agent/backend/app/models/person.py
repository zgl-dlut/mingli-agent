from datetime import datetime

from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Person(Base):
    __tablename__ = "persons"

    user_id: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    birth_date: Mapped[str] = mapped_column(String(20), nullable=False)
    birth_time: Mapped[str] = mapped_column(String(20), nullable=False)
    birth_location: Mapped[str] = mapped_column(String(200))
    birth_lat: Mapped[float] = mapped_column(Float)
    birth_lng: Mapped[float] = mapped_column(Float)
    calendar_type: Mapped[str] = mapped_column(String(10), default='solar')
    province: Mapped[str] = mapped_column(String(50), default='')
    city: Mapped[str] = mapped_column(String(50), default='')
    bazi_data_json: Mapped[dict] = mapped_column(JSON, nullable=True, comment='完整排盘数据（包括命格箴言）')
    is_self: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    relationship_note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    consent_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    chart_snapshot_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    chart_snapshot_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    chart_snapshot_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
