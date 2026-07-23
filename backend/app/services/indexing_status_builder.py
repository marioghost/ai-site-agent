"""Build user-friendly indexing status fields for the API."""
from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.indexing import (
    IndexActivityEntry,
    IndexAdvancedStatus,
    IndexJobStatus,
    IndexLogEntry,
    IndexRunProgress,
    IndexRunSummary,
)
from app.services.indexing_progress import IndexingProgress
from app.services.indexing_stages import resolve_stage
from app.utils.time_utils import utcnow

# Heartbeat thresholds (seconds)
HEARTBEAT_ACTIVE = 30
HEARTBEAT_SLOW = 120
HEARTBEAT_STUCK = 300


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def compute_heartbeat_state(
    last_activity_at: str | None,
    *,
    now: datetime | None = None,
) -> tuple[str, int | None]:
    """Return (alive_state, seconds_since_activity)."""
    ref = now or utcnow()
    if ref.tzinfo is not None:
        ref = ref.replace(tzinfo=None)
    last = _parse_iso(last_activity_at)
    if last is None:
        return "unknown", None
    if last.tzinfo is not None:
        last = last.replace(tzinfo=None)
    delta = int((ref - last).total_seconds())
    if delta < 0:
        delta = 0
    if delta <= HEARTBEAT_ACTIVE:
        return "active", delta
    if delta <= HEARTBEAT_SLOW:
        return "slow", delta
    if delta >= HEARTBEAT_STUCK:
        return "stuck", delta
    return "slow", delta


def compute_run_progress(prog: IndexingProgress) -> IndexRunProgress:
    selected_pages = prog.queue.queued_pages_for_this_run
    selected_files = prog.files.queued_files_for_this_run
    selected_total = selected_pages + selected_files
    processed_total = prog.pages.processed_pages + prog.files.processed_files

    if selected_total > 0:
        percent = round(min(100.0, processed_total / selected_total * 100), 1)
        return IndexRunProgress(
            selected_total=selected_total,
            processed_total=processed_total,
            selected_pages=selected_pages,
            selected_files=selected_files,
            processed_pages=prog.pages.processed_pages,
            processed_files=prog.files.processed_files,
            percent=percent,
            is_indeterminate=False,
        )

    return IndexRunProgress(
        selected_total=0,
        processed_total=processed_total,
        selected_pages=selected_pages,
        selected_files=selected_files,
        processed_pages=prog.pages.processed_pages,
        processed_files=prog.files.processed_files,
        percent=None,
        is_indeterminate=True,
    )


def compute_run_summary(prog: IndexingProgress) -> IndexRunSummary:
    added = prog.pages.indexed_new_pages + prog.files.indexed_new_files
    updated = prog.pages.updated_pages + prog.files.updated_files
    unchanged = prog.pages.unchanged_pages + prog.files.unchanged_files
    skipped = (
        prog.pages.skipped_empty_pages
        + prog.pages.skipped_fresh_pages
        + prog.files.skipped_files
    )
    errors = prog.pages.failed_pages + prog.files.failed_files

    return IndexRunSummary(
        found_pages=prog.discovery.discovered_pages,
        found_files=prog.discovery.discovered_files,
        selected_pages=prog.queue.queued_pages_for_this_run,
        selected_files=prog.files.queued_files_for_this_run,
        processed_pages=prog.pages.processed_pages,
        processed_files=prog.files.processed_files,
        added=added,
        updated=updated,
        unchanged=unchanged,
        skipped=skipped,
        errors=errors,
    )


def log_to_recent_activity(
    entries: list[IndexLogEntry], *, limit: int = 20
) -> list[IndexActivityEntry]:
    tail = entries[-limit:]
    return [
        IndexActivityEntry(
            time=e.timestamp,
            level=e.level,
            message=e.message,
        )
        for e in tail
    ]


def enrich_job_status(status: IndexJobStatus, prog: IndexingProgress) -> IndexJobStatus:
    """Attach user-friendly fields to a base IndexJobStatus."""
    alive, seconds = compute_heartbeat_state(prog.last_activity_at)
    stage = resolve_stage(prog.stage, prog.current_phase)

    status.stage = stage
    status.run_mode = prog.run_mode if prog.run_mode != "full" else None
    status.current_url_type = prog.current_url_type
    status.current_action = prog.current_action
    status.last_activity_at = prog.last_activity_at
    status.last_activity_message = prog.last_activity_message
    status.heartbeat_counter = prog.heartbeat_counter
    status.alive_state = alive
    status.seconds_since_activity = seconds
    status.progress = compute_run_progress(prog)
    status.summary = compute_run_summary(prog)
    status.recent_activity = log_to_recent_activity(status.log_tail or [])
    status.advanced = IndexAdvancedStatus(
        current_phase=prog.current_phase,
        discovery=status.discovery,
        queue=status.queue,
        pages=status.pages,
        files=status.files,
        errors_count=prog.errors_count,
        log=status.log,
    )
    return status
