from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SafetyEvent(Base):
    __tablename__ = "safety_events"
    __table_args__ = (
        Index("ix_safety_events_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[int] = mapped_column(nullable=False)
    persona_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
