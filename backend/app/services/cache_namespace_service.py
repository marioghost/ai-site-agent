"""Build retrieval/answer cache namespace fingerprints for safe invalidation."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.services.feature_flags import cache_namespace_v2_enabled
from app.services.memory_version_service import MemoryVersionService
from app.services.source_intelligence_constants import (
    CONTEXT_BUILDER_VERSION,
    PROMPT_TEMPLATE_VERSION,
    SOURCE_INTELLIGENCE_VERSION,
)
from app.utils.hashing import sha256_hex
RETRIEVAL_EMPTY_TTL_SECONDS = 60
RETRIEVAL_ERROR_TTL_SECONDS = 30
ANSWER_FALLBACK_TTL_SECONDS = 120


def _profile_rules_hash(profile_json: str) -> dict[str, str]:
    try:
        data = json.loads(profile_json or "{}")
    except json.JSONDecodeError:
        data = {}
    doc_rules = data.get("document_type_rules") or []
    hint_rules = data.get("content_hint_rules") or []
    priority_rules = data.get("source_priority_rules") or []
    expansion_rules = data.get("query_expansion_rules") or []
    intents = data.get("intents") or []
    return {
        "document_type_rules_version": sha256_hex(
            json.dumps(doc_rules, sort_keys=True, ensure_ascii=False)
        ),
        "content_hint_rules_version": sha256_hex(
            json.dumps(hint_rules, sort_keys=True, ensure_ascii=False)
        ),
        "source_priority_rules_version": sha256_hex(
            json.dumps(priority_rules, sort_keys=True, ensure_ascii=False)
        ),
        "query_expansion_version": sha256_hex(
            json.dumps(
                {
                    "rules": expansion_rules,
                    "intents": intents,
                    "topics": data.get("important_topics") or [],
                },
                sort_keys=True,
                ensure_ascii=False,
            )
        ),
    }


def build_retrieval_namespace(settings: Settings, *, db: Session | None = None) -> dict[str, str]:
    profile_json = getattr(settings, "knowledge_profile_json", None) or ""
    rule_hashes = _profile_rules_hash(profile_json)
    retrieval_settings = {
        "top_k": settings.top_k,
        "similarity_threshold": settings.similarity_threshold,
        "retrieval_mode": settings.retrieval_mode or "hybrid",
        "enable_query_expansion": bool(settings.enable_query_expansion),
        "enable_reranking": bool(settings.enable_reranking),
        "enable_intent_aware_retrieval": bool(settings.enable_intent_aware_retrieval),
        "enable_canonical_source_selection": bool(settings.enable_canonical_source_selection),
        "enable_broad_question_mode": bool(getattr(settings, "enable_broad_question_mode", True)),
        "enable_context_builder": bool(getattr(settings, "enable_context_builder", True)),
        "retrieval_candidate_count": getattr(settings, "retrieval_candidate_count", 30),
        "max_pages_in_context": getattr(settings, "max_pages_in_context", 3),
        "max_chunks_per_page": getattr(settings, "max_chunks_per_page", 2),
        "max_sources_in_prompt": getattr(settings, "max_sources_in_prompt", 3),
        "max_chars_per_source": getattr(settings, "max_chars_per_source", 1200),
        "max_total_context_chars": getattr(settings, "max_total_context_chars", 5000),
        "enable_source_intelligence": bool(getattr(settings, "enable_source_intelligence", True)),
        "llm_num_predict": getattr(settings, "llm_num_predict", 512),
        "polish_mode": getattr(settings, "polish_mode", "off"),
        "homepage_boost_enabled": bool(settings.homepage_boost_enabled),
        "homepage_boost_value": settings.homepage_boost_value,
        "title_match_boost": settings.title_match_boost,
        "heading_match_boost": settings.heading_match_boost,
        "short_query_lexical_boost": settings.short_query_lexical_boost,
    }
    namespace = {
        "index_version": str(settings.knowledge_version or 1),
        "knowledge_profile_version": sha256_hex(profile_json),
        "retrieval_settings_version": sha256_hex(
            json.dumps(retrieval_settings, sort_keys=True)
        ),
        "embedding_model": settings.embedding_model or "",
        "collection_name": settings.qdrant_collection or "",
        "source_intelligence_version": SOURCE_INTELLIGENCE_VERSION,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "context_builder_version": CONTEXT_BUILDER_VERSION,
        "llm_model": settings.llm_model or "",
        **rule_hashes,
    }
    if cache_namespace_v2_enabled(settings):
        if db is None:
            raise ValueError(
                "db session is required when cache_namespace_v2_enabled is True"
            )
        namespace["memory_version"] = str(MemoryVersionService(db).get())
    return namespace


def namespace_hash(namespace: dict[str, str]) -> str:
    return sha256_hex(json.dumps(namespace, sort_keys=True))
