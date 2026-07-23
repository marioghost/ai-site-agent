"""Chat session lifecycle: create, close, clear, message persistence."""
from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.chat_session_repository import ChatSessionRepository
from app.utils.time_utils import utcnow

SESSION_TITLE_MAX = 60


def new_session_id() -> str:
    return str(uuid.uuid4())


def session_title_from_message(message: str) -> str:
    text = " ".join((message or "").split())
    if len(text) <= SESSION_TITLE_MAX:
        return text or "New chat"
    return text[: SESSION_TITLE_MAX - 1].rstrip() + "…"


class ChatSessionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.sessions = ChatSessionRepository(db)
        self.messages = ChatMessageRepository(db)

    def resolve_session(
        self,
        session_id: str | None,
        *,
        user_ip: str | None = None,
        user_agent: str | None = None,
        referrer: str | None = None,
    ) -> tuple[ChatSession, bool]:
        """Return (session, created). Reopen cleared sessions on new activity."""
        if session_id:
            existing = self.sessions.get_by_session_id(session_id)
            if existing is not None:
                if existing.status == "closed":
                    raise ValueError("session_closed")
                if existing.status == "cleared":
                    existing.status = "active"
                    self.sessions.save(existing)
                return existing, False
            return self.sessions.create(
                session_id=session_id,
                user_ip=user_ip,
                user_agent=user_agent,
                referrer=referrer,
            ), True

        row = self.sessions.create(
            session_id=new_session_id(),
            user_ip=user_ip,
            user_agent=user_agent,
            referrer=referrer,
        )
        return row, True

    def create_session(
        self,
        *,
        close_current_session_id: str | None = None,
        user_ip: str | None = None,
        user_agent: str | None = None,
        referrer: str | None = None,
    ) -> ChatSession:
        if close_current_session_id:
            self.close_session(close_current_session_id)
        return self.sessions.create(
            session_id=new_session_id(),
            user_ip=user_ip,
            user_agent=user_agent,
            referrer=referrer,
        )

    def close_session(self, session_id: str) -> ChatSession | None:
        row = self.sessions.get_by_session_id(session_id)
        if row is None:
            return None
        row.status = "closed"
        row.closed_at = utcnow()
        return self.sessions.save(row)

    def clear_session(self, session_id: str) -> ChatSession | None:
        row = self.sessions.get_by_session_id(session_id)
        if row is None:
            return None
        self.messages.delete_for_session(session_id)
        row.status = "cleared"
        row.message_count = 0
        row.last_message_at = None
        return self.sessions.save(row)

    def add_user_message(self, session: ChatSession, content: str) -> None:
        if not session.title:
            session.title = session_title_from_message(content)
        self.messages.create(session_id=session.session_id, role="user", content=content)
        session.message_count = (session.message_count or 0) + 1
        session.last_message_at = utcnow()
        session.status = "active"
        self.sessions.save(session)

    def add_assistant_message(
        self,
        session: ChatSession,
        *,
        content: str,
        request_id: str,
        sources_json: str,
        used_context: bool,
        cache_hit: bool,
        cache_type: str,
        timing_json: str,
        trace_id: str | None = None,
        diagnostics_json: str = "{}",
    ) -> None:
        self.messages.create(
            session_id=session.session_id,
            role="assistant",
            content=content,
            request_id=request_id,
            trace_id=trace_id,
            sources_json=sources_json,
            used_context=used_context,
            cache_hit=cache_hit,
            cache_type=cache_type,
            timing_json=timing_json,
            diagnostics_json=diagnostics_json,
        )
        session.message_count = (session.message_count or 0) + 1
        session.last_message_at = utcnow()
        self.sessions.save(session)

    def get_session_payload(self, session_id: str) -> ChatSession | None:
        return self.sessions.get_with_messages(session_id)

    @staticmethod
    def timing_to_json(timing: dict) -> str:
        return json.dumps(timing, ensure_ascii=False)
