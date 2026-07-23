"""LLM-based semantic profile generation for indexed sources."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.models.settings import Settings
from app.models.source import Source
from app.schemas.source_intelligence import (
    GENERIC_DOCUMENT_PURPOSES,
    GENERIC_ENTITY_TYPES,
    GENERIC_SUPPORTED_INTENTS,
    SourceSemanticProfile,
)
from app.services.ollama_service import OllamaError, OllamaService
from app.services.source_intelligence_llm_cache_service import (
    SourceIntelligenceLLMCacheService,
)
from app.services.source_intelligence_perf import detect_source_language

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You analyze web pages for a retrieval-augmented generation (RAG) system.
Return ONLY valid JSON matching this schema (no markdown fences):

{
  "main_topic": "short primary topic (2-5 words, domain-neutral)",
  "main_topic_confidence": 0.0-1.0,
  "subtopics": ["up to 8 specific subtopics"],
  "document_purpose": "one of: Product Listing, Product Details, Service Description, Legal Information, Documentation, FAQ, Contact Information, News, Promotion, Landing Page, About Company, Support, Policy, Comparison, Pricing, General Information",
  "document_purpose_confidence": 0.0-1.0,
  "entity_type": "one of: Product, Service, Branch, Person, Organization, Policy, FAQ, Promotion, Document, Article, Category",
  "entity_type_confidence": 0.0-1.0,
  "supported_intents": ["from: overview, listing, comparison, pricing, eligibility, requirements, contacts, support, troubleshooting, legal, documentation, faq, product_query"],
  "search_keywords": ["meaningful content keywords, no nav/menu words"],
  "synonyms": ["semantic synonyms users might use"],
  "semantic_tags": ["short tags like retail, legal, support, faq, promotion"],
  "suitable_for": ["concrete user questions this page SHOULD answer"],
  "not_suitable_for": ["concrete user questions this page should NOT answer"],
  "confidence": 0.0-1.0
}

Rules:
- Infer meaning from content, NOT from shared vocabulary alone.
- Distinguish product/service pages from legal, news, promotional, FAQ, and contact pages.
- suitable_for / not_suitable_for must be specific question types, not page titles.
- Do NOT assume any specific industry; work for any website type.
- Lower confidence when content is thin or ambiguous.
"""


def _normalize_purpose(value: str) -> str:
    v = (value or "").strip().lower()
    if not v:
        return "general information"
    for p in GENERIC_DOCUMENT_PURPOSES:
        if p in v or v in p:
            return p
    return v[:64]


def _normalize_entity(value: str) -> str:
    v = (value or "").strip().lower()
    if not v:
        return "document"
    for e in GENERIC_ENTITY_TYPES:
        if e in v or v == e:
            return e
    return v[:32]


def _clean_list(items: list | None, limit: int = 16) -> list[str]:
    if not items:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        s = str(item).strip()
        if not s or s.lower() in seen:
            continue
        seen.add(s.lower())
        out.append(s[:120])
        if len(out) >= limit:
            break
    return out


def _parse_json_response(raw: str) -> dict | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


class SourceIntelligenceLLMService:
    @staticmethod
    def generate(
        source: Source,
        settings: Settings,
        *,
        document_type: str = "",
        page_role: str = "",
        db=None,
        stats=None,
    ) -> SourceSemanticProfile | None:
        title = source.title or ""
        url = source.url or ""
        main_text = (source.main_content_text or source.extracted_text or "")[:6000]
        if len(main_text.strip()) < 40 and not title.strip():
            return None

        content_hash = source.content_hash or ""
        language = detect_source_language(title, main_text[:800])
        cache_svc = SourceIntelligenceLLMCacheService(db) if db is not None else None
        cache_key = None
        if cache_svc and content_hash:
            cache_key = cache_svc.build_key(
                content_hash=content_hash,
                llm_model=settings.llm_model or "",
                settings=settings,
                language=language,
            )
            cached = cache_svc.get_profile(cache_key)
            if cached is not None:
                if stats is not None:
                    stats.llm_cache_hits += 1
                return cached

        user_payload = {
            "url": url,
            "title": title,
            "document_type_hint": document_type or source.document_type,
            "page_role_hint": page_role or getattr(source, "page_role", ""),
            "content_excerpt": main_text[:5000],
            "site_section": getattr(source, "site_section", "") or "",
        }
        user = json.dumps(user_payload, ensure_ascii=False)

        if stats is not None:
            stats.llm_calls += 1
        try:
            ollama = OllamaService(timeout=float(settings.ollama_generation_timeout_seconds or 90))
            result = ollama.chat(
                settings.llm_model,
                _SYSTEM_PROMPT,
                user,
                temperature=0.1,
                max_tokens=1024,
                num_ctx=4096,
                background=True,
            )
        except OllamaError as exc:
            logger.debug("Source intelligence LLM skipped for %s: %s", url, exc)
            if stats is not None:
                stats.llm_failures += 1
            return None

        data = _parse_json_response(result.content)
        if not data:
            if stats is not None:
                stats.llm_failures += 1
            return None

        intents = [
            i.lower().replace(" ", "_")
            for i in _clean_list(data.get("supported_intents"), 16)
        ]
        intents = [i for i in intents if i in GENERIC_SUPPORTED_INTENTS or len(i) >= 3]

        profile = SourceSemanticProfile(
            main_topic=str(data.get("main_topic") or "")[:128],
            main_topic_confidence=min(1.0, max(0.0, float(data.get("main_topic_confidence") or 0.5))),
            subtopics=_clean_list(data.get("subtopics"), 12),
            document_purpose=_normalize_purpose(str(data.get("document_purpose") or "")),
            document_purpose_confidence=min(
                1.0, max(0.0, float(data.get("document_purpose_confidence") or 0.5))
            ),
            entity_type=_normalize_entity(str(data.get("entity_type") or "")),
            entity_type_confidence=min(
                1.0, max(0.0, float(data.get("entity_type_confidence") or 0.5))
            ),
            supported_intents=intents[:16],
            search_keywords=_clean_list(data.get("search_keywords"), 24),
            synonyms=_clean_list(data.get("synonyms"), 24),
            semantic_tags=_clean_list(data.get("semantic_tags"), 20),
            suitable_for=_clean_list(data.get("suitable_for"), 12),
            not_suitable_for=_clean_list(data.get("not_suitable_for"), 12),
            confidence=min(1.0, max(0.0, float(data.get("confidence") or 0.6))),
            generator="llm",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        if cache_svc and cache_key and content_hash:
            cache_svc.store_success(
                cache_key=cache_key,
                content_hash=content_hash,
                llm_model=settings.llm_model or "",
                settings=settings,
                language=language,
                raw_json=result.content,
                profile=profile,
            )
        return profile
