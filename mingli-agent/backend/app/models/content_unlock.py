"""深度解读解锁记录

记录「大纲消息 → 用户付费解锁正文」的解锁状态，服务端持久化。
存在此记录才允许返回/生成详细正文，避免刷新或换端绕过付费。
"""
from datetime import datetime

from sqlalchemy import Integer, UniqueConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContentUnlock(Base):
    __tablename__ = "content_unlocks"
    __table_args__ = (
        UniqueConstraint("user_id", "message_id", name="uq_content_unlock_user_message"),
    )

    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    message_id: Mapped[int] = mapped_column(nullable=False, index=True)
    # 解锁方式与消耗，便于对账（points_cost 为解锁时扣减的积分）
    unlock_type: Mapped[str] = mapped_column(String(20), nullable=False, default="points")
    points_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unlocked_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
