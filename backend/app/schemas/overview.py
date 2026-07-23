"""Overview dashboard schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeBaseStatus(BaseModel):
    total_sources: int = 0
    ready_to_use: int = 0
    waiting: int = 0
    needs_refresh: int = 0
    failed: int = 0
    skipped: int = 0
    readiness_percent: float = 0.0
    ready_pages: int = 0
    ready_files: int = 0
    waiting_pages: int = 0
    waiting_files: int = 0
    chunks_count: int = 0
    vectors_count: int = 0
    last_indexed_at: datetime | None = None


class OverviewResponse(BaseModel):
    knowledge_base: KnowledgeBaseStatus = Field(default_factory=KnowledgeBaseStatus)
