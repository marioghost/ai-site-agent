"""Priority-based indexing candidate classification and queue planning."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from math import ceil

from app.models.source import Source
from app.utils.time_utils import to_naive_utc, utcnow


class CandidateClass(str, Enum):
    NEW = "new"
    FAILED = "failed"
    SKIPPED = "skipped"
    STALE = "stale"
    FRESH = "fresh"


PRIORITY: dict[CandidateClass, int] = {
    CandidateClass.NEW: 100,
    CandidateClass.FAILED: 80,
    CandidateClass.SKIPPED: 70,
    CandidateClass.STALE: 50,
    CandidateClass.FRESH: 10,
}

WAITING_CLASSES = (
    CandidateClass.NEW,
    CandidateClass.FAILED,
    CandidateClass.SKIPPED,
    CandidateClass.STALE,
)


@dataclass(frozen=True)
class IndexCandidate:
    source: Source
    candidate_class: CandidateClass

    @property
    def priority(self) -> int:
        return PRIORITY[self.candidate_class]


@dataclass(frozen=True)
class QueuePreviewResult:
    new_pages_waiting: int
    failed_pages_waiting: int
    stale_pages_waiting: int
    fresh_pages_skipped_until_refresh: int
    skipped_pages_waiting: int
    total_pages_waiting: int
    queued_pages_for_this_run: int
    max_pages_per_run: int
    estimated_runs_remaining: int

    def as_dict(self) -> dict[str, int]:
        return {
            "new_pages_waiting": self.new_pages_waiting,
            "failed_pages_waiting": self.failed_pages_waiting,
            "stale_pages_waiting": self.stale_pages_waiting,
            "fresh_pages_skipped_until_refresh": self.fresh_pages_skipped_until_refresh,
            "skipped_pages_waiting": self.skipped_pages_waiting,
            "total_pages_waiting": self.total_pages_waiting,
            "queued_pages_for_this_run": self.queued_pages_for_this_run,
            "max_pages_per_run": self.max_pages_per_run,
            "estimated_runs_remaining": self.estimated_runs_remaining,
            # Legacy flat keys for queue-preview API
            "new_pages": self.new_pages_waiting,
            "failed_pages": self.failed_pages_waiting,
            "stale_pages": self.stale_pages_waiting,
            "fresh_pages": self.fresh_pages_skipped_until_refresh,
            "queued_pages": self.queued_pages_for_this_run,
            "total_sources": self.total_pages_waiting + self.fresh_pages_skipped_until_refresh,
        }


class IndexingPlannerService:
    """Classifies sources and builds priority-sorted processing queues."""

    def __init__(
        self,
        *,
        page_refresh_hours: int = 168,
        file_refresh_hours: int = 168,
        force_reindex: bool = False,
    ) -> None:
        self.page_refresh_hours = max(1, page_refresh_hours)
        self.file_refresh_hours = max(1, file_refresh_hours)
        self.force_reindex = force_reindex

    def classify(self, source: Source, *, now: datetime | None = None) -> CandidateClass:
        now = to_naive_utc(now) or utcnow()
        status = (source.status or "pending").lower()

        if status in {"pending", "new"}:
            return CandidateClass.NEW
        if status == "error":
            return CandidateClass.FAILED
        if status == "skipped":
            return CandidateClass.SKIPPED
        if status == "indexed":
            if self.force_reindex:
                return CandidateClass.STALE
            refresh_at = to_naive_utc(source.next_refresh_at)
            if refresh_at is None:
                return CandidateClass.STALE
            if refresh_at <= now:
                return CandidateClass.STALE
            return CandidateClass.FRESH
        return CandidateClass.NEW

    def should_process(self, candidate_class: CandidateClass) -> bool:
        if self.force_reindex:
            return True
        return candidate_class is not CandidateClass.FRESH

    def should_fetch_for_discovery(
        self, candidate_class: CandidateClass, *, needs_link_expansion: bool
    ) -> bool:
        """Whether to HTTP-fetch a page during discovery (for link extraction)."""
        if not needs_link_expansion:
            return False
        if self.force_reindex:
            return True
        return candidate_class is not CandidateClass.FRESH

    def refresh_hours_for(self, source_type: str) -> int:
        if source_type in {"pdf", "docx", "txt"}:
            return self.file_refresh_hours
        return self.page_refresh_hours

    def compute_next_refresh(self, source: Source, *, now: datetime | None = None) -> datetime:
        now = to_naive_utc(now) or utcnow()
        hours = self.refresh_hours_for(source.source_type)
        return now + timedelta(hours=hours)

    def build_queue(self, sources: list[Source], *, now: datetime | None = None) -> list[IndexCandidate]:
        now = to_naive_utc(now) or utcnow()
        candidates: list[IndexCandidate] = []
        for source in sources:
            cls = self.classify(source, now=now)
            if self.should_process(cls):
                candidates.append(IndexCandidate(source=source, candidate_class=cls))
        candidates.sort(key=lambda c: (-c.priority, c.source.url))
        return candidates

    def count_by_class(self, sources: list[Source], *, now: datetime | None = None) -> dict[str, int]:
        counts = {c.value: 0 for c in CandidateClass}
        now = to_naive_utc(now) or utcnow()
        for source in sources:
            counts[self.classify(source, now=now).value] += 1
        return counts

    def select_candidates_for_run(
        self,
        sources: list[Source],
        max_pages_per_run: int = 0,
        *,
        now: datetime | None = None,
    ) -> list[IndexCandidate]:
        """Priority queue capped by max_pages_per_run (0 = unlimited)."""
        queue = self.build_queue(sources, now=now)
        if max_pages_per_run > 0:
            return queue[:max_pages_per_run]
        return queue

    def build_queue_preview(
        self,
        sources: list[Source],
        max_pages_per_run: int = 0,
        *,
        now: datetime | None = None,
    ) -> QueuePreviewResult:
        """Same planner logic used by the worker and GET /api/index/queue-preview."""
        now = to_naive_utc(now) or utcnow()
        counts = self.count_by_class(sources, now=now)
        total_waiting = sum(counts[c.value] for c in WAITING_CLASSES)
        full_queue = self.build_queue(sources, now=now)
        if max_pages_per_run > 0:
            selected = min(len(full_queue), max_pages_per_run)
            estimated = ceil(total_waiting / max_pages_per_run) if total_waiting else 0
        else:
            selected = len(full_queue)
            estimated = 1 if total_waiting else 0
        return QueuePreviewResult(
            new_pages_waiting=counts[CandidateClass.NEW.value],
            failed_pages_waiting=counts[CandidateClass.FAILED.value],
            stale_pages_waiting=counts[CandidateClass.STALE.value],
            fresh_pages_skipped_until_refresh=counts[CandidateClass.FRESH.value],
            skipped_pages_waiting=counts[CandidateClass.SKIPPED.value],
            total_pages_waiting=total_waiting,
            queued_pages_for_this_run=selected,
            max_pages_per_run=max_pages_per_run,
            estimated_runs_remaining=estimated,
        )
