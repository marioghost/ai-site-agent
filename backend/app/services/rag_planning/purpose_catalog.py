"""Purpose catalog — single mapping owner for document purposes and slots."""
from __future__ import annotations

from app.schemas.source_intelligence import GENERIC_DOCUMENT_PURPOSES
from app.services.rag_planning.intent_taxonomy import DOCUMENTATION_PAGE_ROLES
from app.services.source_intelligence_constants import DOCUMENT_TYPE_TO_ROLE

PURPOSE_TO_SLOT: dict[str, str] = {
    "news": "news_item",
    "promotion": "offer",
    "about company": "identity",
    "contact information": "contact_info",
    "product listing": "options",
    "landing page": "identity",
    "service description": "capabilities",
    "product details": "product_identity",
    "documentation": "documentation",
    "faq": "answer",
    "support": "answer",
    "legal information": "rule",
    "policy": "rule",
    "pricing": "pricing",
}

ROLE_TO_DEFAULT_PURPOSE: dict[str, str] = {
    "organization_overview": "about company",
    "service_overview": "service description",
    "product_details": "product details",
    "news": "news",
    "campaign": "promotion",
    "marketing": "landing page",
    "contact": "contact information",
    "documentation": "documentation",
    "faq": "faq",
    "support": "support",
    "legal": "legal information",
    "pricing": "pricing",
    "generic": "general information",
    "download": "documentation",
}

DOC_TYPE_TO_PURPOSE: dict[str, str] = {
    "news_page": "news",
    "blog_page": "news",
    "blog_post": "news",
    "promotion_page": "promotion",
    "campaign_page": "promotion",
    "offer_page": "promotion",
    "action_page": "promotion",
    "about_page": "about company",
    "company_page": "about company",
    "contact_page": "contact information",
    "documentation_page": "documentation",
    "knowledge_base_page": "documentation",
    "product_page": "product details",
    "service_page": "service description",
    "category_page": "product listing",
    "pricing_page": "pricing",
    "faq_page": "faq",
    "support_page": "support",
    "legal_page": "legal information",
    "homepage": "landing page",
    "landing_page": "landing page",
}

# Inverse for refining page_role from high-confidence purpose (SI only).
PURPOSE_TO_DEFAULT_ROLE: dict[str, str] = {
    "about company": "organization_overview",
    "landing page": "marketing",
    "service description": "service_overview",
    "product details": "product_details",
    "product listing": "service_overview",
    "pricing": "pricing",
    "news": "news",
    "promotion": "campaign",
    "contact information": "contact",
    "documentation": "documentation",
    "faq": "faq",
    "support": "support",
    "legal information": "legal",
    "policy": "legal",
    "general information": "generic",
}

# Chunk content_type_hint → SI purpose vocabulary (evidence/retrieval).
CONTENT_HINT_TO_PURPOSE: dict[str, str] = {
    "about": "about company",
    "overview": "about company",
    "contacts": "contact information",
    "contact": "contact information",
    "faq": "faq",
    "pricing": "pricing",
    "rates": "pricing",
    "products": "product details",
    "product": "product details",
    "docs": "documentation",
    "documentation": "documentation",
    "support": "support",
    "news": "news",
    "schedule": "general information",
    "delivery": "service description",
    "returns": "support",
}


def purpose_from_metadata(*, page_role: str, document_type: str) -> str:
    role = (page_role or "").lower().strip()
    if role and role != "generic" and role in ROLE_TO_DEFAULT_PURPOSE:
        return ROLE_TO_DEFAULT_PURPOSE[role]
    doc = (document_type or "generic_page").lower()
    if doc in DOC_TYPE_TO_PURPOSE:
        return DOC_TYPE_TO_PURPOSE[doc]
    mapped_role = DOCUMENT_TYPE_TO_ROLE.get(doc, "generic")
    return ROLE_TO_DEFAULT_PURPOSE.get(mapped_role, "general information")


def role_from_purpose(purpose: str, *, fallback_role: str = "generic") -> str:
    key = (purpose or "").lower().strip()
    return PURPOSE_TO_DEFAULT_ROLE.get(key, fallback_role or "generic")


def normalize_content_hint_to_purpose(hint: str) -> str:
    h = (hint or "").lower().strip()
    if not h or h == "generic":
        return ""
    return CONTENT_HINT_TO_PURPOSE.get(h, "")


def purposes_to_forbidden_slots(purposes: list[str]) -> tuple[str, ...]:
    out: list[str] = []
    for p in purposes:
        slot = PURPOSE_TO_SLOT.get(p.lower().strip())
        if slot:
            out.append(slot)
    return tuple(dict.fromkeys(out))


def filter_valid_purposes(purposes: list[str]) -> tuple[str, ...]:
    return tuple(p for p in purposes if p in GENERIC_DOCUMENT_PURPOSES)


