"""Repository for index jobs."""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.index_job import IndexJob
from app.utils.time_utils import utcnow


class IndexJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def fail_stale_running(self) -> int:
        """Mark any 'running' jobs as 'failed'.

        Called on startup: if the process was killed mid-job the worker thread
        is gone but the DB row is left at 'running', which otherwise makes the
        dashboard show a job that can never be stopped.
        """
        result = self.db.execute(
            update(IndexJob)
            .where(IndexJob.status == "running")
            .values(status="failed", finished_at=utcnow(), current_url=None)
        )
        self.db.commit()
        return result.rowcount or 0

    def create(self) -> IndexJob:
        job = IndexJob(status="running")
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, job_id: int) -> IndexJob | None:
        return self.db.get(IndexJob, job_id)

    def latest(self) -> IndexJob | None:
        return self.db.execute(
            select(IndexJob).order_by(IndexJob.id.desc()).limit(1)
        ).scalar_one_or_none()

    def save(self, job: IndexJob) -> IndexJob:
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
