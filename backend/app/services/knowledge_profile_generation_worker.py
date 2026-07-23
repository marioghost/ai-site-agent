"""Background worker for Knowledge Profile generation."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.profile_generation_job import ProfileGenerationJob
from app.repositories.profile_generation_job_repository import (
    ProfileGenerationJobRepository,
)
from app.schemas.knowledge_profile_generation import GenerationPreview
from app.services.knowledge_profile_generator_service import (
    KnowledgeProfileGeneratorService,
)
from app.utils.time_utils import isoformat_now, utcnow

logger = get_logger(__name__)


@dataclass
class _JobLog:
    entries: list[dict] = field(default_factory=list)

    def add(self, level: str, message: str) -> None:
        self.entries.append(
            {"timestamp": isoformat_now(), "level": level, "message": message}
        )


@dataclass
class GenerationOptions:
    use_llm: bool = True
    merge_identity: bool = False


class KnowledgeProfileGenerationWorker:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, options: GenerationOptions) -> int:
        with self._lock:
            if self.is_running():
                raise RuntimeError("Profile generation already running")
            db = SessionLocal()
            try:
                job = ProfileGenerationJobRepository(db).create()
                job.started_at = utcnow()
                job.updated_at = utcnow()
                ProfileGenerationJobRepository(db).save(job)
                job_id = job.id
            finally:
                db.close()
            self._thread = threading.Thread(
                target=self._run,
                args=(job_id, options),
                daemon=True,
            )
            self._thread.start()
            return job_id

    def _run(self, job_id: int, options: GenerationOptions) -> None:
        db = SessionLocal()
        repo = ProfileGenerationJobRepository(db)
        job = repo.get(job_id)
        log = _JobLog()
        try:
            log.add("info", "Starting Knowledge Profile generation")

            def on_stage(name: str, pct: int) -> None:
                job.current_stage = name
                job.progress_percent = pct
                job.updated_at = utcnow()
                log.add("info", f"Stage: {name} ({pct}%)")
                job.log_json = json.dumps(log.entries, ensure_ascii=False)
                repo.save(job)

            generator = KnowledgeProfileGeneratorService(db)
            preview, analytics = generator.generate(
                use_llm=options.use_llm,
                merge_identity=options.merge_identity,
                on_stage=on_stage,
            )
            job.status = "completed"
            job.current_stage = "complete"
            job.progress_percent = 100
            job.error_message = None
            job.result_json = preview.model_dump_json()
            job.analytics_json = json.dumps(analytics, ensure_ascii=False)
            job.finished_at = utcnow()
            job.updated_at = utcnow()
            log.add("info", "Generation completed successfully")
            job.log_json = json.dumps(log.entries, ensure_ascii=False)
            repo.save(job)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Profile generation failed")
            log.add("error", str(exc))
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = utcnow()
            job.updated_at = utcnow()
            job.log_json = json.dumps(log.entries, ensure_ascii=False)
            repo.save(job)
        finally:
            db.close()
            with self._lock:
                self._thread = None


profile_generation_worker = KnowledgeProfileGenerationWorker()
