from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PersonaConversation(Base):
    __tablename__ = "persona_conversations"
    __table_args__ = (
        Index("ix_persona_conversations_persona_recent", "persona_id", "last_message_at"),
    )

    persona_id: Mapped[int] = mapped_column(nullable=False)
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False, default="新的对话")
    user_turn_count: Mapped[int] = mapped_column(nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_message_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
