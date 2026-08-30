from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BonusPhone(Base):
    __tablename__ = "bonus_phones"

    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, comment="白名单手机号")
    points: Mapped[int] = mapped_column(default=1000, comment="赠送积分数")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
