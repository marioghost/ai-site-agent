"""Build MemoryRegionRequest from PreparedRetrieval (RFC-100 Step 047)."""
from __future__ import annotations

from app.services.epistemic_memory.memory_region_types import (
    DEFAULT_REGION_LIMIT,
    MemoryCorpusScope,
    MemoryIsolationScope,
    MemoryRegionRequest,
)
from app.services.epistemic_memory.provenance_scope import ProvenanceScope
from app.services.retrieval_pipeline_service import PreparedRetrieval

_TOPIC_CONFIDENCE_MIN = 0.75
_PAGE_ROLE_HINTS = frozenset(
    {
        "about",
        "contact",
        "product",
        "service",
        "news",
        "legal",
        "career",
        "faq",
        "homepage",
        "organization",
    }
)


def _reliable_topic_key(prepared: PreparedRetrieval) -> str | None:
    applied = prepared.applied_config
    topic = (applied.matched_topic_key or "").strip().lower()
    if not topic or topic == "unknown":
        return None
    confidence = getattr(prepared.intent_result, "confidence", 0.0) or 0.0
    if confidence < _TOPIC_CONFIDENCE_MIN and not prepared.intent_result.matched_topic:
        return None
    return topic


def _page_role_hints(prepared: PreparedRetrieval) -> tuple[str, ...]:
    hints: set[str] = set()
    for hint in prepared.applied_config.boosted_content_hints or []:
        normalized = (hint or "").strip().lower()
        if normalized in _PAGE_ROLE_HINTS:
            hints.add(normalized)
    legacy = (prepared.intent_result.legacy_intent or "").strip().lower()
    if legacy in _PAGE_ROLE_HINTS:
        hints.add(legacy)
    return tuple(sorted(hints))


def _document_type_hints(prepared: PreparedRetrieval) -> tuple[str, ...]:
    types = [
        (t or "").strip().lower()
        for t in (prepared.applied_config.boosted_document_types or [])
        if (t or "").strip()
    ]
    return tuple(sorted(set(types)))


def build_memory_region_request(prepared: PreparedRetrieval) -> MemoryRegionRequest:
    """Deterministic Memory region request — deployment corpus isolation only."""
    topic_key = _reliable_topic_key(prepared)
    page_roles = _page_role_hints(prepared)
    document_types = _document_type_hints(prepared)
    information_need = (
        prepared.intent_result.legacy_intent
        or prepared.applied_config.detected_intent
        or None
    )
    return MemoryRegionRequest(
        isolation=MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT),
        information_need=information_need,
        topic_key=topic_key,
        language=prepared.query_language or None,
        page_roles=page_roles or None,
        document_types=document_types or None,
        provenance_scope=ProvenanceScope.REAL,
        active_only=True,
        include_superseded=False,
        include_evidence=True,
        limit=DEFAULT_REGION_LIMIT,
        offset=0,
    )
