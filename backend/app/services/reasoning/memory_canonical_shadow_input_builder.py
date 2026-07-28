"""Build MemoryCanonicalShadowInput from pipeline DTOs (Step 048)."""
from __future__ import annotations

from app.models.settings import Settings
from app.services.reasoning.memory_assist_types import MemoryAssistResult
from app.services.reasoning.memory_canonical_shadow_types import (
    MemoryCanonicalShadowInput,
)
from app.services.retrieval_engine.pipeline import DocumentRetrievalResult
from app.services.retrieval_pipeline_service import (
    PipelineResult,
    PreparedRetrieval,
)
from app.services.settings_flags import setting_bool


def _unique_source_ids(hits) -> tuple[int, ...]:
    ids = {h.source_id for h in hits if getattr(h, "source_id", None) and h.source_id > 0}
    return tuple(sorted(ids))


def _norm_set(values: tuple[str, ...] | frozenset[str]) -> frozenset[str]:
    return frozenset(v.strip().lower() for v in values if v and str(v).strip())


def _metadata_from_hits(hits) -> tuple[frozenset[str], frozenset[str]]:
    doc_types: set[str] = set()
    page_roles: set[str] = set()
    for hit in hits:
        dt = (getattr(hit, "document_type", None) or "").strip().lower()
        if dt:
            doc_types.add(dt)
        hint = (getattr(hit, "content_type_hint", None) or "").strip().lower()
        if hint:
            page_roles.add(hint)
    return frozenset(doc_types), frozenset(page_roles)


def build_memory_canonical_shadow_input(
    *,
    memory_assist: MemoryAssistResult,
    prepared: PreparedRetrieval,
    doc_result: DocumentRetrievalResult,
    pipe_result: PipelineResult,
    settings: Settings,
) -> MemoryCanonicalShadowInput:
    """Extract ID-only comparison inputs from already-produced pipeline artifacts."""
    context_hits = list(pipe_result.hits or [])
    dfp_hits = list(doc_result.selected_hits or [])
    doc_types, page_roles = _metadata_from_hits(context_hits)
    applied = prepared.applied_config
    diag = prepared.diagnostics

    return MemoryCanonicalShadowInput(
        memory_anchor_source_ids=tuple(sorted(memory_assist.source_ids)),
        support_source_ids=tuple(sorted(memory_assist.support_source_ids)),
        support_observation_ref_ids=tuple(sorted(memory_assist.support_observation_ref_ids)),
        dfp_selected_source_ids=_unique_source_ids(dfp_hits),
        context_source_ids=_unique_source_ids(context_hits),
        topic_hints=tuple(sorted(_norm_set(memory_assist.topic_hints))),
        page_role_hints=tuple(sorted(_norm_set(memory_assist.page_role_hints))),
        selected_document_types=doc_types,
        selected_page_roles=page_roles,
        matched_topic_key=(
            (applied.matched_topic_key or diag.matched_topic_key or "").strip().lower()
            or None
        ),
        query_intent=prepared.intent_result.legacy_intent or None,
        answer_strategy=str(applied.answer_strategy or diag.answer_strategy or "") or None,
        broad_injected=bool(diag.broad_injected),
        canonical_selection_enabled=bool(
            setting_bool(settings, "enable_canonical_source_selection")
        ),
        memory_assist_path=memory_assist.path,
        memory_assist_usable=memory_assist.usable_for_evidence,
        memory_sparse=memory_assist.path == "sparse",
        memory_empty=memory_assist.path in ("empty", "off") or not memory_assist.source_ids,
        corpus_unconfigured=not memory_assist.corpus_scope_configured,
    )
