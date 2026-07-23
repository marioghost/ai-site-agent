"""Answer trace ORM — full diagnostic record for each chat request."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnswerTrace(Base):
    __tablename__ = "answer_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    user_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    original_query: Mapped[str] = mapped_column(Text)
    normalized_query: Mapped[str] = mapped_column(Text, default="")
    expanded_queries_json: Mapped[str] = mapped_column(Text, default="[]")
    answer_text: Mapped[str] = mapped_column(Text, default="")
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    selected_chunks_json: Mapped[str] = mapped_column(Text, default="[]")
    trace_steps_json: Mapped[str] = mapped_column(Text, default="[]")

    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_type: Mapped[str] = mapped_column(String(32), default="none")
    used_context: Mapped[bool] = mapped_column(Boolean, default=False)
    retrieval_mode: Mapped[str] = mapped_column(String(16), default="hybrid")
    knowledge_version: Mapped[int] = mapped_column(Integer, default=1)

    total_ms: Mapped[int] = mapped_column(Integer, default=0)
    retrieval_ms: Mapped[int] = mapped_column(Integer, default=0)
    generation_ms: Mapped[int] = mapped_column(Integer, default=0)
    polish_ms: Mapped[int] = mapped_column(Integer, default=0)

    query_intent: Mapped[str] = mapped_column(String(64), default="unknown", index=True)
    matched_topic_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
