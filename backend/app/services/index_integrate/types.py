"""Ephemeral Index → Integrate compose results (additive contract)."""
from __future__ import annotations

from dataclasses import dataclass

STATUS_SUCCEEDED = "succeeded"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"

STAGE_NONE = "none"
STAGE_INDEXING = "indexing"
STAGE_SOURCE_INTELLIGENCE = "source_intelligence"
STAGE_MEMORY_INTEGRATION = "memory_integration"

REASON_FETCH_FAILED = "fetch_failed"
REASON_PARSE_FAILED = "parse_failed"
REASON_INDEX_FAILED = "index_failed"
REASON_CONTENT_UNCHANGED = "content_unchanged"
REASON_SI_FAILED = "si_failed"
REASON_MEMORY_SHADOW_WRITE_FAILED = "memory_shadow_write_failed"


@dataclass(frozen=True)
class IndexIntegrateResult:
    """Ephemeral compose outcome. Not ORM. Not persisted."""

    status: str
    completed_stage: str
    failed_stage: str | None
    outcome_reason: str | None
    indexing_summary: str | None
    source_intelligence_summary: str | None
    memory_summary: str | None
