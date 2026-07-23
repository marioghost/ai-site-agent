"""Throttled progress persistence for Source Intelligence jobs."""
from __future__ import annotations

import json
import time
from collections import deque
from typing import Callable

from app.repositories.index_job_repository import IndexJobRepository
from app.services.indexing_progress import IndexingProgress
from app.utils.time_utils import isoformat_now, utcnow


class SourceIntelligenceProgressTracker:
    def __init__(
        self,
        job_repo: IndexJobRepository,
        job_id: int,
        *,
        flush_every_sources: int = 10,
        flush_interval_seconds: float = 3.0,
    ) -> None:
        self.job_repo = job_repo
        self.job_id = job_id
        self.flush_every_sources = max(1, flush_every_sources)
        self.flush_interval_seconds = max(0.5, flush_interval_seconds)
        self._last_flush_at = 0.0
        self._since_flush = 0
        self._flush_count = 0
        self._recent_log: deque[dict] = deque(maxlen=40)
        self._pending_extra: dict = {}

    @property
    def flush_count(self) -> int:
        return self._flush_count

    def note(self, level: str, message: str) -> None:
        self._recent_log.append(
            {"timestamp": isoformat_now(), "level": level, "message": message}
        )

    def tick(
        self,
        *,
        phase: str,
        message: str,
        url: str | None = None,
        selected: int | None = None,
        processed: int = 0,
        extra: dict | None = None,
        force: bool = False,
    ) -> None:
        if extra:
            self._pending_extra.update(extra)
        self._since_flush += 1
        now = time.monotonic()
        should_flush = force or self._since_flush >= self.flush_every_sources
        if not should_flush and self.flush_interval_seconds > 0:
            should_flush = (now - self._last_flush_at) >= self.flush_interval_seconds
        if not should_flush:
            return
        self._flush(phase=phase, message=message, url=url, selected=selected, processed=processed)

    def finish(
        self,
        *,
        phase: str,
        message: str,
        selected: int,
        processed: int,
        extra: dict | None = None,
    ) -> None:
        if extra:
            self._pending_extra.update(extra)
        self._flush(
            phase=phase,
            message=message,
            url=None,
            selected=selected,
            processed=processed,
            force=True,
        )

    def _flush(
        self,
        *,
        phase: str,
        message: str,
        url: str | None,
        selected: int | None,
        processed: int,
        force: bool = False,
    ) -> None:
        job = self.job_repo.get(self.job_id)
        if not job:
            return
        progress = IndexingProgress()
        progress.run_mode = "source_intelligence"
        progress.apply_intelligence_tick(
            phase=phase,
            message=message,
            url=url,
            selected=selected,
            processed=processed,
        )
        progress.apply_to_job(job)
        payload = json.loads(job.progress_json or "{}")
        payload["job_kind"] = "source_intelligence"
        payload.update(self._pending_extra)
        job.progress_json = json.dumps(payload, ensure_ascii=False)
        job.updated_at = utcnow()
        level = "error" if phase == "failed" else "info"
        self.note(level, message)
        try:
            existing = json.loads(job.log_json or "[]")
        except (json.JSONDecodeError, TypeError):
            existing = []
        merged = (existing + list(self._recent_log))[-200:]
        job.log_json = json.dumps(merged, ensure_ascii=False)
        self.job_repo.save(job)
        self._flush_count += 1
        self._since_flush = 0
        self._last_flush_at = time.monotonic()
        self._recent_log.clear()
