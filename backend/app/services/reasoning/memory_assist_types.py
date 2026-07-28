"""Reasoning-owned DTOs for advisory Memory evidence assist (RFC-100 Step 047)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

MemoryAssistPath = Literal["off", "skipped", "used", "empty", "sparse", "failed"]

SKIP_REASONING_DISABLED = "reasoning_disabled"
SKIP_CACHE_NAMESPACE_V2_REQUIRED = "cache_namespace_v2_required"
SKIP_FLAG_OFF = "flag_off"
SKIP_CORPUS_UNCONFIGURED = "corpus_scope_unconfigured"

_DEBUG_ID_CAP = 20


@dataclass(frozen=True)
class MemoryAssistResult:
    """Advisory Memory read outcome — no claim text or scores."""

    attempted: bool
    path: MemoryAssistPath
    region_found: bool
    matched_claim_count: int
    supported_claim_count: int
    conflicted_claim_count: int
    source_ids: tuple[int, ...]
    observation_ref_ids: tuple[int, ...]
    topic_hints: tuple[str, ...]
    page_role_hints: tuple[str, ...]
    limitations: tuple[str, ...]
    corpus_limitations: tuple[str, ...]
    corpus_scope_configured: bool
    corpus_scope_complete: bool
    completeness_unknown: bool
    usable_for_evidence: bool
    assist_reason: str | None = None
    skipped_reason: str | None = None
    memory_read_duration_ms: int | None = None
    memory_version: int | None = None
    claim_ids: tuple[int, ...] = ()
    corpus_boundary_fingerprint: str | None = None

    @staticmethod
    def off(*, skipped_reason: str | None = SKIP_FLAG_OFF) -> MemoryAssistResult:
        return MemoryAssistResult(
            attempted=False,
            path="off",
            region_found=False,
            matched_claim_count=0,
            supported_claim_count=0,
            conflicted_claim_count=0,
            source_ids=(),
            observation_ref_ids=(),
            topic_hints=(),
            page_role_hints=(),
            limitations=(),
            corpus_limitations=(),
            corpus_scope_configured=False,
            corpus_scope_complete=False,
            completeness_unknown=True,
            usable_for_evidence=False,
            skipped_reason=skipped_reason,
        )

    @staticmethod
    def skipped(reason: str) -> MemoryAssistResult:
        return MemoryAssistResult(
            attempted=False,
            path="skipped",
            region_found=False,
            matched_claim_count=0,
            supported_claim_count=0,
            conflicted_claim_count=0,
            source_ids=(),
            observation_ref_ids=(),
            topic_hints=(),
            page_role_hints=(),
            limitations=(),
            corpus_limitations=(),
            corpus_scope_configured=False,
            corpus_scope_complete=False,
            completeness_unknown=True,
            usable_for_evidence=False,
            skipped_reason=reason,
        )

    def to_diagnostics(self) -> dict[str, Any]:
        """Bounded diagnostics — no claim proposition text."""
        payload: dict[str, Any] = {
            "memory_assist_path": self.path,
            "memory_region_source_count": len(self.source_ids),
            "memory_claim_count": self.matched_claim_count,
            "memory_supported_claim_count": self.supported_claim_count,
            "memory_conflicted_claim_count": self.conflicted_claim_count,
            "memory_completeness_unknown": self.completeness_unknown,
            "memory_limitations": list(self.limitations),
            "memory_corpus_limitations": list(self.corpus_limitations),
            "memory_scope_configured": self.corpus_scope_configured,
            "memory_scope_complete": self.corpus_scope_complete,
            "memory_version": self.memory_version,
            "memory_observation_hints_count": len(self.observation_ref_ids),
            "memory_affected_evidence_assembly": False,
            "memory_assist_reason": self.assist_reason,
            "memory_skipped_reason": self.skipped_reason,
            "memory_read_duration_ms": self.memory_read_duration_ms,
            "memory_usable_for_evidence": self.usable_for_evidence,
            "memory_region_found": self.region_found,
        }
        if self.claim_ids:
            payload["memory_claim_ids"] = list(self.claim_ids[:_DEBUG_ID_CAP])
        if self.observation_ref_ids:
            payload["memory_observation_ref_ids"] = list(
                self.observation_ref_ids[:_DEBUG_ID_CAP]
            )
        if self.source_ids:
            payload["memory_source_ids"] = list(self.source_ids[:_DEBUG_ID_CAP])
        if self.corpus_boundary_fingerprint:
            payload["memory_corpus_boundary_fingerprint"] = self.corpus_boundary_fingerprint
        return payload
