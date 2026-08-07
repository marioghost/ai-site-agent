"""Rule-based semantic profile fallback (domain-agnostic)."""
from __future__ import annotations

import re

from app.models.source import Source
from app.schemas.source_intelligence import SourceSemanticProfile
from app.services.rag_planning.purpose_catalog import purpose_from_metadata

_DOC_TYPE_TO_ENTITY: dict[str, str] = {
    "product_page": "product",
    "service_page": "service",
    "category_page": "category",
    "faq_page": "faq",
    "legal_page": "policy",
    "contact_page": "organization",
    "about_page": "organization",
    "company_page": "organization",
    "homepage": "organization",
    "news_page": "article",
    "blog_post": "article",
    "blog_page": "article",
    "promotion_page": "promotion",
    "campaign_page": "promotion",
    "documentation_page": "document",
    "knowledge_base_page": "document",
    "support_page": "document",
    "pricing_page": "product",
}

_ROLE_TO_INTENTS: dict[str, list[str]] = {
    "organization_overview": ["overview", "entity_overview"],
    "service_overview": ["overview", "listing", "topic_overview"],
    "product_details": ["listing", "specific_fact", "product_query", "pricing"],
    "pricing": ["pricing", "comparison"],
    "support": ["support", "troubleshooting", "faq"],
    "documentation": ["documentation", "specific_fact"],
    "faq": ["faq", "faq_like", "support"],
    "contact": ["contacts", "contacts_query"],
    "legal": ["legal", "documentation"],
    "campaign": ["listing", "promotion"],
    "marketing": ["overview"],
    "news": ["news_query"],
    "generic": ["overview", "specific_fact"],
}

_ROLE_NOT_SUITABLE: dict[str, list[str]] = {
    "product_details": ["company overview", "branch search", "legal disputes"],
    "legal": ["product listing", "product comparison", "pricing quotes"],
    "campaign": ["legal information", "detailed product specs"],
    "news": ["product requirements", "pricing", "contact details"],
    "contact": ["product comparison", "legal policy details"],
    "organization_overview": ["specific product pricing", "troubleshooting steps"],
    "faq": ["company history overview"],
}

_LANG_SEGMENTS = frozenset(
    {
        "en",
        "uk",
        "ua",
        "ru",
        "de",
        "fr",
        "es",
        "pl",
        "it",
        "pt",
        "en-us",
        "uk-ua",
        "ru-ru",
    }
)

_NOISE_TOPIC = frozenset(
    {
        "page",
        "index",
        "home",
        "default",
        "null",
        "www",
        "html",
        "php",
        "asp",
    }
)


def _clean_title_topic(title: str) -> str:
    raw = (title or "").strip()
    if not raw:
        return ""
    parts = re.split(r"\s+[|\u2014\u2013\-]\s+", raw, maxsplit=1)
    head = parts[0].strip() if parts else raw
    return head[:80]


def _topic_from_section(site_section: str) -> str:
    seg = (site_section or "").strip().lower()
    if not seg or seg in _LANG_SEGMENTS or seg in _NOISE_TOPIC or seg == "general":
        return ""
    if len(seg) <= 2:
        return ""
    return seg.replace("-", " ").replace("_", " ").title()


def build_rules_semantic(
    source: Source,
    *,
    page_role: str,
    document_type: str,
    keywords: list[str],
    site_section: str,
) -> SourceSemanticProfile:
    # Single purpose owner: purpose_catalog (not a local role map).
    purpose = purpose_from_metadata(page_role=page_role, document_type=document_type)
    entity = _DOC_TYPE_TO_ENTITY.get(document_type, "document")

    title_topic = _clean_title_topic(source.title or "")
    section_topic = _topic_from_section(site_section)
    # Prefer human title over URL slug (especially language prefixes).
    main_topic = title_topic or section_topic
    if not main_topic and keywords:
        main_topic = " ".join(keywords[:3]).title()

    suitable: list[str] = []
    not_suitable = list(_ROLE_NOT_SUITABLE.get(page_role, []))
    if page_role == "product_details":
        suitable = ["list available products", "product details", "product requirements"]
    elif page_role == "legal":
        suitable = ["legal terms", "regulatory information", "policy details"]
        not_suitable.extend(["product listing", "product comparison"])
    elif page_role == "organization_overview":
        suitable = ["company overview", "about the organization", "organization profile"]
    elif page_role == "faq":
        suitable = ["common questions", "how-to answers"]
    elif page_role == "contact":
        suitable = ["contact details", "address", "phone"]
    elif page_role == "news":
        suitable = ["recent news", "announcements"]

    conf = 0.45
    if source.main_content_chars and source.main_content_chars >= 400:
        conf += 0.15
    if source.title:
        conf += 0.05
    if title_topic:
        conf += 0.05

    subtopics = [k for k in keywords[:8] if k and k.lower() not in _NOISE_TOPIC][:6]

    return SourceSemanticProfile(
        main_topic=main_topic,
        main_topic_confidence=min(0.85, conf),
        subtopics=subtopics,
        document_purpose=purpose,
        document_purpose_confidence=min(0.8, conf + 0.1),
        entity_type=entity,
        entity_type_confidence=min(0.75, conf),
        supported_intents=_ROLE_TO_INTENTS.get(page_role, ["overview"]),
        search_keywords=keywords[:16],
        synonyms=keywords[:8],
        semantic_tags=(subtopics[:4] or [page_role.replace("_", "-")])[:6],
        suitable_for=suitable[:8],
        not_suitable_for=not_suitable[:8],
        confidence=round(min(0.75, conf), 3),
        generator="rules",
    )
