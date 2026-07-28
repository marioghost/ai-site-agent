"""Diagnostic-only Memory vs retrieval shadow comparator (RFC-100 Step 048)."""
from __future__ import annotations

import logging
import time

from app.models.settings import Settings
from app.services.feature_flags import (
    cache_namespace_v2_enabled,
    memory_canonical_shadow_enabled,
    memory_evidence_assist_enabled,
    reasoning_service_enabled,
)
from app.services.reasoning.memory_assist_types import MemoryAssistResult
from app.services.reasoning.memory_canonical_shadow_input_builder import (
    build_memory_canonical_shadow_input,
)
from app.services.reasoning.memory_canonical_shadow_types import (
    DIVERGENCE_CANONICAL_ALIGNED,
    DIVERGENCE_CORPUS_UNCONFIGURED,
    DIVERGENCE_MEMORY_ASSIST_NOT_USABLE,
    DIVERGENCE_MEMORY_EMPTY,
    DIVERGENCE_MEMORY_ONLY_SOURCE_OBSERVED,
    DIVERGENCE_MEMORY_SOURCE_MISSING_FROM_CONTEXT,
    DIVERGENCE_MEMORY_SPARSE,
    DIVERGENCE_MEMORY_SUPPORT_MISSING_FROM_CONTEXT,
    DIVERGENCE_NO_OVERLAP,
    DIVERGENCE_PAGE_ROLE_HINT_ALIGNED,
    DIVERGENCE_PAGE_ROLE_HINT_NOT_REFLECTED,
    DIVERGENCE_PARTIAL_OVERLAP,
    DIVERGENCE_RETRIEVAL_SOURCE_NOT_IN_MEMORY,
    DIVERGENCE_SHADOW_COMPARISON_FAILED,
    DIVERGENCE_TOPIC_HINT_ALIGNED,
    DIVERGENCE_TOPIC_HINT_NOT_REFLECTED,
    LIMITATION_SPARSE_MEMORY_EXPECTED,
    SHADOW_SKIP_CACHE_NAMESPACE_V2_REQUIRED,
    SHADOW_SKIP_FLAG_OFF,
    SHADOW_SKIP_MEMORY_ASSIST_REQUIRED,
    SHADOW_SKIP_REASONING_DISABLED,
    MemoryCanonicalShadowInput,
    MemoryCanonicalShadowResult,
)
from app.services.retrieval_engine.pipeline import DocumentRetrievalResult
from app.services.retrieval_pipeline_service import PipelineResult, PreparedRetrieval

logger = logging.getLogger(__name__)


def _dedupe_codes(codes: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(codes))


