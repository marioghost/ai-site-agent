"""Background worker for Source Intelligence generation."""
from __future__ import annotations

import json
import threading

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.repositories.index_job_repository import IndexJobRepository
from app.repositories.settings_repository import SettingsRepository
from app.services.indexing_progress import IndexingProgress
from app.services.source_intelligence_generation_service import (
    IntelligenceOptions,
    SourceIntelligenceGenerationService,
)
from app.services.source_intelligence_progress_tracker import (
    SourceIntelligenceProgressTracker,
)
from app.utils.time_utils import utcnow

logger = get_logger(__name__)


class IntelligenceJobState:
    def __init__(self) -> None:
        self.job_id: int | None = None
        self.status: str = "idle"
        self.phase: str = "idle"
        self.selected_sources: int = 0
        self.processed_sources: int = 0
        self.current_url: str | None = None
        self.message: str = ""
        self.dry_run: bool = False


class SourceIntelligenceWorker:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._state = IntelligenceJobState()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def status(self) -> IntelligenceJobState:
        return self._state

    def stop(self) -> None:
        self._stop_event.set()

    def start(self, options: IntelligenceOptions) -> int:
        with self._lock:
            if self.is_running():
                raise RuntimeError("A Source Intelligence job is already running")
            self._stop_event.clear()
            db = SessionLocal()
            try:
                repo = IndexJobRepository(db)
                job = repo.create()
                job.current_phase = "selecting_sources"
                job.started_at = utcnow()
                job.updated_at = utcnow()
                progress = IndexingProgress()
                progress.run_mode = "source_intelligence"
                progress.set_stage(
                    "preparing",
                    phase="selecting_sources",
                    message="Starting Source Intelligence",
                )
                progress.apply_to_job(job)
                payload = json.loads(job.progress_json or "{}")
                payload["job_kind"] = "source_intelligence"
                payload["dry_run"] = options.dry_run
                payload["scope"] = options.scope
                job.progress_json = json.dumps(payload, ensure_ascii=False)
                repo.save(job)
                job_id = job.id
            finally:
                db.close()

            self._state = IntelligenceJobState()
            self._state.job_id = job_id
            self._state.status = "running"
            self._state.dry_run = options.dry_run
            self._thread = threading.Thread(
                target=self._run,
                args=(job_id, options),
                daemon=True,
            )
            self._thread.start()
            return job_id

    def _run(self, job_id: int, options: IntelligenceOptions) -> None:
        db = SessionLocal()
        try:
            settings = SettingsRepository(db).get_or_create()
            service = SourceIntelligenceGenerationService(db, settings)
            job_repo = IndexJobRepository(db)
            flush_every = int(
                getattr(settings, "source_intelligence_progress_flush_every_sources", 10) or 10
            )
            flush_interval = float(
                getattr(settings, "source_intelligence_progress_flush_interval_seconds", 3) or 3
            )
            tracker = SourceIntelligenceProgressTracker(
                job_repo,
                job_id,
                flush_every_sources=flush_every,
                flush_interval_seconds=flush_interval,
            )

            def on_progress(phase: str, message: str, extra: dict) -> None:
                if self._stop_event.is_set():
                    return
                processed = int(extra.get("processed") or extra.get("updated") or 0)
                selected = int(extra.get("selected_sources") or extra.get("selected") or 0)
                url = extra.get("url") or (message if message.startswith("http") else None)
                self._state.phase = phase
                self._state.message = message
                self._state.current_url = url
                self._state.processed_sources = processed
                if selected:
                    self._state.selected_sources = selected
                force = phase in {
                    "completed",
                    "failed",
                    "invalidating_cache",
                    "rebuilding_understanding",
                }
                tracker.tick(
                    phase=phase,
                    message=message,
                    url=url,
                    selected=selected or self._state.selected_sources or None,
                    processed=processed,
                    extra=extra,
                    force=force,
                )

            if options.dry_run:
                result = service.run(
                    options,
                    on_progress=on_progress,
                    should_stop=self._stop_event.is_set,
                )
                if self._stop_event.is_set():
                    self._finish_job(job_repo, job_id, status="stopped", extra=result)
                    self._state.status = "stopped"
                    return
                self._state.status = "completed"
                self._state.selected_sources = int(result.get("selected_sources") or 0)
                tracker.finish(
                    phase="completed",
                    message=f"Dry run: {result.get('selected_sources', 0)} sources",
                    selected=int(result.get("selected_sources") or 0),
                    processed=0,
                    extra={"dry_run": True, **result},
                )
                job = job_repo.get(job_id)
                if job:
                    job.status = "completed"
                    job.finished_at = utcnow()
                    job.current_phase = "completed"
                    job_repo.save(job)
                return

            selected = service.count_sources(options)
            self._state.selected_sources = selected
            if selected <= 0 and not options.dry_run:
                self._state.status = "completed"
                tracker.finish(
                    phase="completed",
                    message="No sources need intelligence updates",
                    selected=0,
                    processed=0,
                    extra={"selected_sources": 0, "updated_sources": 0, "empty_run": True},
                )
                job = job_repo.get(job_id)
                if job:
                    job.status = "completed"
                    job.finished_at = utcnow()
                    job.current_phase = "completed"
                    job_repo.save(job)
                return

            on_progress(
                "analyzing_sources",
                f"Analyzing {selected} sources",
                {"selected": selected, "selected_sources": selected, "processed": 0},
            )

            result = service.run(
                options,
                on_progress=on_progress,
                should_stop=self._stop_event.is_set,
            )

            if self._stop_event.is_set() or result.get("stopped"):
                self._state.status = "stopped"
                self._finish_job(job_repo, job_id, status="stopped", extra=result)
                return

            self._state.status = "completed"
            self._state.processed_sources = int(result.get("processed_sources") or 0)
            tracker.finish(
                phase="completed",
                message=f"Updated {result.get('updated_sources', 0)} source profiles",
                selected=int(result.get("selected_sources") or selected),
                processed=int(result.get("processed_sources") or 0),
                extra=result,
            )
            job = job_repo.get(job_id)
            if job:
                job.status = "completed"
                job.finished_at = utcnow()
                job.current_phase = "completed"
                job_repo.save(job)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Source Intelligence job failed: %s", exc)
            self._state.status = "failed"
            self._state.message = str(exc)
            try:
                job = IndexJobRepository(db).get(job_id)
                if job:
                    job.status = "failed"
                    job.finished_at = utcnow()
                    job.current_phase = "failed"
                    if "tracker" in locals():
                        tracker.finish(
                            phase="failed",
                            message=str(exc),
                            selected=self._state.selected_sources,
                            processed=self._state.processed_sources,
                            extra={"error": str(exc)},
                        )
                    else:
                        job_repo.save(job)
            except Exception:  # noqa: BLE001
                pass
        finally:
            db.close()
            self._stop_event.clear()

    @staticmethod
    def _finish_job(job_repo, job_id: int, *, status: str, extra: dict) -> None:
        job = job_repo.get(job_id)
        if not job:
            return
        job.status = status
        job.finished_at = utcnow()
        job.current_phase = status
        payload = json.loads(job.progress_json or "{}")
        payload.update(extra)
        payload["stopped"] = status == "stopped"
        job.progress_json = json.dumps(payload, ensure_ascii=False)
        job_repo.save(job)


source_intelligence_worker = SourceIntelligenceWorker()
