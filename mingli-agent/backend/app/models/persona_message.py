from datetime import datetime
from typing import Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PersonaMessage(Base):
    __tablename__ = "persona_messages"
    __table_args__ = (
        Index("ix_persona_messages_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[int] = mapped_column(nullable=False)
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    safety_category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v3-persona-1")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
