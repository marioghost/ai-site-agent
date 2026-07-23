"""Repository for append-only job events."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job_event import JobEvent


class JobEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def append(
        self,
        job_id: int,
        level: str,
        message: str,
        *,
        payload: dict | None = None,
    ) -> JobEvent:
        row = JobEvent(
            job_id=job_id,
            level=level,
            message=message,
            payload_json=json.dumps(payload or {}, ensure_ascii=False),
        )
        self.db.add(row)
        return row

    def append_many(self, events: list[JobEvent]) -> None:
        self.db.add_all(events)

    def recent_for_job(self, job_id: int, limit: int = 50) -> list[JobEvent]:
        stmt = (
            select(JobEvent)
            .where(JobEvent.job_id == job_id)
            .order_by(JobEvent.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())
