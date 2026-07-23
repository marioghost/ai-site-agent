"""Source ORM model. One record per indexed document (page or file)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Source(Base):
    __tablename__ = "sources"

    __table_args__ = (
        Index("ix_sources_profile_version", "profile_version"),
        Index("ix_sources_document_type", "document_type"),
        Index("ix_sources_page_role", "page_role"),
        Index("ix_sources_indexed_at", "indexed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)  # page/pdf/docx/txt/html
    url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    document_type: Mapped[str] = mapped_column(String(32), default="generic_page")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content_length: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_refresh_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    index_attempts: Mapped[int] = mapped_column(Integer, default=0)
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    navigation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    footer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    header_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    boilerplate_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_content_chars: Mapped[int] = mapped_column(Integer, default=0)
    boilerplate_chars: Mapped[int] = mapped_column(Integer, default=0)
    boilerplate_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    raw_html_available: Mapped[bool] = mapped_column(Boolean, default=False)
    extraction_version: Mapped[str] = mapped_column(String(32), default="")
    chunking_version: Mapped[str] = mapped_column(String(32), default="")
    classification_version: Mapped[str] = mapped_column(String(32), default="")
    needs_reprocess: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_reprocessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Source Intelligence Layer
    page_role: Mapped[str] = mapped_column(String(32), default="generic")
    importance: Mapped[int] = mapped_column(Integer, default=0, index=True)
    canonical: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    content_quality: Mapped[int] = mapped_column(Integer, default=0)
    site_section: Mapped[str] = mapped_column(String(64), default="general")
    topics_json: Mapped[str] = mapped_column(Text, default="[]")
    entity_types_json: Mapped[str] = mapped_column(Text, default="[]")
    should_answer_general: Mapped[bool] = mapped_column(Boolean, default=False)
    should_answer_product: Mapped[bool] = mapped_column(Boolean, default=False)
    should_answer_support: Mapped[bool] = mapped_column(Boolean, default=False)
    should_answer_company: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords_json: Mapped[str] = mapped_column(Text, default="[]")
    intelligence_json: Mapped[str] = mapped_column(Text, default="{}")
    profile_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    profile_version: Mapped[str] = mapped_column(String(32), default="")
    source_language: Mapped[str] = mapped_column(String(8), default="unknown")
    needs_intelligence: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_source_intelligence_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    intelligence_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intelligence_settings_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intelligence_llm_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    intelligence_prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intelligence_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="source", cascade="all, delete-orphan"
    )
