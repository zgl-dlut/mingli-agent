from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, comment="手机号")
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, comment="邮箱")
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="密码哈希（手机登录可为空）")
    name: Mapped[str] = mapped_column(String(100), default="用户", comment="用户名")
    avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="头像URL")
    points: Mapped[int] = mapped_column(Integer, default=200, comment="积分余额（新用户赠送200，够1次首次解读160+1次追问40）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)