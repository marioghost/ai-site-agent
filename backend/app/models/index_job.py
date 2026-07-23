"""IndexJob ORM model. Tracks indexing job state and counters."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IndexJob(Base):
    __tablename__ = "index_jobs"

    __table_args__ = (
        Index("ix_index_jobs_created_at", "created_at"),
        Index("ix_index_jobs_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # idle / running / completed / failed / stopped
    status: Mapped[str] = mapped_column(String(32), default="idle", index=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Legacy aggregate counters (kept for backward compatibility).
    processed_files: Mapped[int] = mapped_column(Integer, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, default=0)

    # Separate page/file counters.
    discovered_pages: Mapped[int] = mapped_column(Integer, default=0)
    indexed_pages: Mapped[int] = mapped_column(Integer, default=0)
    skipped_pages: Mapped[int] = mapped_column(Integer, default=0)
    new_pages: Mapped[int] = mapped_column(Integer, default=0)
    queued_pages: Mapped[int] = mapped_column(Integer, default=0)
    processed_pages: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_pages: Mapped[int] = mapped_column(Integer, default=0)
    skipped_fresh_pages: Mapped[int] = mapped_column(Integer, default=0)
    failed_pages: Mapped[int] = mapped_column(Integer, default=0)
    stale_pages: Mapped[int] = mapped_column(Integer, default=0)
    discovered_files: Mapped[int] = mapped_column(Integer, default=0)
    indexed_files: Mapped[int] = mapped_column(Integer, default=0)
    skipped_files: Mapped[int] = mapped_column(Integer, default=0)
    current_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    current_phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    progress_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    log_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
