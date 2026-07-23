"""Chat session management API."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import require_operator
from app.core.database import get_db
from app.repositories.chat_session_repository import ChatSessionRepository
from app.schemas.chat_session import (
    ChatMessageRead,
    ChatSessionCreateRequest,
    ChatSessionDetail,
    ChatSessionListResponse,
    ChatSessionRead,
)
from app.schemas.common import ChatSource
from app.schemas.trace import TimingMetrics
from app.services.chat_session_service import ChatSessionService

router = APIRouter(tags=["chat-sessions"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _message_to_read(msg) -> ChatMessageRead:
    try:
        sources = [ChatSource(**s) for s in json.loads(msg.sources_json or "[]")]
    except (json.JSONDecodeError, TypeError):
        sources = []
    try:
        timing_raw = json.loads(msg.timing_json or "{}")
        timing = TimingMetrics(**timing_raw)
    except (json.JSONDecodeError, TypeError):
        timing = TimingMetrics()
    diagnostics: dict | None = None
    try:
        raw_diag = json.loads(getattr(msg, "diagnostics_json", None) or "{}")
        diagnostics = raw_diag if isinstance(raw_diag, dict) and raw_diag else None
    except (json.JSONDecodeError, TypeError):
        diagnostics = None
    return ChatMessageRead(
        id=msg.id,
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        sources=sources,
        request_id=msg.request_id,
        trace_id=msg.trace_id,
        used_context=msg.used_context,
        cache_hit=msg.cache_hit,
        cache_type=msg.cache_type or "none",
        timing=timing,
        diagnostics=diagnostics,
        created_at=msg.created_at,
    )


def _session_to_read(row) -> ChatSessionRead:
    return ChatSessionRead(
        session_id=row.session_id,
        title=row.title or "",
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        closed_at=row.closed_at,
        last_message_at=row.last_message_at,
        message_count=row.message_count or 0,
    )


def _session_to_detail(row) -> ChatSessionDetail:
    return ChatSessionDetail(
        **_session_to_read(row).model_dump(),
        messages=[_message_to_read(m) for m in (row.messages or [])],
    )


@router.get("/api/chat/sessions/current", response_model=ChatSessionDetail)
def get_current_session(
    session_id: str | None = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> ChatSessionDetail:
    if not session_id:
        raise HTTPException(status_code=404, detail="No active session id provided")
    row = ChatSessionService(db).get_session_payload(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if row.status == "closed":
        raise HTTPException(status_code=404, detail="Session is closed")
    return _session_to_detail(row)


@router.post("/api/chat/sessions", response_model=ChatSessionDetail)
def create_session(
    payload: ChatSessionCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> ChatSessionDetail:
    svc = ChatSessionService(db)
    row = svc.create_session(
        close_current_session_id=payload.close_current_session_id,
        user_ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        referrer=request.headers.get("referer"),
    )
    return ChatSessionDetail(**_session_to_read(row).model_dump(), messages=[])


@router.get("/api/chat/sessions/{session_id}", response_model=ChatSessionDetail)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> ChatSessionDetail:
    row = ChatSessionService(db).get_session_payload(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_detail(row)


@router.get("/api/chat/sessions", response_model=ChatSessionListResponse)
def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status: str | None = None,
    query: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> ChatSessionListResponse:
    items, total = ChatSessionRepository(db).list_sessions(
        page=page,
        page_size=page_size,
        status=status,
        query=query,
        date_from=date_from,
        date_to=date_to,
    )
    return ChatSessionListResponse(
        items=[_session_to_read(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/api/chat/sessions/{session_id}/clear", response_model=ChatSessionDetail)
def clear_session(
    session_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> ChatSessionDetail:
    row = ChatSessionService(db).clear_session(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return ChatSessionDetail(**_session_to_read(row).model_dump(), messages=[])


@router.post("/api/chat/sessions/{session_id}/close", response_model=ChatSessionRead)
def close_session(
    session_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> ChatSessionRead:
    row = ChatSessionService(db).close_session(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_read(row)
