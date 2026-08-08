from typing import Optional
from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    user_id: Mapped[int] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    points: Mapped[int] = mapped_column(nullable=False)
    order_id: Mapped[Optional[int]] = mapped_column()
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
