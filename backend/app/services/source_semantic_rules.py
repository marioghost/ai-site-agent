"""Rule-based semantic profile fallback (domain-agnostic)."""
from __future__ import annotations

from app.models.source import Source
from app.schemas.source_intelligence import SourceSemanticProfile

_ROLE_TO_PURPOSE: dict[str, str] = {
    "organization_overview": "about company",
    "service_overview": "service description",
    "product_details": "product details",
    "pricing": "pricing",
    "support": "support",
    "documentation": "documentation",
    "marketing": "landing page",
    "campaign": "promotion",
    "news": "news",
    "contact": "contact information",
    "faq": "faq",
    "download": "documentation",
    "legal": "legal information",
    "generic": "general information",
}

_DOC_TYPE_TO_ENTITY: dict[str, str] = {
    "product_page": "product",
    "service_page": "service",
    "category_page": "category",
    "faq_page": "faq",
    "legal_page": "policy",
    "contact_page": "branch",
    "about_page": "organization",
    "company_page": "organization",
    "homepage": "organization",
    "news_page": "article",
    "blog_post": "article",
    "promotion_page": "promotion",
    "campaign_page": "promotion",
    "documentation_page": "document",
    "knowledge_base_page": "document",
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
    "campaign": ["listing"],
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


def build_rules_semantic(
    source: Source,
    *,
    page_role: str,
    document_type: str,
    keywords: list[str],
    site_section: str,
) -> SourceSemanticProfile:
    purpose = _ROLE_TO_PURPOSE.get(page_role, "general information")
    entity = _DOC_TYPE_TO_ENTITY.get(document_type, "document")
    main_topic = site_section.replace("-", " ").replace("_", " ").title() if site_section else ""
    if not main_topic and source.title:
        main_topic = source.title[:80]

    suitable: list[str] = []
    not_suitable = list(_ROLE_NOT_SUITABLE.get(page_role, []))
    if page_role == "product_details":
        suitable = ["list available products", "product details", "product requirements"]
    elif page_role == "legal":
        suitable = ["legal terms", "regulatory information", "policy details"]
        not_suitable.extend(["product listing", "product comparison"])
    elif page_role == "organization_overview":
        suitable = ["company overview", "about the organization"]
    elif page_role == "faq":
        suitable = ["common questions", "how-to answers"]

    conf = 0.45
    if source.main_content_chars and source.main_content_chars >= 400:
        conf += 0.15
    if source.title:
        conf += 0.05

    return SourceSemanticProfile(
        main_topic=main_topic,
        main_topic_confidence=min(0.85, conf),
        subtopics=keywords[:6],
        document_purpose=purpose,
        document_purpose_confidence=min(0.8, conf + 0.1),
        entity_type=entity,
        entity_type_confidence=min(0.75, conf),
        supported_intents=_ROLE_TO_INTENTS.get(page_role, ["overview"]),
        search_keywords=keywords[:16],
        synonyms=keywords[:8],
        semantic_tags=[page_role.replace("_", "-"), document_type.replace("_", "-")][:6],
        suitable_for=suitable[:8],
        not_suitable_for=not_suitable[:8],
        confidence=round(min(0.75, conf), 3),
        generator="rules",
    )
