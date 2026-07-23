"""Repository for chat messages."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage


class ChatMessageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        sources_json: str = "[]",
        trace_id: str | None = None,
        request_id: str | None = None,
        used_context: bool = False,
        cache_hit: bool = False,
        cache_type: str = "none",
        timing_json: str = "{}",
        diagnostics_json: str = "{}",
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sources_json=sources_json,
            trace_id=trace_id,
            request_id=request_id,
            used_context=used_context,
            cache_hit=cache_hit,
            cache_type=cache_type,
            timing_json=timing_json,
            diagnostics_json=diagnostics_json,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def list_for_session(self, session_id: str) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete_for_session(self, session_id: str) -> int:
        result = self.db.execute(
            delete(ChatMessage).where(ChatMessage.session_id == session_id)
        )
        self.db.commit()
        return result.rowcount or 0
