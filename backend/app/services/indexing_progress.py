"""Unified indexing progress counters for jobs and status API.

Counter meanings (see README indexing section):
- discovery.* — URL finding during the current run
- queue.* — planner state for pages waiting / selected this run
- pages.* — page fetch/index outcomes this run
- files.* — file fetch/index outcomes this run
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.index_job import IndexJob
from app.services.indexing_stages import PHASE_TO_STAGE, resolve_stage
from app.utils.time_utils import isoformat_now


@dataclass
class IndexingDiscoveryProgress:
    discovered_urls: int = 0
    discovered_pages: int = 0
    discovered_files: int = 0
    already_known_urls: int = 0
    newly_discovered_urls: int = 0


@dataclass
class IndexingQueueProgress:
    new_pages_waiting: int = 0
    failed_pages_waiting: int = 0
    stale_pages_waiting: int = 0
    fresh_pages_skipped_until_refresh: int = 0
    queued_pages_for_this_run: int = 0
    total_pages_waiting: int = 0


@dataclass
class IndexingPagesProgress:
    processed_pages: int = 0
    indexed_new_pages: int = 0
    updated_pages: int = 0
    unchanged_pages: int = 0
    skipped_empty_pages: int = 0
    skipped_fresh_pages: int = 0
    failed_pages: int = 0


@dataclass
class IndexingFilesProgress:
    discovered_files: int = 0
    queued_files_for_this_run: int = 0
    processed_files: int = 0
    indexed_new_files: int = 0
    updated_files: int = 0
    unchanged_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0


@dataclass
class IndexingProgress:
    current_phase: str = "idle"
    stage: str = "idle"
    current_url: str | None = None
    current_url_type: str | None = None
    current_action: str | None = None
    last_activity_at: str | None = None
    last_activity_message: str | None = None
    heartbeat_counter: int = 0
    errors_count: int = 0
    run_mode: str = "full"
    discovery: IndexingDiscoveryProgress = field(
        default_factory=IndexingDiscoveryProgress
    )
    queue: IndexingQueueProgress = field(default_factory=IndexingQueueProgress)
    pages: IndexingPagesProgress = field(default_factory=IndexingPagesProgress)
    files: IndexingFilesProgress = field(default_factory=IndexingFilesProgress)

    def reset_for_job(self) -> None:
        self.current_phase = "discovery"
        self.stage = "preparing"
        self.current_url = None
        self.current_url_type = None
        self.current_action = None
        self.last_activity_at = None
        self.last_activity_message = None
        self.heartbeat_counter = 0
        self.errors_count = 0
        self.discovery = IndexingDiscoveryProgress()
        self.queue = IndexingQueueProgress()
        self.pages = IndexingPagesProgress()
        self.files = IndexingFilesProgress()
        self.run_mode = "full"

    def set_stage(
        self,
        stage: str,
        *,
        phase: str | None = None,
        action: str | None = None,
        message: str | None = None,
    ) -> None:
        self.stage = stage
        if phase is not None:
            self.current_phase = phase
        elif stage in PHASE_TO_STAGE.values():
            for legacy, mapped in PHASE_TO_STAGE.items():
                if mapped == stage:
                    self.current_phase = legacy
                    break
        if action is not None:
            self.current_action = action
        if message:
            self.record_activity(message)

    def record_activity(self, message: str) -> None:
        self.heartbeat_counter += 1
        self.last_activity_at = isoformat_now()
        self.last_activity_message = message

    def set_current_url(
        self,
        url: str | None,
        *,
        url_type: str | None = None,
        action: str | None = None,
        message: str | None = None,
    ) -> None:
        self.current_url = url
        if url_type is not None:
            self.current_url_type = url_type
        if action is not None:
            self.current_action = action
        if message:
            self.record_activity(message)
        elif url:
            self.record_activity(f"Processing: {url}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_phase": self.current_phase,
            "stage": self.stage,
            "current_url": self.current_url,
            "current_url_type": self.current_url_type,
            "current_action": self.current_action,
            "last_activity_at": self.last_activity_at,
            "last_activity_message": self.last_activity_message,
            "heartbeat_counter": self.heartbeat_counter,
            "errors_count": self.errors_count,
            "run_mode": self.run_mode,
            "discovery": asdict(self.discovery),
            "queue": asdict(self.queue),
            "pages": asdict(self.pages),
            "files": asdict(self.files),
        }

    @classmethod
    def from_reprocess_dict(
        cls, data: dict[str, Any], job: IndexJob | None = None
    ) -> IndexingProgress:
        """Map flat reprocess worker progress_json to unified counters."""
        prog = cls()
        prog.run_mode = "reprocess"
        phase = str(data.get("phase") or data.get("current_phase") or "idle")
        prog.current_phase = phase
        prog.stage = resolve_stage(data.get("stage"), phase)
        prog.current_url = (
            data.get("url")
            or data.get("current_url")
            or (getattr(job, "current_url", None) if job else None)
        )
        prog.current_url_type = data.get("current_url_type") or "page"
        prog.current_action = data.get("current_action") or data.get("message")
        prog.last_activity_message = data.get("message") or data.get(
            "last_activity_message"
        )
        prog.last_activity_at = data.get("last_activity_at")
        prog.heartbeat_counter = int(data.get("heartbeat_counter") or 0)

        queue = data.get("queue") or {}
        pages = data.get("pages") or {}
        selected = int(
            data.get("selected")
            or data.get("selected_sources")
            or queue.get("queued_pages_for_this_run")
            or 0
        )
        processed = int(
            data.get("processed")
            or data.get("processed_sources")
            or pages.get("updated_pages")
            or 0
        )
        failed = int(
            data.get("failed")
            or data.get("failed_sources")
            or pages.get("failed_pages")
            or 0
        )
        skipped = int(
            data.get("skipped")
            or data.get("skipped_sources")
            or pages.get("skipped_empty_pages")
            or 0
        )
        handled = int(pages.get("processed_pages") or processed + failed + skipped)

        prog.queue.queued_pages_for_this_run = selected
        prog.pages.processed_pages = handled
        prog.pages.updated_pages = processed
        prog.pages.failed_pages = failed
        prog.pages.skipped_empty_pages = skipped
        prog.errors_count = failed
        return prog

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> IndexingProgress:
        if not data:
            return cls()
        if data.get("job_kind") == "reprocess":
            return cls.from_reprocess_dict(data)
        if data.get("job_kind") == "source_intelligence":
            prog = cls.from_reprocess_dict(data)
            prog.run_mode = "source_intelligence"
            return prog
        prog = cls()
        prog.current_phase = str(data.get("current_phase") or "idle")
        prog.stage = resolve_stage(
            data.get("stage"), prog.current_phase
        )
        prog.current_url = data.get("current_url")
        prog.current_url_type = data.get("current_url_type")
        prog.current_action = data.get("current_action")
        prog.last_activity_at = data.get("last_activity_at")
        prog.last_activity_message = data.get("last_activity_message")
        prog.heartbeat_counter = int(data.get("heartbeat_counter") or 0)
        prog.errors_count = int(data.get("errors_count") or 0)
        prog.run_mode = str(data.get("run_mode") or "full")
        for section, factory in (
            ("discovery", IndexingDiscoveryProgress),
            ("queue", IndexingQueueProgress),
            ("pages", IndexingPagesProgress),
            ("files", IndexingFilesProgress),
        ):
            raw = data.get(section) or {}
            setattr(
                prog,
                section,
                factory(
                    **{
                        k: int(raw.get(k) or 0)
                        for k in factory.__dataclass_fields__
                    }
                ),
            )
        return prog

    @classmethod
    def from_job(cls, job: IndexJob) -> IndexingProgress:
        raw = getattr(job, "progress_json", None) or ""
        if raw:
            try:
                data = json.loads(raw)
                if data.get("job_kind") == "reprocess":
                    return cls.from_reprocess_dict(data, job)
                if data.get("job_kind") == "source_intelligence":
                    prog = cls.from_reprocess_dict(data, job)
                    prog.run_mode = "source_intelligence"
                    return prog
                return cls.from_dict(data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls.from_legacy_job(job)

    def apply_reprocess_tick(
        self,
        *,
        phase: str,
        message: str,
        url: str | None = None,
        selected: int | None = None,
        processed: int = 0,
        failed: int = 0,
        skipped: int = 0,
        action: str | None = None,
    ) -> None:
        """Update unified counters from a reprocess worker tick."""
        self.run_mode = "reprocess"
        self.set_stage(
            resolve_stage(None, phase),
            phase=phase,
            action=action or message,
            message=message,
        )
        if url:
            self.set_current_url(url, url_type="page", message=message)
        elif phase in {
            "rebuilding_understanding",
            "invalidating_cache",
            "finalize",
            "completed",
            "failed",
            "stopped",
        }:
            # Long post-SI phases are not page-bound — clear stale URL from last source.
            self.current_url = None
        if selected is not None:
            self.queue.queued_pages_for_this_run = selected
        handled = processed + failed + skipped
        self.pages.processed_pages = handled
        self.pages.updated_pages = processed
        self.pages.failed_pages = failed
        self.pages.skipped_empty_pages = skipped
        self.errors_count = failed

    def apply_intelligence_tick(
        self,
        *,
        phase: str,
        message: str,
        url: str | None = None,
        selected: int | None = None,
        processed: int = 0,
        failed: int = 0,
        skipped: int = 0,
        action: str | None = None,
    ) -> None:
        """Update unified counters from a Source Intelligence worker tick."""
        self.apply_reprocess_tick(
            phase=phase,
            message=message,
            url=url,
            selected=selected,
            processed=processed,
            failed=failed,
            skipped=skipped,
            action=action,
        )
        self.run_mode = "source_intelligence"

    @classmethod
    def from_legacy_job(cls, job: IndexJob) -> IndexingProgress:
        """Rebuild nested counters from flat columns when progress_json is absent."""
        prog = cls()
        prog.current_phase = getattr(job, "current_phase", None) or (
            "idle"
            if job.status in ("idle", "completed", "failed", "stopped")
            else "processing"
        )
        prog.current_url = job.current_url
        prog.stage = resolve_stage(None, prog.current_phase)
        prog.errors_count = int(job.errors_count or 0)
        d = prog.discovery
        d.discovered_urls = int(job.discovered_pages or 0) + int(
            job.discovered_files or 0
        )
        d.discovered_pages = int(job.discovered_pages or 0)
        d.discovered_files = int(job.discovered_files or 0)
        q = prog.queue
        q.new_pages_waiting = int(getattr(job, "new_pages", 0) or 0)
        q.queued_pages_for_this_run = int(getattr(job, "queued_pages", 0) or 0)
        q.stale_pages_waiting = int(getattr(job, "stale_pages", 0) or 0)
        q.fresh_pages_skipped_until_refresh = int(
            getattr(job, "skipped_fresh_pages", 0) or 0
        )
        q.total_pages_waiting = (
            q.new_pages_waiting + q.failed_pages_waiting + q.stale_pages_waiting
        )
        p = prog.pages
        p.processed_pages = int(getattr(job, "processed_pages", 0) or 0)
        p.indexed_new_pages = int(job.indexed_pages or 0)
        p.unchanged_pages = int(getattr(job, "unchanged_pages", 0) or 0)
        p.skipped_empty_pages = int(job.skipped_pages or 0)
        p.skipped_fresh_pages = int(getattr(job, "skipped_fresh_pages", 0) or 0)
        p.failed_pages = int(getattr(job, "failed_pages", 0) or 0)
        f = prog.files
        f.discovered_files = int(job.discovered_files or 0)
        f.processed_files = int(getattr(job, "processed_files", 0) or 0)
        f.indexed_new_files = int(job.indexed_files or 0)
        f.skipped_files = int(job.skipped_files or 0)
        return prog

    def apply_queue_preview(self, preview) -> None:
        """Copy planner preview into queue section."""
        q = self.queue
        q.new_pages_waiting = preview.new_pages_waiting
        q.failed_pages_waiting = preview.failed_pages_waiting
        q.stale_pages_waiting = preview.stale_pages_waiting
        q.fresh_pages_skipped_until_refresh = (
            preview.fresh_pages_skipped_until_refresh
        )
        q.total_pages_waiting = preview.total_pages_waiting
        q.queued_pages_for_this_run = preview.queued_pages_for_this_run

    def apply_to_job(self, job: IndexJob) -> None:
        """Persist nested progress and mirror legacy flat columns."""
        job.progress_json = json.dumps(self.to_dict(), ensure_ascii=False)
        job.current_phase = self.current_phase
        job.current_url = self.current_url
        job.errors_count = self.errors_count

        job.discovered_pages = self.discovery.discovered_pages
        job.discovered_files = self.discovery.discovered_files
        job.new_pages = self.queue.new_pages_waiting
        job.queued_pages = self.queue.queued_pages_for_this_run
        job.stale_pages = self.queue.stale_pages_waiting
        job.processed_pages = self.pages.processed_pages
        job.indexed_pages = self.pages.indexed_new_pages + self.pages.updated_pages
        job.unchanged_pages = self.pages.unchanged_pages
        job.skipped_pages = self.pages.skipped_empty_pages
        job.skipped_fresh_pages = self.pages.skipped_fresh_pages
        job.failed_pages = self.pages.failed_pages + self.files.failed_files
        job.indexed_files = self.files.indexed_new_files + self.files.updated_files
        job.skipped_files = self.files.skipped_files + self.files.unchanged_files
        job.processed_files = self.files.processed_files
