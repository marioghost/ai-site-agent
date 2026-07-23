"""Pydantic schemas for sources."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    url: str
    title: str | None = None
    document_type: str | None = None
    content_hash: str | None = None
    content_length: int = 0
    status: str
    display_status: str | None = None
    chunk_count: int = 0
    error_message: str | None = None
    indexed_at: datetime | None = None
    last_checked_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SourceDetailRead(SourceRead):
    preview_text: str = ""
    word_count: int = 0
    char_count: int = 0
    content_type_hint: str = "generic"
    semantic_profile: dict = {}
    profile_version: str = ""
    llm_summary: str = ""


class SourceBulkRequest(BaseModel):
    ids: list[int]


class SourceListResponse(BaseModel):
    items: list[SourceRead]
    total: int
    page: int
    page_size: int
