from datetime import datetime

from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Persona(Base):
    __tablename__ = "personas"
    __table_args__ = (
        UniqueConstraint("person_id", name="uq_personas_person_id"),
    )

    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    person_id: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_key: Mapped[str] = mapped_column(String(40), nullable=False)
    profile_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v3-persona-1")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
