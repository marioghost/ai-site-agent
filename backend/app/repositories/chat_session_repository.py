"""Repository for chat sessions."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.chat_session import ChatSession
from app.utils.time_utils import utcnow


class ChatSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_session_id(self, session_id: str) -> ChatSession | None:
        return self.db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        ).scalar_one_or_none()

    def get_with_messages(self, session_id: str) -> ChatSession | None:
        return self.db.execute(
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.session_id == session_id)
        ).scalar_one_or_none()

    def create(
        self,
        *,
        session_id: str,
        title: str = "",
        user_ip: str | None = None,
        user_agent: str | None = None,
        referrer: str | None = None,
        metadata_json: str = "{}",
    ) -> ChatSession:
        row = ChatSession(
            session_id=session_id,
            title=title,
            status="active",
            user_ip=user_ip,
            user_agent=user_agent,
            referrer=referrer,
            metadata_json=metadata_json,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, session: ChatSession) -> ChatSession:
        session.updated_at = utcnow()
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
        query: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[ChatSession], int]:
        stmt = select(ChatSession)
        count_stmt = select(func.count()).select_from(ChatSession)

        if status:
            stmt = stmt.where(ChatSession.status == status)
            count_stmt = count_stmt.where(ChatSession.status == status)
        if query:
            pattern = f"%{query.strip()}%"
            filt = or_(ChatSession.title.ilike(pattern), ChatSession.session_id.ilike(pattern))
            stmt = stmt.where(filt)
            count_stmt = count_stmt.where(filt)
        if date_from:
            stmt = stmt.where(ChatSession.created_at >= date_from)
            count_stmt = count_stmt.where(ChatSession.created_at >= date_from)
        if date_to:
            stmt = stmt.where(ChatSession.created_at <= date_to)
            count_stmt = count_stmt.where(ChatSession.created_at <= date_to)

        total = self.db.execute(count_stmt).scalar_one()
        stmt = (
            stmt.order_by(ChatSession.last_message_at.desc().nulls_last(), ChatSession.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
