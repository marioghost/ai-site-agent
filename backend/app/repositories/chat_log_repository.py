"""Repository for chat logs."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chat_log import ChatLog


class ChatLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        session_id: str | None,
        user_message: str,
        assistant_answer: str,
        used_context: bool,
        sources_json: str,
        cache_hit: bool = False,
        cache_type: str = "none",
        retrieval_ms: int = 0,
        generation_ms: int = 0,
        polish_ms: int = 0,
        request_id: str | None = None,
    ) -> ChatLog:
        log = ChatLog(
            session_id=session_id,
            request_id=request_id,
            user_message=user_message,
            assistant_answer=assistant_answer,
            used_context=used_context,
            sources_json=sources_json,
            cache_hit=cache_hit,
            cache_type=cache_type,
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
            polish_ms=polish_ms,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list(
        self,
        page: int = 1,
        page_size: int = 50,
        session_id: str | None = None,
    ) -> tuple[list[ChatLog], int]:
        count_stmt = select(func.count()).select_from(ChatLog)
        stmt = select(ChatLog)
        if session_id:
            count_stmt = count_stmt.where(ChatLog.session_id == session_id)
            stmt = stmt.where(ChatLog.session_id == session_id)
        total = self.db.execute(count_stmt).scalar_one()
        stmt = (
            stmt.order_by(ChatLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
