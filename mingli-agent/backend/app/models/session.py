from datetime import datetime

from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    person_id: Mapped[int] = mapped_column(nullable=False)
    bazi_data_json: Mapped[dict] = mapped_column(JSON)
    astro_data_json: Mapped[dict] = mapped_column(JSON)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )
