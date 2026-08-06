"""Single intent taxonomy — all modules import from here."""
from __future__ import annotations

OVERVIEW_INTENTS: frozenset[str] = frozenset({
    "entity_overview",
    "site_overview",
    "organization_overview",
    "topic_overview",
    "category_overview",
})

CONTACT_INTENTS: frozenset[str] = frozenset({"contacts_query", "contact"})
NEWS_INTENTS: frozenset[str] = frozenset({"news_query"})
FAQ_INTENTS: frozenset[str] = frozenset({"faq_like", "support", "support_query"})
POLICY_INTENTS: frozenset[str] = frozenset({"legal", "documentation", "policy"})
PRODUCT_INTENTS: frozenset[str] = frozenset({"topic_overview", "category_overview", "product_query", "listing"})
SUPPORT_INTENTS: frozenset[str] = frozenset({"faq_like", "support_query", "support", "faq", "troubleshooting"})
LISTING_INTENTS: frozenset[str] = frozenset({
    "listing",
    "product_query",
    "category_overview",
})
COMPARISON_MARKERS: frozenset[str] = frozenset({"comparison"})

GENERIC_PAGE_ROLES: frozenset[str] = frozenset({
    "organization_overview",
    "service_overview",
    "product_details",
    "documentation",
    "faq",
    "support",
    "contact",
    "news",
    "campaign",
    "marketing",
    "legal",
    "pricing",
    "generic",
})

OVERVIEW_PAGE_ROLES: frozenset[str] = frozenset({"organization_overview", "service_overview"})
DOCUMENTATION_PAGE_ROLES: frozenset[str] = frozenset({"documentation", "faq", "support"})
CONTACT_PAGE_ROLES: frozenset[str] = frozenset({"contact"})
NEWS_PAGE_ROLES: frozenset[str] = frozenset({"news", "campaign", "marketing"})

INCIDENTAL_PAGE_ROLES: frozenset[str] = frozenset({
    "campaign",
    "marketing",
    "news",
    "employee_story",
    "hr",
    "recruitment",
})

INCIDENTAL_DOCUMENT_TYPES: frozenset[str] = frozenset({
    "promotion_page",
    "campaign_page",
    "offer_page",
    "action_page",
    "news_page",
    "blog_post",
    "blog_page",
})

OVERVIEW_DOCUMENT_TYPES: frozenset[str] = frozenset({
    "about_page",
    "company_page",
    "homepage",
})


def is_overview_intent(intent: str) -> bool:
    return (intent or "").lower() in OVERVIEW_INTENTS


def is_broad_overview(intent: str, answer_type: str) -> bool:
    return is_overview_intent(intent) or answer_type == "overview"
