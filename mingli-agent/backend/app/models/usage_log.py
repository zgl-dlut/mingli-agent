from typing import Optional
from datetime import datetime

from sqlalchemy import String, Boolean, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiUsageLog(Base):
    """AI 请求用量记录：每次首次报告/追问的字数与 token 消耗，仅后台查看"""
    __tablename__ = "ai_usage_logs"
    __table_args__ = (
        Index("idx_usage_logs_user_id", "user_id"),
        Index("idx_usage_logs_created_at", "created_at"),
    )

    user_id: Mapped[int] = mapped_column(nullable=False)
    session_id: Mapped[Optional[int]] = mapped_column()
    biz_type: Mapped[str] = mapped_column(String(20), nullable=False)  # first_reading / followup
    input_chars: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_chars: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str] = mapped_column(String(100), default="")
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