class MemoryCanonicalShadowComparator:
    """Set-compare DTOs only — no retrieval, Memory reads, or ranking."""

    def compare_pipeline(
        self,
        settings: Settings,
        memory_assist: MemoryAssistResult,
        prepared: PreparedRetrieval,
        doc_result: DocumentRetrievalResult,
        pipe_result: PipelineResult,
    ) -> MemoryCanonicalShadowResult:
        if not memory_canonical_shadow_enabled(settings):
            return MemoryCanonicalShadowResult.off()
        if not reasoning_service_enabled():
            return MemoryCanonicalShadowResult.skipped(SHADOW_SKIP_REASONING_DISABLED)
        if not memory_evidence_assist_enabled(settings):
            return MemoryCanonicalShadowResult.skipped(SHADOW_SKIP_MEMORY_ASSIST_REQUIRED)
        if not cache_namespace_v2_enabled(settings):
            return MemoryCanonicalShadowResult.skipped(
                SHADOW_SKIP_CACHE_NAMESPACE_V2_REQUIRED
            )

        started = time.perf_counter()
        try:
            shadow_input = build_memory_canonical_shadow_input(
                memory_assist=memory_assist,
                prepared=prepared,
                doc_result=doc_result,
                pipe_result=pipe_result,
                settings=settings,
            )
            return self._compare(shadow_input, memory_assist.memory_version, started)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.warning(
                "memory_canonical_shadow_failed error_type=%s duration_ms=%s",
                type(exc).__name__,
                duration_ms,
            )
            return MemoryCanonicalShadowResult(
                attempted=True,
                path="failed",
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
                divergence_codes=(DIVERGENCE_SHADOW_COMPARISON_FAILED,),
                limitations=(),
                comparison_duration_ms=duration_ms,
                memory_version=memory_assist.memory_version,
            )

    def _compare(
        self,
        inp: MemoryCanonicalShadowInput,
        memory_version: int | None,
        started: float,
    ) -> MemoryCanonicalShadowResult:
        duration_ms = int((time.perf_counter() - started) * 1000)
        limitations: list[str] = []
        codes: list[str] = []

        if inp.corpus_unconfigured:
            return MemoryCanonicalShadowResult(
                attempted=True,
                path="empty_memory",
                memory_anchor_source_ids=(),
                dfp_selected_source_ids=inp.dfp_selected_source_ids,
                context_source_ids=inp.context_source_ids,
                overlap_source_ids=(),
                memory_only_source_ids=(),
                retrieval_only_source_ids=inp.context_source_ids,
                support_observation_count=0,
                support_source_ids=(),
                support_missing_from_context_count=0,
                topic_hint_match=None,
                page_role_hint_match=None,
                canonical_alignment="not_evaluable",
                divergence_codes=(DIVERGENCE_CORPUS_UNCONFIGURED, DIVERGENCE_MEMORY_EMPTY),
                limitations=limitations,
                comparison_duration_ms=duration_ms,
                memory_version=memory_version,
            )

        if inp.memory_empty or inp.memory_assist_path == "empty":
            codes.append(DIVERGENCE_MEMORY_EMPTY)
            return MemoryCanonicalShadowResult(
                attempted=True,
                path="empty_memory",
                memory_anchor_source_ids=(),
                dfp_selected_source_ids=inp.dfp_selected_source_ids,
                context_source_ids=inp.context_source_ids,
                overlap_source_ids=(),
                memory_only_source_ids=(),
                retrieval_only_source_ids=inp.context_source_ids,
                support_observation_count=len(inp.support_observation_ref_ids),
                support_source_ids=(),
                support_missing_from_context_count=0,
                topic_hint_match=None,
                page_role_hint_match=None,
                canonical_alignment="not_evaluable",
                divergence_codes=_dedupe_codes(codes),
                limitations=limitations,
                comparison_duration_ms=duration_ms,
                memory_version=memory_version,
            )

        if inp.memory_sparse:
            codes.append(DIVERGENCE_MEMORY_SPARSE)
            limitations.append(LIMITATION_SPARSE_MEMORY_EXPECTED)

        memory_set = set(inp.memory_anchor_source_ids)
        context_set = set(inp.context_source_ids)
        overlap = memory_set & context_set
        memory_only = memory_set - context_set
        retrieval_only = context_set - memory_set

        overlap_ids = tuple(sorted(overlap))
        memory_only_ids = tuple(sorted(memory_only))
        retrieval_only_ids = tuple(sorted(retrieval_only))

        if memory_only_ids:
            codes.append(DIVERGENCE_MEMORY_ONLY_SOURCE_OBSERVED)
            codes.append(DIVERGENCE_MEMORY_SOURCE_MISSING_FROM_CONTEXT)

        if retrieval_only_ids:
            codes.append(DIVERGENCE_RETRIEVAL_SOURCE_NOT_IN_MEMORY)
            limitations.append(LIMITATION_SPARSE_MEMORY_EXPECTED)

        support_set = set(inp.support_source_ids)
        support_missing = len(support_set - context_set)
        if support_missing > 0 and inp.memory_assist_usable:
            codes.append(DIVERGENCE_MEMORY_SUPPORT_MISSING_FROM_CONTEXT)
        elif not inp.memory_assist_usable and inp.support_observation_ref_ids:
            codes.append(DIVERGENCE_MEMORY_ASSIST_NOT_USABLE)

        topic_match = _topic_hint_match(inp)
        page_role_match = _page_role_hint_match(inp)
        if topic_match is True:
            codes.append(DIVERGENCE_TOPIC_HINT_ALIGNED)
        elif topic_match is False:
            codes.append(DIVERGENCE_TOPIC_HINT_NOT_REFLECTED)
        if page_role_match is True:
            codes.append(DIVERGENCE_PAGE_ROLE_HINT_ALIGNED)
        elif page_role_match is False:
            codes.append(DIVERGENCE_PAGE_ROLE_HINT_NOT_REFLECTED)

        alignment = _canonical_alignment(memory_set, context_set, overlap)
        if alignment == "aligned":
            codes.append(DIVERGENCE_CANONICAL_ALIGNED)
        elif alignment == "partial":
            codes.append(DIVERGENCE_PARTIAL_OVERLAP)
        elif alignment == "divergent":
            codes.append(DIVERGENCE_NO_OVERLAP)

        return MemoryCanonicalShadowResult(
            attempted=True,
            path="compared",
            memory_anchor_source_ids=inp.memory_anchor_source_ids,
            dfp_selected_source_ids=inp.dfp_selected_source_ids,
            context_source_ids=inp.context_source_ids,
            overlap_source_ids=overlap_ids,
            memory_only_source_ids=memory_only_ids,
            retrieval_only_source_ids=retrieval_only_ids,
            support_observation_count=len(inp.support_observation_ref_ids),
            support_source_ids=inp.support_source_ids,
            support_missing_from_context_count=support_missing,
            topic_hint_match=topic_match,
            page_role_hint_match=page_role_match,
            canonical_alignment=alignment,
            divergence_codes=_dedupe_codes(codes),
            limitations=tuple(dict.fromkeys(limitations)),
            comparison_duration_ms=duration_ms,
            memory_version=memory_version,
        )


def _canonical_alignment(
    memory_set: set[int],
    context_set: set[int],
    overlap: set[int],
) -> str:
    if not memory_set or not context_set:
        return "not_evaluable"
    if memory_set <= context_set:
        return "aligned"
    if overlap:
        return "partial"
    return "divergent"


def _topic_hint_match(inp: MemoryCanonicalShadowInput) -> bool | None:
    if not inp.topic_hints and not inp.matched_topic_key:
        return None
    hints = set(inp.topic_hints)
    if inp.matched_topic_key:
        hints.add(inp.matched_topic_key)
    if not hints:
        return None
    for hint in hints:
        if hint in inp.selected_document_types or hint in inp.selected_page_roles:
            return True
        if inp.matched_topic_key and inp.matched_topic_key == hint:
            return True
    return False if hints else None


def _page_role_hint_match(inp: MemoryCanonicalShadowInput) -> bool | None:
    if not inp.page_role_hints:
        return None
    for hint in inp.page_role_hints:
        if hint in inp.selected_page_roles or hint in inp.selected_document_types:
            return True
    return False
