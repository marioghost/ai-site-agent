"""ORM models for the retrieval cache and the semantic answer cache.

Both caches are invalidated lazily by comparing the stored ``knowledge_version``
against the current one, plus a TTL ``expires_at``.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RetrievalCache(Base):
    """Caches retrieved (and reranked/trimmed) chunks for a normalized query."""

    __tablename__ = "retrieval_cache"

    __table_args__ = (Index("ix_retrieval_cache_expires_at", "expires_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    normalized_query: Mapped[str] = mapped_column(Text)
    knowledge_version: Mapped[int] = mapped_column(Integer, index=True, default=1)
    namespace_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    cache_type: Mapped[str] = mapped_column(String(32), default="retrieval_success")
    selected_chunks_count: Mapped[int] = mapped_column(Integer, default=0)
    context_used: Mapped[bool] = mapped_column(Boolean, default=False)
    retrieved_chunks_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AnswerCache(Base):
    """Metadata for semantically-cached answers.

    The query embedding itself lives in a dedicated Qdrant collection; this row
    is looked up by ``vector_id`` (the Qdrant point id).
    """

    __tablename__ = "answer_cache"

    __table_args__ = (Index("ix_answer_cache_expires_at", "expires_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vector_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    normalized_query: Mapped[str] = mapped_column(Text)
    query_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    used_context: Mapped[bool] = mapped_column(Boolean, default=True)
    knowledge_version: Mapped[int] = mapped_column(Integer, index=True, default=1)
    namespace_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    cache_type: Mapped[str] = mapped_column(String(32), default="answer_success")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
