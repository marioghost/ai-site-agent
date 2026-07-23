"""ChatLog ORM model. Stores chat interactions for the Logs page."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChatLog(Base):
    __tablename__ = "chat_logs"

    __table_args__ = (
        Index("ix_chat_logs_cache_hit", "cache_hit"),
        Index("ix_chat_logs_used_context", "used_context"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_message: Mapped[str] = mapped_column(Text)
    assistant_answer: Mapped[str] = mapped_column(Text)
    used_context: Mapped[bool] = mapped_column(Boolean, default=False)
    sources_json: Mapped[str] = mapped_column(Text, default="[]")

    # Cache + timing instrumentation.
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_type: Mapped[str] = mapped_column(String(32), default="none")
    retrieval_ms: Mapped[int] = mapped_column(Integer, default=0)
    generation_ms: Mapped[int] = mapped_column(Integer, default=0)
    polish_ms: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
