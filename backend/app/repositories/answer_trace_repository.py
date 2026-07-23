"""Repository for answer traces."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.answer_trace import AnswerTrace


class AnswerTraceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> AnswerTrace:
        row = AnswerTrace(**kwargs)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_request_id(self, request_id: str) -> AnswerTrace | None:
        return self.db.execute(
            select(AnswerTrace).where(AnswerTrace.request_id == request_id)
        ).scalar_one_or_none()

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        session_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        cache_hit: bool | None = None,
        used_context: bool | None = None,
        min_total_ms: int | None = None,
        query: str | None = None,
    ) -> tuple[list[AnswerTrace], int]:
        stmt = select(AnswerTrace)
        count_stmt = select(func.count()).select_from(AnswerTrace)
        if session_id:
            stmt = stmt.where(AnswerTrace.session_id == session_id)
            count_stmt = count_stmt.where(AnswerTrace.session_id == session_id)
        if date_from:
            stmt = stmt.where(AnswerTrace.created_at >= date_from)
            count_stmt = count_stmt.where(AnswerTrace.created_at >= date_from)
        if date_to:
            stmt = stmt.where(AnswerTrace.created_at <= date_to)
            count_stmt = count_stmt.where(AnswerTrace.created_at <= date_to)
        if cache_hit is not None:
            stmt = stmt.where(AnswerTrace.cache_hit == cache_hit)
            count_stmt = count_stmt.where(AnswerTrace.cache_hit == cache_hit)
        if used_context is not None:
            stmt = stmt.where(AnswerTrace.used_context == used_context)
            count_stmt = count_stmt.where(AnswerTrace.used_context == used_context)
        if min_total_ms is not None:
            stmt = stmt.where(AnswerTrace.total_ms >= min_total_ms)
            count_stmt = count_stmt.where(AnswerTrace.total_ms >= min_total_ms)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                AnswerTrace.original_query.ilike(like)
                | AnswerTrace.normalized_query.ilike(like)
            )
            count_stmt = count_stmt.where(
                AnswerTrace.original_query.ilike(like)
                | AnswerTrace.normalized_query.ilike(like)
            )
        total = self.db.execute(count_stmt).scalar_one()
        stmt = (
            stmt.order_by(AnswerTrace.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.execute(stmt).scalars().all()), total

    def purge_older_than(self, days: int) -> int:
        if days <= 0:
            return 0
        cutoff = datetime.utcnow()  # noqa: DTZ003 — SQLite stores naive UTC
        from datetime import timedelta

        cutoff = cutoff - timedelta(days=days)
        rows = list(
            self.db.execute(
                select(AnswerTrace).where(AnswerTrace.created_at < cutoff)
            ).scalars().all()
        )
        for r in rows:
            self.db.delete(r)
        self.db.commit()
        return len(rows)
