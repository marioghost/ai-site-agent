"""Source Intelligence Layer constants (domain-agnostic)."""

SOURCE_INTELLIGENCE_VERSION = "source-intelligence-v2"
PROMPT_TEMPLATE_VERSION = "prompt-v7"
CONTEXT_BUILDER_VERSION = "context-v4"

# Generic document types (no domain-specific types in core code).
GENERIC_DOCUMENT_TYPES = frozenset({
    "homepage",
    "about_page",
    "company_page",
    "contact_page",
    "service_page",
    "product_page",
    "category_page",
    "landing_page",
    "faq_page",
    "support_page",
    "documentation_page",
    "knowledge_base_page",
    "pricing_page",
    "legal_page",
    "blog_post",
    "news_page",
    "promotion_page",
    "campaign_page",
    "offer_page",
    "download_page",
    "media_page",
    "generic_page",
    # Legacy aliases from earlier pipeline
    "action_page",
    "blog_page",
    "rates_page",
})

GENERIC_PAGE_ROLES = frozenset({
    "organization_overview",
    "service_overview",
    "product_details",
    "pricing",
    "support",
    "documentation",
    "marketing",
    "campaign",
    "news",
    "contact",
    "faq",
    "download",
    "legal",
    "generic",
    "employee_story",
    "hr",
    "recruitment",
})

# document_type -> default page_role
DOCUMENT_TYPE_TO_ROLE: dict[str, str] = {
    "homepage": "organization_overview",
    "about_page": "organization_overview",
    "company_page": "organization_overview",
    "contact_page": "contact",
    "service_page": "service_overview",
    "product_page": "product_details",
    "category_page": "service_overview",
    "landing_page": "marketing",
    "faq_page": "faq",
    "support_page": "support",
    "documentation_page": "documentation",
    "knowledge_base_page": "documentation",
    "pricing_page": "pricing",
    "legal_page": "legal",
    "blog_post": "news",
    "news_page": "news",
    "promotion_page": "campaign",
    "campaign_page": "campaign",
    "offer_page": "campaign",
    "action_page": "campaign",
    "download_page": "download",
    "media_page": "marketing",
    "generic_page": "generic",
}

# document_type -> canonical candidacy
CANONICAL_DOCUMENT_TYPES = frozenset({
    "homepage",
    "about_page",
    "company_page",
    "contact_page",
    "service_page",
    "documentation_page",
    "knowledge_base_page",
    "pricing_page",
    "faq_page",
})

# Re-export from single taxonomy owner (rag_planning.intent_taxonomy).
from app.services.rag_planning.intent_taxonomy import (
    INCIDENTAL_DOCUMENT_TYPES as LOW_OVERVIEW_DOCUMENT_TYPES,
    INCIDENTAL_PAGE_ROLES as LOW_OVERVIEW_PAGE_ROLES,
)

# Rule-based summary templates (no domain terms)
SUMMARY_TEMPLATES: dict[str, str] = {
    "organization_overview": "This page describes the organization and its main activity.",
    "service_overview": "This page describes services or product categories offered.",
    "product_details": "This page describes a specific product or service offering.",
    "pricing": "This page contains pricing or tariff information.",
    "support": "This page provides support or help information.",
    "documentation": "This page contains documentation or knowledge-base content.",
    "marketing": "This page is a marketing or landing page.",
    "campaign": "This page describes a temporary promotional campaign or offer.",
    "news": "This page contains news or blog content.",
    "contact": "This page contains contact information.",
    "faq": "This page contains frequently asked questions.",
    "download": "This page offers downloadable resources.",
    "legal": "This page contains legal or policy information.",
    "generic": "This page contains general site content.",
}
