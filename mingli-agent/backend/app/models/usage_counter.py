from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UsageCounter(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "metric",
            "period_key",
            "scope_id",
            name="uq_usage_counter_identity",
        ),
    )

    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    period_key: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