def infer_knowledge_slots(
    *,
    page_role: str,
    document_type: str,
    source_purpose: str,
    heading: str,
    text: str,
) -> frozenset[str]:
    """Map source metadata + text cues to generic knowledge slots.

    Role alone must not invent full overview coverage — thin about pages would
    otherwise satisfy identity/activity/capabilities without evidence.
    """
    aspects: set[str] = set()
    role = (page_role or "").lower()
    doc = (document_type or "").lower()
    purpose = (source_purpose or purpose_from_metadata(page_role=role, document_type=doc)).lower()
    blob = f"{heading} {text[:600]}".lower()
    org_like = role in {"organization_overview", "service_overview"} or doc in {
        "about_page",
        "company_page",
        "homepage",
    }
    if org_like or purpose in {"about company", "landing page"}:
        # Always allow identity for org/homepage surfaces.
        aspects.add("identity")
        # Activity/capabilities require textual support (or longer body).
        activity_cues = (
            "service",
            "product",
            "offer",
            "provide",
            "activity",
            "mission",
            "we ",
            "our ",
        )
        capability_cues = ("service", "product", "solution", "platform", "capabilit")
        if any(c in blob for c in activity_cues) or len(blob) >= 280:
            aspects.add("activity")
        if any(c in blob for c in capability_cues) or len(blob) >= 400:
            aspects.add("capabilities")
    if purpose in {"service description", "product details", "product listing"}:
        aspects.update({"capabilities", "options", "product_identity", "benefits"})
    if purpose == "pricing":
        aspects.add("pricing")
    if purpose == "news" or role == "news" or doc in {"news_page", "blog_post"}:
        aspects.add("news_item")
        aspects.add("current_item")
    if purpose == "promotion" or role in {"campaign", "marketing"}:
        aspects.add("offer")
        aspects.add("current_item")
    if role in {"hr", "recruitment"}:
        aspects.add("vacancy")
    if role == "contact" or purpose == "contact information" or doc == "contact_page":
        aspects.add("contact_info")
    if role in DOCUMENTATION_PAGE_ROLES or purpose in {
        "documentation",
        "faq",
        "support",
        "legal information",
        "policy",
    }:
        aspects.update({"documentation", "rule", "scope", "conditions"})
    if "step" in blob or "procedure" in blob or "how to" in blob:
        aspects.update({"steps", "prerequisites"})
    if "compare" in blob or " versus " in blob:
        aspects.update({"attributes", "alternatives"})
    if not aspects:
        aspects.add("general")
    return frozenset(aspects)


# Deterministic slot→keyword hints for answer coverage validation only.
SLOT_COVERAGE_HINTS: dict[str, tuple[str, ...]] = {
    "identity": ("identity", "organization", "company", "institution", "who we", "about"),
    "activity": ("activity", "services", "provide", "offer", "work", "mission"),
    "capabilities": ("service", "product", "capabilit", "solution"),
    "contact_info": ("contact", "phone", "email", "address"),
    "options": ("option", "available", "list", "catalog"),
    "current_item": ("offer", "news", "promotion", "current"),
    "offer": ("offer", "discount", "promotion", "sale"),
    "documentation": ("documentation", "guide", "manual"),
    "rule": ("policy", "rule", "terms", "legal"),
    "fact": ("",),
    "general": ("",),
    "answer": ("",),
}


def purpose_expectations_for_answer_type(
    answer_type: str,
) -> tuple[list[str], list[str]]:
    """Map answer type to generic document purposes (schema enums only)."""
    preferred: list[str] = []
    unsuitable: list[str] = []

    if answer_type == "listing":
        preferred = [
            "product listing",
            "product details",
            "service description",
            "pricing",
            "comparison",
            "general information",
        ]
        unsuitable = ["news", "promotion", "about company", "contact information"]
    elif answer_type == "overview":
        preferred = ["about company", "landing page", "service description"]
        unsuitable = ["news", "promotion", "contact information", "general information"]
    elif answer_type == "contact":
        preferred = ["contact information"]
        unsuitable = ["product listing", "news", "promotion"]
    elif answer_type == "faq":
        preferred = ["faq", "support", "documentation"]
        unsuitable = ["news", "promotion"]
    elif answer_type == "comparison":
        preferred = ["comparison", "product listing", "pricing", "product details"]
        unsuitable = ["news", "about company"]
    elif answer_type == "documentation":
        preferred = ["documentation", "legal information", "policy"]
        unsuitable = ["promotion", "news"]
    elif answer_type in {"definition", "fact"}:
        preferred = [
            "product details",
            "service description",
            "documentation",
            "faq",
            "general information",
        ]
        unsuitable = ["news", "promotion", "landing page"]
    else:
        preferred = ["general information", "documentation", "faq"]
        unsuitable = []

    return filter_valid_purposes(preferred), filter_valid_purposes(unsuitable)
