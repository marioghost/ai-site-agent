"""Map sources to UI display status buckets."""
from __future__ import annotations

from datetime import datetime

from app.models.source import Source
from app.services.indexing_planner_service import CandidateClass, IndexingPlannerService
from app.utils.time_utils import utcnow

DISPLAY_READY = "ready"
DISPLAY_PENDING = "pending"
DISPLAY_FAILED = "failed"
DISPLAY_SKIPPED = "skipped"
DISPLAY_NEEDS_REFRESH = "needs_refresh"


def source_display_status(
    source: Source,
    *,
    chunk_count: int = 0,
    planner: IndexingPlannerService | None = None,
    now: datetime | None = None,
) -> str:
    status = (source.status or "pending").lower()
    if status == "error":
        if chunk_count > 0:
            return DISPLAY_NEEDS_REFRESH
        return DISPLAY_FAILED
    if status == "skipped":
        return DISPLAY_SKIPPED
    if status == "indexed" and chunk_count > 0:
        if source.needs_reprocess or source.error_message:
            return DISPLAY_NEEDS_REFRESH
        if planner and planner.classify(source, now=now) is CandidateClass.STALE:
            return DISPLAY_NEEDS_REFRESH
        return DISPLAY_READY
    return DISPLAY_PENDING
