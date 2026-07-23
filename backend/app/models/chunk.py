"""Chunk ORM model. Local metadata for chunks stored in Qdrant."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    # Deterministic UUID used as the Qdrant point id for this chunk.
    vector_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Retrieval metadata (used for hybrid search + ranking boosts).
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    heading: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_homepage: Mapped[bool] = mapped_column(Boolean, default=False)
    is_structured_block: Mapped[bool] = mapped_column(Boolean, default=False)
    content_type_hint: Mapped[str] = mapped_column(String(32), default="generic")
    document_type: Mapped[str] = mapped_column(String(32), default="generic_page")
    content_category: Mapped[str] = mapped_column(String(32), default="generic")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    source: Mapped["Source"] = relationship("Source", back_populates="chunks")
