"""Background worker for reprocessing existing indexed sources."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass

from app.core.config import get_config
from app.core.database import SessionLocal
from app.core.job_progress_tracker import JobProgressThrottle
from app.core.logging import get_logger
from app.repositories.index_job_repository import IndexJobRepository
from app.repositories.job_event_repository import JobEventRepository
from app.repositories.settings_repository import SettingsRepository
from app.services.indexing_progress import IndexingProgress
from app.services.reprocess_service import ReprocessOptions, ReprocessService
from app.utils.time_utils import isoformat_now, utcnow

logger = get_logger(__name__)


@dataclass
class ReprocessJobState:
    job_id: int | None = None
    status: str = "idle"
    phase: str = "idle"
    selected_sources: int = 0
    processed_sources: int = 0
    failed_sources: int = 0
    skipped_sources: int = 0
    chunks_rebuilt: int = 0
    current_url: str | None = None
    message: str = ""


class ReprocessWorker:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._state = ReprocessJobState()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def status(self) -> ReprocessJobState:
        return self._state

    def stop(self) -> None:
        self._stop_event.set()

    def start(self, options: ReprocessOptions) -> int:
        with self._lock:
            if self.is_running():
                raise RuntimeError("A reprocess job is already running")
            self._stop_event.clear()
            db = SessionLocal()
            try:
                repo = IndexJobRepository(db)
                job = repo.create()
                job.current_phase = "selecting_sources"
                job.started_at = utcnow()
                job.updated_at = utcnow()
                progress = IndexingProgress()
                progress.run_mode = "reprocess"
                progress.set_stage("preparing", phase="selecting_sources", message="Starting reprocess")
                progress.apply_to_job(job)
                job.progress_json = json.dumps(
                    {"job_kind": "reprocess", **json.loads(job.progress_json or "{}")},
                    ensure_ascii=False,
                )
                repo.save(job)
                job_id = job.id
            finally:
                db.close()
            self._state = ReprocessJobState(job_id=job_id, status="running")
            self._thread = threading.Thread(
                target=self._run,
                args=(job_id, options),
                daemon=True,
            )
            self._thread.start()
            return job_id

    @staticmethod
    def _append_log(job, level: str, message: str) -> None:
        try:
            entries = json.loads(job.log_json or "[]")
        except (json.JSONDecodeError, TypeError):
            entries = []
        entries.append(
            {"timestamp": isoformat_now(), "level": level, "message": message}
        )
        job.log_json = json.dumps(entries[-200:], ensure_ascii=False)

    def _run(self, job_id: int, options: ReprocessOptions) -> None:
        db = SessionLocal()
        cfg = get_config()
        throttle = JobProgressThrottle(
            flush_every_items=cfg.progress_flush_every_items,
            flush_interval_seconds=cfg.progress_flush_interval_seconds,
        )
        event_repo = JobEventRepository(db)
        try:
            settings = SettingsRepository(db).get_or_create()
            service = ReprocessService(db, settings)
            job_repo = IndexJobRepository(db)
            progress = IndexingProgress()
            progress.run_mode = "reprocess"

            def on_progress(phase: str, message: str, extra: dict) -> None:
                self._state.phase = phase
                self._state.message = message
                self._state.current_url = extra.get("url")
                if "selected" in extra:
                    self._state.selected_sources = extra["selected"]
                if "processed" in extra:
                    self._state.processed_sources = extra["processed"]
                    self._state.failed_sources = extra.get("failed", 0)
                    self._state.skipped_sources = extra.get("skipped", 0)

                force = phase in {
                    "selecting_sources",
                    "detecting_boilerplate",
                    "completed",
                    "failed",
                    "stopped",
                }
                if not throttle.should_flush(force=force):
                    return

                progress.apply_reprocess_tick(
                    phase=phase,
                    message=message,
                    url=extra.get("url"),
                    selected=extra.get("selected"),
                    processed=int(extra.get("processed") or 0),
                    failed=int(extra.get("failed") or 0),
                    skipped=int(extra.get("skipped") or 0),
                )
                job = job_repo.get(job_id)
                if job:
                    progress.apply_to_job(job)
                    payload = json.loads(job.progress_json or "{}")
                    payload["job_kind"] = "reprocess"
                    job.progress_json = json.dumps(payload, ensure_ascii=False)
                    job.updated_at = utcnow()
                    level = "error" if phase == "failed" else "info"
                    self._append_log(job, level, message)
                    event_repo.append(job_id, level, message)
                    job_repo.save(job)
                    throttle.mark_flushed()

            if options.dry_run:
                preview = service.preview(options)
                self._state.selected_sources = preview.selected_sources
                self._state.status = "completed"
                job = job_repo.get(job_id)
                if job:
                    job.status = "completed"
                    job.finished_at = utcnow()
                    job.progress_json = json.dumps(
                        {"job_kind": "reprocess", "dry_run": True, **preview.__dict__},
                        ensure_ascii=False,
                    )
                    job_repo.save(job)
                return

            result = service.run(
                options,
                on_progress=on_progress,
                cancel_check=self._stop_event.is_set,
            )
            stopped = bool(result.get("stopped"))
            self._state.status = "stopped" if stopped else "completed"
            self._state.processed_sources = result.get("processed_sources", 0)
            self._state.failed_sources = result.get("failed_sources", 0)
            self._state.skipped_sources = result.get("skipped_sources", 0)
            self._state.chunks_rebuilt = result.get("chunks_rebuilt", 0)
            job = job_repo.get(job_id)
            if job:
                job.status = "stopped" if stopped else "completed"
                job.finished_at = utcnow()
                job.current_phase = "stopped" if stopped else "completed"
                progress.apply_reprocess_tick(
                    phase="stopped" if stopped else "completed",
                    message=(
                        "Reprocess stopped by user"
                        if stopped
                        else f"Reprocess complete: {self._state.processed_sources} updated"
                    ),
                    selected=result.get("selected_sources", self._state.selected_sources),
                    processed=self._state.processed_sources,
                    failed=self._state.failed_sources,
                    skipped=self._state.skipped_sources,
                )
                progress.apply_to_job(job)
                payload = json.loads(job.progress_json or "{}")
                payload["job_kind"] = "reprocess"
                payload.update(result)
                job.progress_json = json.dumps(payload, ensure_ascii=False)
                self._append_log(
                    job,
                    "info",
                    "Reprocess stopped" if stopped else "Reprocess completed",
                )
                job_repo.save(job)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Reprocess job failed: %s", exc)
            self._state.status = "failed"
            self._state.message = str(exc)
            try:
                job = IndexJobRepository(db).get(job_id)
                if job:
                    job.status = "failed"
                    job.finished_at = utcnow()
                    self._append_log(job, "error", str(exc))
                    IndexJobRepository(db).save(job)
            except Exception:  # noqa: BLE001
                pass
        finally:
            db.close()
            self._stop_event.clear()


reprocess_worker = ReprocessWorker()
