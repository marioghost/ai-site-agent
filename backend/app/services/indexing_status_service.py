"""Build API status responses from IndexJob + IndexingProgress."""
from __future__ import annotations

import json
from dataclasses import asdict

from app.models.index_job import IndexJob
from app.schemas.indexing import (
    IndexDiscoveryStatus,
    IndexFilesStatus,
    IndexJobStatus,
    IndexLogEntry,
    IndexPagesStatus,
    IndexQueuePreview,
    IndexQueueStatus,
)
from app.services.indexing_progress import IndexingProgress
from app.services.indexing_status_builder import enrich_job_status


def _parse_log(job: IndexJob) -> list[IndexLogEntry]:
    try:
        raw = json.loads(job.log_json or "[]")
        return [IndexLogEntry(**e) for e in raw]
    except (json.JSONDecodeError, TypeError):
        return []


def _intelligence_extras(job: IndexJob) -> dict:
    try:
        data = json.loads(job.progress_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    if data.get("job_kind") != "source_intelligence":
        return {}
    return {
        "intelligence_sample_profiles": data.get("sample_profiles") or [],
        "intelligence_selected_sources": int(
            data.get("selected_sources") or data.get("selected") or 0
        ),
        "intelligence_updated_sources": int(data.get("updated_sources") or 0),
        "dry_run": bool(data.get("dry_run")),
        "skipped_unchanged": int(data.get("skipped_unchanged") or 0),
        "would_skip_unchanged": int(data.get("would_skip_unchanged") or 0),
        "would_call_llm": int(data.get("would_call_llm") or 0),
        "llm_cache_hits": int(data.get("llm_cache_hits") or 0),
        "llm_calls": int(data.get("llm_calls") or 0),
        "llm_failures": int(data.get("llm_failures") or 0),
        "avg_ms_per_source": float(data.get("avg_ms_per_source") or 0),
        "estimated_time_with_llm": float(data.get("estimated_time_with_llm") or 0),
        "estimated_remaining_seconds": data.get("estimated_remaining_seconds"),
        "worker_count": int(data.get("worker_count") or 0),
        "batch_size": int(data.get("batch_size") or 0),
    }


def job_to_status(job: IndexJob | None) -> IndexJobStatus:
    if job is None:
        return IndexJobStatus(status="idle", current_phase="idle", stage="idle")

    prog = IndexingProgress.from_job(job)
    log_entries = _parse_log(job)
    d = prog.discovery
    q = prog.queue
    p = prog.pages
    f = prog.files

    base = IndexJobStatus(
        id=job.id,
        status=job.status,
        current_phase=prog.current_phase,
        current_url=prog.current_url,
        started_at=job.started_at,
        updated_at=getattr(job, "updated_at", None),
        finished_at=job.finished_at,
        discovery=IndexDiscoveryStatus(**asdict(d)),
        queue=IndexQueueStatus(**asdict(q)),
        pages=IndexPagesStatus(**asdict(p)),
        files=IndexFilesStatus(**asdict(f)),
        log_tail=log_entries[-50:],
        log=log_entries,
        discovered_pages=d.discovered_pages,
        new_pages=q.new_pages_waiting,
        queued_pages=q.queued_pages_for_this_run,
        processed_pages=p.processed_pages,
        indexed_pages=p.indexed_new_pages + p.updated_pages,
        unchanged_pages=p.unchanged_pages,
        skipped_pages=p.skipped_empty_pages,
        skipped_fresh_pages=p.skipped_fresh_pages,
        failed_pages=p.failed_pages + f.failed_files,
        stale_pages=q.stale_pages_waiting,
        discovered_files=f.discovered_files or d.discovered_files,
        indexed_files=f.indexed_new_files + f.updated_files,
        skipped_files=f.skipped_files + f.unchanged_files,
        errors_count=prog.errors_count,
        run_mode=prog.run_mode if prog.run_mode != "full" else None,
        **_intelligence_extras(job),
    )
    return enrich_job_status(base, prog)


def preview_to_response(data: dict[str, int]) -> IndexQueuePreview:
    queue = IndexQueueStatus(
        new_pages_waiting=int(data.get("new_pages_waiting", data.get("new_pages", 0))),
        failed_pages_waiting=int(
            data.get("failed_pages_waiting", data.get("failed_pages", 0))
        ),
        stale_pages_waiting=int(
            data.get("stale_pages_waiting", data.get("stale_pages", 0))
        ),
        fresh_pages_skipped_until_refresh=int(
            data.get(
                "fresh_pages_skipped_until_refresh",
                data.get("fresh_pages", 0),
            )
        ),
        queued_pages_for_this_run=int(
            data.get("queued_pages_for_this_run", data.get("queued_pages", 0))
        ),
        total_pages_waiting=int(
            data.get("total_pages_waiting", data.get("queued_pages", 0))
        ),
    )
    return IndexQueuePreview(
        queue=queue,
        max_pages_per_run=int(data.get("max_pages_per_run", 0)),
        estimated_runs_remaining=int(data.get("estimated_runs_remaining", 0)),
        new_pages=queue.new_pages_waiting,
        failed_pages=queue.failed_pages_waiting,
        skipped_pages_waiting=int(data.get("skipped_pages_waiting", 0)),
        stale_pages=queue.stale_pages_waiting,
        fresh_pages=queue.fresh_pages_skipped_until_refresh,
        queued_pages=queue.total_pages_waiting,
        total_sources=int(data.get("total_sources", 0)),
    )
