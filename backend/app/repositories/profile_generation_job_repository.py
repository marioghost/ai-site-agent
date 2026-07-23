"""Repository for profile generation jobs."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile_generation_job import ProfileGenerationJob


class ProfileGenerationJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self) -> ProfileGenerationJob:
        job = ProfileGenerationJob(status="running")
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, job_id: int) -> ProfileGenerationJob | None:
        return self.db.get(ProfileGenerationJob, job_id)

    def latest(self) -> ProfileGenerationJob | None:
        return self.db.scalars(
            select(ProfileGenerationJob).order_by(ProfileGenerationJob.id.desc())
        ).first()

    def save(self, job: ProfileGenerationJob) -> ProfileGenerationJob:
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def fail_stale_running(self) -> int:
        jobs = list(
            self.db.scalars(
                select(ProfileGenerationJob).where(
                    ProfileGenerationJob.status == "running"
                )
            ).all()
        )
        for job in jobs:
            job.status = "failed"
            job.error_message = "Interrupted by server restart"
            self.db.add(job)
        if jobs:
            self.db.commit()
        return len(jobs)
