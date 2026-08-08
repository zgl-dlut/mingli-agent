from typing import Optional
from datetime import datetime

from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"

    user_id: Mapped[int] = mapped_column(nullable=False)
    points: Mapped[int] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    pay_method: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    trade_no: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    paid_at: Mapped[Optional[datetime]] = mapped_column()
