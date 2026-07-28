"""DTOs and stable codes for Memory canonical shadow (RFC-100 Step 048)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

MemoryCanonicalShadowPath = Literal[
    "off", "skipped", "compared", "empty_memory", "failed"
]

CanonicalAlignment = Literal["aligned", "partial", "divergent", "not_evaluable"]

# Skip reasons (shadow policy)
SHADOW_SKIP_FLAG_OFF = "flag_off"
SHADOW_SKIP_MEMORY_ASSIST_REQUIRED = "memory_assist_required"
SHADOW_SKIP_REASONING_DISABLED = "reasoning_disabled"
SHADOW_SKIP_CACHE_NAMESPACE_V2_REQUIRED = "cache_namespace_v2_required"
SHADOW_SKIP_CACHE_HIT = "cache_hit"

# Authoritative divergence codes — single source of truth
DIVERGENCE_CANONICAL_ALIGNED = "canonical_aligned"
DIVERGENCE_PARTIAL_OVERLAP = "partial_overlap"
DIVERGENCE_NO_OVERLAP = "no_overlap"
DIVERGENCE_MEMORY_SOURCE_MISSING_FROM_CONTEXT = "memory_source_missing_from_context"
DIVERGENCE_MEMORY_SUPPORT_MISSING_FROM_CONTEXT = "memory_support_missing_from_context"
DIVERGENCE_RETRIEVAL_SOURCE_NOT_IN_MEMORY = "retrieval_source_not_in_memory"
DIVERGENCE_MEMORY_ONLY_SOURCE_OBSERVED = "memory_only_source_observed"
DIVERGENCE_TOPIC_HINT_ALIGNED = "topic_hint_aligned"
DIVERGENCE_TOPIC_HINT_NOT_REFLECTED = "topic_hint_not_reflected"
DIVERGENCE_PAGE_ROLE_HINT_ALIGNED = "page_role_hint_aligned"
DIVERGENCE_PAGE_ROLE_HINT_NOT_REFLECTED = "page_role_hint_not_reflected"
DIVERGENCE_MEMORY_EMPTY = "memory_empty"
DIVERGENCE_MEMORY_SPARSE = "memory_sparse"
DIVERGENCE_CORPUS_UNCONFIGURED = "corpus_scope_unconfigured"
DIVERGENCE_COMPARISON_NOT_POSSIBLE = "comparison_not_possible"
DIVERGENCE_MEMORY_ASSIST_NOT_USABLE = "memory_assist_not_usable"
DIVERGENCE_SHADOW_COMPARISON_FAILED = "shadow_comparison_failed"

ALL_SHADOW_DIVERGENCE_CODES = frozenset(
    {
        DIVERGENCE_CANONICAL_ALIGNED,
        DIVERGENCE_PARTIAL_OVERLAP,
        DIVERGENCE_NO_OVERLAP,
        DIVERGENCE_MEMORY_SOURCE_MISSING_FROM_CONTEXT,
        DIVERGENCE_MEMORY_SUPPORT_MISSING_FROM_CONTEXT,
        DIVERGENCE_RETRIEVAL_SOURCE_NOT_IN_MEMORY,
        DIVERGENCE_MEMORY_ONLY_SOURCE_OBSERVED,
        DIVERGENCE_TOPIC_HINT_ALIGNED,
        DIVERGENCE_TOPIC_HINT_NOT_REFLECTED,
        DIVERGENCE_PAGE_ROLE_HINT_ALIGNED,
        DIVERGENCE_PAGE_ROLE_HINT_NOT_REFLECTED,
        DIVERGENCE_MEMORY_EMPTY,
        DIVERGENCE_MEMORY_SPARSE,
        DIVERGENCE_CORPUS_UNCONFIGURED,
        DIVERGENCE_COMPARISON_NOT_POSSIBLE,
        DIVERGENCE_MEMORY_ASSIST_NOT_USABLE,
        DIVERGENCE_SHADOW_COMPARISON_FAILED,
    }
)

LIMITATION_SPARSE_MEMORY_EXPECTED = "sparse_memory_expected"

_DEBUG_ID_CAP = 20


@dataclass(frozen=True)
class MemoryCanonicalShadowInput:
    """Immutable comparison inputs — IDs and flags only."""

    memory_anchor_source_ids: tuple[int, ...]
    support_source_ids: tuple[int, ...]
    support_observation_ref_ids: tuple[int, ...]
    dfp_selected_source_ids: tuple[int, ...]
    context_source_ids: tuple[int, ...]
    topic_hints: tuple[str, ...]
    page_role_hints: tuple[str, ...]
    selected_document_types: frozenset[str]
    selected_page_roles: frozenset[str]
    matched_topic_key: str | None
    query_intent: str | None
    answer_strategy: str | None
    broad_injected: bool
    canonical_selection_enabled: bool
    memory_assist_path: str
    memory_assist_usable: bool
    memory_sparse: bool
    memory_empty: bool
    corpus_unconfigured: bool


@dataclass(frozen=True)
class MemoryCanonicalShadowResult:
    """Diagnostic-only shadow comparison outcome."""

    attempted: bool
    path: MemoryCanonicalShadowPath
    memory_anchor_source_ids: tuple[int, ...]
    dfp_selected_source_ids: tuple[int, ...]
    context_source_ids: tuple[int, ...]
    overlap_source_ids: tuple[int, ...]
    memory_only_source_ids: tuple[int, ...]
    retrieval_only_source_ids: tuple[int, ...]
    support_observation_count: int
    support_source_ids: tuple[int, ...]
    support_missing_from_context_count: int
    topic_hint_match: bool | None
    page_role_hint_match: bool | None
    canonical_alignment: CanonicalAlignment
    divergence_codes: tuple[str, ...]
    limitations: tuple[str, ...]
    skipped_reason: str | None = None
    comparison_duration_ms: int | None = None
    memory_version: int | None = None

    @staticmethod
    def off(*, skipped_reason: str = SHADOW_SKIP_FLAG_OFF) -> MemoryCanonicalShadowResult:
        return MemoryCanonicalShadowResult(
            attempted=False,
            path="off",
            memory_anchor_source_ids=(),
            dfp_selected_source_ids=(),
            context_source_ids=(),
            overlap_source_ids=(),
            memory_only_source_ids=(),
            retrieval_only_source_ids=(),
            support_observation_count=0,
            support_source_ids=(),
            support_missing_from_context_count=0,
            topic_hint_match=None,
            page_role_hint_match=None,
            canonical_alignment="not_evaluable",
            divergence_codes=(),
            limitations=(),
            skipped_reason=skipped_reason,
        )

    @staticmethod
    def skipped(reason: str) -> MemoryCanonicalShadowResult:
        return MemoryCanonicalShadowResult(
            attempted=False,
            path="skipped",
            memory_anchor_source_ids=(),
            dfp_selected_source_ids=(),
            context_source_ids=(),
            overlap_source_ids=(),
            memory_only_source_ids=(),
            retrieval_only_source_ids=(),
            support_observation_count=0,
            support_source_ids=(),
            support_missing_from_context_count=0,
            topic_hint_match=None,
            page_role_hint_match=None,
            canonical_alignment="not_evaluable",
            divergence_codes=(DIVERGENCE_COMPARISON_NOT_POSSIBLE,),
            limitations=(),
            skipped_reason=reason,
        )

    def to_diagnostics(self) -> dict[str, Any]:
        return {
            "memory_canonical_shadow_path": self.path,
            "overlap_count": len(self.overlap_source_ids),
            "memory_only_count": len(self.memory_only_source_ids),
            "retrieval_only_count": len(self.retrieval_only_source_ids),
            "context_overlap_count": len(self.overlap_source_ids),
            "support_observation_count": self.support_observation_count,
            "support_missing_from_context_count": self.support_missing_from_context_count,
            "topic_hint_match": self.topic_hint_match,
            "page_role_hint_match": self.page_role_hint_match,
            "canonical_alignment": self.canonical_alignment,
            "divergence_codes": list(self.divergence_codes),
            "limitations": list(self.limitations),
            "memory_canonical_shadow_skipped_reason": self.skipped_reason,
            "comparison_duration_ms": self.comparison_duration_ms,
            "memory_version": self.memory_version,
            "memory_anchor_source_ids": list(
                self.memory_anchor_source_ids[:_DEBUG_ID_CAP]
            ),
            "context_source_ids": list(self.context_source_ids[:_DEBUG_ID_CAP]),
            "overlap_source_ids": list(self.overlap_source_ids[:_DEBUG_ID_CAP]),
            "memory_only_source_ids": list(
                self.memory_only_source_ids[:_DEBUG_ID_CAP]
            ),
            "retrieval_only_source_ids": list(
                self.retrieval_only_source_ids[:_DEBUG_ID_CAP]
            ),
            "dfp_selected_source_ids": list(
                self.dfp_selected_source_ids[:_DEBUG_ID_CAP]
            ),
            "support_source_ids": list(self.support_source_ids[:_DEBUG_ID_CAP]),
        }
