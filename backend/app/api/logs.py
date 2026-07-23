"""Chat logs API."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_authenticated
from app.core.database import get_db
from app.repositories.chat_log_repository import ChatLogRepository
from app.schemas.chat import ChatLogListResponse, ChatLogRead
from app.schemas.common import ChatSource

router = APIRouter(tags=["logs"])


@router.get("/api/chat/logs", response_model=ChatLogListResponse)
def chat_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    session_id: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> ChatLogListResponse:
    repo = ChatLogRepository(db)
    items, total = repo.list(page=page, page_size=page_size, session_id=session_id)
    logs: list[ChatLogRead] = []
    for item in items:
        raw_sources = json.loads(item.sources_json or "[]")
        logs.append(
            ChatLogRead(
                id=item.id,
                session_id=item.session_id,
                request_id=item.request_id,
                user_message=item.user_message,
                assistant_answer=item.assistant_answer,
                used_context=item.used_context,
                sources=[ChatSource(**s) for s in raw_sources],
                cache_hit=item.cache_hit,
                cache_type=item.cache_type,
                retrieval_ms=item.retrieval_ms,
                generation_ms=item.generation_ms,
                polish_ms=item.polish_ms,
                created_at=item.created_at,
            )
        )
    return ChatLogListResponse(items=logs, total=total, page=page, page_size=page_size)
