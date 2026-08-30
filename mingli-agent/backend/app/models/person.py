from datetime import datetime

from sqlalchemy import String, Float, JSON
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
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
