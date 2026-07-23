"""Answer trace API."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_operator
from app.core.database import get_db
from app.repositories.answer_trace_repository import AnswerTraceRepository
from app.schemas.common import ChatSource
from app.schemas.trace import (
    AnswerTraceListResponse,
    AnswerTraceRead,
    TimingMetrics,
    TracePayload,
    TraceStepRead,
    RetrievedChunkRead,
)

router = APIRouter(tags=["traces"])


def _to_read(row) -> AnswerTraceRead:
    steps = json.loads(row.trace_steps_json or "[]")
    chunks = json.loads(row.selected_chunks_json or "[]")
    sources = json.loads(row.sources_json or "[]")
    expanded = json.loads(row.expanded_queries_json or "[]")
    return AnswerTraceRead(
        id=row.id,
        request_id=row.request_id,
        session_id=row.session_id,
        user_ip=row.user_ip,
        user_agent=row.user_agent,
        referrer=row.referrer,
        original_query=row.original_query,
        normalized_query=row.normalized_query,
        expanded_queries=expanded,
        answer_text=row.answer_text,
        sources=[ChatSource(**s) for s in sources],
        trace=TracePayload(
            steps=[TraceStepRead(**s) for s in steps],
            retrieved_chunks=[RetrievedChunkRead(**c) for c in chunks],
        ),
        cache_hit=row.cache_hit,
        cache_type=row.cache_type,
        used_context=row.used_context,
        retrieval_mode=row.retrieval_mode,
        knowledge_version=row.knowledge_version,
        timing=TimingMetrics(
            total_ms=row.total_ms,
            retrieval_ms=row.retrieval_ms,
            generation_ms=row.generation_ms,
            polish_ms=row.polish_ms,
        ),
        created_at=row.created_at,
    )


@router.get("/api/traces", response_model=AnswerTraceListResponse)
def list_traces(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    cache_hit: bool | None = None,
    used_context: bool | None = None,
    min_total_ms: int | None = Query(None, ge=0),
    query: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> AnswerTraceListResponse:
    repo = AnswerTraceRepository(db)
    items, total = repo.list(
        page=page,
        page_size=page_size,
        session_id=session_id,
        date_from=date_from,
        date_to=date_to,
        cache_hit=cache_hit,
        used_context=used_context,
        min_total_ms=min_total_ms,
        query=query,
    )
    return AnswerTraceListResponse(
        items=[_to_read(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/api/traces/{request_id}", response_model=AnswerTraceRead)
def get_trace(
    request_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> AnswerTraceRead:
    row = AnswerTraceRepository(db).get_by_request_id(request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return _to_read(row)
