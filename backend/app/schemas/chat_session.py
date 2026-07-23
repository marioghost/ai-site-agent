"""Pydantic schemas for chat sessions and messages."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ChatSource
from app.schemas.trace import TimingMetrics


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    role: str
    content: str
    sources: list[ChatSource] = Field(default_factory=list)
    request_id: str | None = None
    trace_id: str | None = None
    used_context: bool = False
    cache_hit: bool = False
    cache_type: str = "none"
    timing: TimingMetrics = Field(default_factory=TimingMetrics)
    diagnostics: dict | None = None
    created_at: datetime | None = None


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    title: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    last_message_at: datetime | None = None
    message_count: int = 0


class ChatSessionDetail(ChatSessionRead):
    messages: list[ChatMessageRead] = Field(default_factory=list)


class ChatSessionListResponse(BaseModel):
    items: list[ChatSessionRead]
    total: int
    page: int
    page_size: int


class ChatSessionCreateRequest(BaseModel):
    close_current_session_id: str | None = None
