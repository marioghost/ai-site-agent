"""Ephemeral investigation execution results (RFC-100 Step 060)."""
from __future__ import annotations

from dataclasses import dataclass

STATUS_SUCCEEDED = "succeeded"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"

REASON_UNSUPPORTED_ACTION = "unsupported_action"
REASON_TARGET_UNRESOLVED = "target_unresolved"
REASON_TARGET_AMBIGUOUS = "target_ambiguous"
REASON_SOURCE_MISSING = "source_missing"
REASON_SOURCE_URL_UNAVAILABLE = "source_url_unavailable"
REASON_FETCH_DISALLOWED = "fetch_disallowed"
REASON_INDEXING_BUSY = "indexing_busy"
REASON_CONTENT_UNCHANGED = "content_unchanged"
REASON_FETCH_FAILED = "fetch_failed"
REASON_PARSE_FAILED = "parse_failed"
REASON_INDEX_FAILED = "index_failed"
REASON_SI_FAILED = "si_failed"
REASON_MEMORY_SHADOW_WRITE_FAILED = "memory_shadow_write_failed"
REASON_INTERRUPTED = "interrupted"

VERB_FETCH = "fetch"


@dataclass(frozen=True)
class InvestigationDispatch:
    """In-memory dispatch record. Not ORM. Not persisted."""

    plan_id: str
    verb: str
    source_id: int
    url: str


@dataclass(frozen=True)
class InvestigationPlanResult:
    """Ephemeral per-plan attempt outcome. Not ORM. Not persisted."""

    status: str
    reason: str | None
    plan_id: str
    source_id: int | None
    url: str | None
    downstream_result: str | None


@dataclass(frozen=True)
class InvestigationCycleResult:
    """Ephemeral cycle aggregate. Not persisted. No event bus. No analytics."""

    plan_results: tuple[InvestigationPlanResult, ...]
    succeeded: int
    skipped: int
    failed: int
