"""LLM semantic profile cache for Source Intelligence."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SourceIntelligenceLlmCache(Base):
    __tablename__ = "source_intelligence_llm_cache"

    __table_args__ = (Index("ix_si_llm_cache_expires_at", "expires_at"),)

    cache_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    profile_version: Mapped[str] = mapped_column(String(32), default="")
    llm_model: Mapped[str] = mapped_column(String(255), default="")
    prompt_hash: Mapped[str] = mapped_column(String(64), default="")
    settings_hash: Mapped[str] = mapped_column(String(64), default="")
    language: Mapped[str] = mapped_column(String(8), default="unknown")
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    semantic_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(16), default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
