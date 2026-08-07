"""Shared focus/compatibility evaluation for DFP and EvidencePlanner.

Leaf module — no package-init side effects. Domain-agnostic labels only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.retrieval_engine.query_understanding import QueryUnderstanding

_STRONG_LABELS = frozenset(
    {
        "exact_match",
        "same_product",
        "organization_support",
        "definition_support",
        "procedure_support",
        "navigation_support",
    }
)
_NEGATIVE_LABELS = frozenset(
    {
        "adjacent_incompatible",
        "news_only",
        "marketing_only",
        "historical",
        "irrelevant",
    }
)
_PRODUCT_ROLES = frozenset(
    {"product_details", "service_overview", "pricing", "campaign", "marketing"}
)
_ORG_ROLES = frozenset({"organization_overview"})
_NAV_ROLES = frozenset({"contact", "support", "faq"})
_NEWS_ROLES = frozenset({"news", "campaign", "marketing"})
_NEWS_TYPES = frozenset(
    {
        "news_page",
        "blog_post",
        "blog_page",
        "promotion_page",
        "campaign_page",
        "offer_page",
        "action_page",
    }
)
_LOCATOR_HINTS = frozenset(
    {
        "locator",
        "branch",
        "branches",
        "atm",
        "map",
        "location",
        "office",
        "відділен",
        "банкомат",
        "знайти",
        "finder",
        "directory",
        "store finder",
        "clinic locations",
        "campus map",
    }
)
_HISTORICAL_HINTS = frozenset(
    {
        "archive",
        "historical",
        "formerly",
        "expired",
        "застар",
        "архів",
        "устарел",
        "archived",
        "outdated",
        "legacy",
    }
)
_YEAR_TOKEN = re.compile(r"\b(19\d{2}|20\d{2})\b")
_PRODUCT_PATH_HINTS = re.compile(
    r"(/products?/|/services?/|/pricing|/plans?/|"
    r"/corporate-clients/|/personal-clients/.+|"
    r"trade-finance|salary|зарплат|іпотек|mortgage|"
    r"deposit|депозит|credit-card|кредитн|cash-loan|автокредит)",
    re.I,
)
_NEWS_TITLE_HINTS = re.compile(
    r"(новин|/news|news-post|\bnews\b|\bblog\b|press release|прес-?реліз)",
    re.I,
)
_CAREER_HINTS = re.compile(
    r"(career|vacanc|job\b|jobs\b|ваканс|робот[ауи]|internship|студент)",
    re.I,
)
_GENERIC_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "page",
        "home",
        "what",
        "which",
        "how",
        "are",
        "this",
        "that",
        "about",
        "про",
        "що",
        "як",
        "які",
        "для",
        "або",
    }
)


@dataclass
class FocusCompatibilityResult:
    score: float
    label: str
    reasons: list[str] = field(default_factory=list)


def is_strong_compatibility(label: str) -> bool:
    return label in _STRONG_LABELS


def is_negative_compatibility(label: str) -> bool:
    return label in _NEGATIVE_LABELS


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[\w\u0400-\u04FF]{3,}", (text or "").lower())}


def _overlap_ratio(focus_terms: set[str], source_terms: set[str]) -> float:
    if not focus_terms:
        return 0.0
    matched = 0
    for term in focus_terms:
        if term in source_terms:
            matched += 1
            continue
        needle = term[:5]
        if len(needle) >= 4 and any(
            other.startswith(needle) or term.startswith(other[:5])
            for other in source_terms
            if len(other) >= 4
        ):
            matched += 1
    return matched / max(len(focus_terms), 1)


def _blob_terms(*parts: str) -> set[str]:
    return _tokens(" ".join(p for p in parts if p))


def _has_any(terms: set[str], hints: set[str]) -> bool:
    joined = " ".join(terms)
    return any(h in joined or h in terms for h in hints)


def _has_historical_signal(source_terms: set[str], blob: str = "") -> bool:
    """Detect archive/stale cues including calendar years older than current−1."""
    if _has_any(source_terms, _HISTORICAL_HINTS):
        return True
    from datetime import datetime, timezone

    cutoff_year = datetime.now(timezone.utc).year - 2
    hay = blob or " ".join(source_terms)
    for match in _YEAR_TOKEN.finditer(hay):
        try:
            year = int(match.group(1))
        except ValueError:
            continue
        if year <= cutoff_year:
            return True
    return False


def _looks_like_news(*, title: str, url: str, document_type: str, page_role: str) -> bool:
    dtype = (document_type or "").lower()
    role = (page_role or "").lower()
    if dtype in _NEWS_TYPES or role == "news":
        return True
    return bool(_NEWS_TITLE_HINTS.search(f"{title} {url}"))


def _looks_like_career(*, title: str, url: str, text: str) -> bool:
    return bool(_CAREER_HINTS.search(f"{title} {url} {text[:160]}"))


def evaluate_focus_compatibility(
    understanding: QueryUnderstanding | None,
    *,
    title: str = "",
    purpose: str = "",
    page_role: str = "",
    document_type: str = "",
    text: str = "",
    url: str = "",
    semantic_phrases: list[str] | None = None,
) -> FocusCompatibilityResult:
    if understanding is None:
        return FocusCompatibilityResult(0.45, "ambiguous", ["no_understanding"])

    focus = getattr(understanding, "semantic_focus", "") or "general"
    expected = getattr(understanding, "expected_evidence_type", "") or "general"
    scope = getattr(understanding, "scope_type", "") or "general"
    focus_terms = {
        t
        for t in getattr(understanding, "focus_terms", []) or []
        if len(t) >= 3 and t not in _GENERIC_STOP
    }
    phrases = list(semantic_phrases or [])
    source_terms = _blob_terms(
        title,
        purpose,
        page_role,
        document_type,
        text[:280],
        *phrases,
    )
    overlap = _overlap_ratio(focus_terms, source_terms) if focus_terms else 0.0
    # Ultra-short product codes (2–3 chars) must appear when present in the query focus.
    short_focus = {t for t in focus_terms if len(t) <= 3 and t.isalnum()}
    missing_short = bool(short_focus and not short_focus.issubset(source_terms))
    role = (page_role or "").lower()
    dtype = (document_type or "").lower()
    purpose_l = (purpose or "").lower()
    reasons: list[str] = [f"focus={focus}", f"expected={expected}", f"overlap={overlap:.2f}"]
    is_news = _looks_like_news(
        title=title, url=url, document_type=document_type, page_role=page_role
    )
    is_career = _looks_like_career(title=title, url=url, text=text)

    # Organization profile / overview
    if focus in {"organization_profile", "overview"} or scope == "organization_overview":
        if is_news or is_career:
            label = "news_only" if is_news else "adjacent_incompatible"
            return FocusCompatibilityResult(0.12, label, reasons + ["incidental_news_or_career"])
        if _PRODUCT_PATH_HINTS.search(f"{url} {title}"):
            return FocusCompatibilityResult(
                0.12, "adjacent_incompatible", reasons + ["product_path_vs_organization"]
            )
        if role in _ORG_ROLES or purpose_l in {"about company", "landing page"}:
            return FocusCompatibilityResult(1.0, "organization_support", reasons + ["org_role"])
        if role in {"documentation", "faq", "service_overview"} and expected == "organization_profile":
            return FocusCompatibilityResult(0.62, "supporting_evidence", reasons + ["org_support_page"])
        if role in {"product_details", "pricing"} or purpose_l in {
            "product details",
            "product listing",
            "pricing",
        }:
            return FocusCompatibilityResult(
                0.12, "adjacent_incompatible", reasons + ["product_vs_organization"]
            )
        if role in _NEWS_ROLES or dtype in _NEWS_TYPES:
            label = "news_only" if role == "news" or "news" in dtype else "marketing_only"
            return FocusCompatibilityResult(0.14, label, reasons + ["incidental_for_org"])
        return FocusCompatibilityResult(0.40, "ambiguous", reasons)

    # Locator / contact / navigation
    if focus in {"locator", "contact"} or scope == "navigation":
        if is_news or is_career:
            return FocusCompatibilityResult(
                0.12, "news_only" if is_news else "adjacent_incompatible", reasons + ["news_vs_navigation"]
            )
        locator_hit = _has_any(source_terms, _LOCATOR_HINTS) or "locator" in purpose_l
        if focus == "locator" and (locator_hit or role in _NAV_ROLES or "contact" in purpose_l):
            return FocusCompatibilityResult(
                max(0.82, overlap), "navigation_support", reasons + ["locator_or_contact"]
            )
        if focus == "contact" and (role in _NAV_ROLES or "contact" in purpose_l):
            return FocusCompatibilityResult(
                max(0.8, overlap), "navigation_support", reasons + ["contact_role"]
            )
        if role in _PRODUCT_ROLES or purpose_l in {"product details", "product listing", "pricing"}:
            return FocusCompatibilityResult(
                0.16, "adjacent_incompatible", reasons + ["product_vs_navigation"]
            )
        if role in _NEWS_ROLES or dtype in _NEWS_TYPES or is_news:
            return FocusCompatibilityResult(0.18, "news_only", reasons + ["news_vs_navigation"])
        return FocusCompatibilityResult(
            0.48 if overlap >= 0.34 else 0.20,
            "category_support" if overlap >= 0.34 else "adjacent_incompatible",
            reasons,
        )

    # Definition
    if focus == "definition" or expected == "definition":
        if is_news:
            return FocusCompatibilityResult(0.14, "news_only", reasons + ["news_not_definition"])
        if role in {"product_details", "service_overview", "documentation", "faq"} or purpose_l in {
            "product details",
            "service description",
            "documentation",
            "faq",
        }:
            if overlap >= 0.34 and not missing_short:
                return FocusCompatibilityResult(
                    0.92, "definition_support", reasons + ["authoritative_definition"]
                )
            return FocusCompatibilityResult(0.58, "same_category", reasons + ["related_definition"])
        if role in _ORG_ROLES or purpose_l in {"landing page", "about company"}:
            return FocusCompatibilityResult(0.28, "ambiguous", reasons + ["homepage_weak_for_definition"])
        if role in _NEWS_ROLES or dtype in _NEWS_TYPES:
            return FocusCompatibilityResult(0.14, "news_only", reasons + ["news_not_definition"])
        if overlap >= 0.66 and not missing_short:
            return FocusCompatibilityResult(0.9, "definition_support", reasons)
        return FocusCompatibilityResult(0.30, "ambiguous", reasons)

    # Procedure
    if focus == "procedure" or expected == "procedure":
        if role in {"faq", "support", "documentation", "product_details", "service_overview"}:
            return FocusCompatibilityResult(
                max(0.78, overlap), "procedure_support", reasons + ["procedure_page"]
            )
        if role in _NEWS_ROLES or dtype in _NEWS_TYPES:
            return FocusCompatibilityResult(0.16, "news_only", reasons)
        if overlap >= 0.5:
            return FocusCompatibilityResult(0.64, "supporting_evidence", reasons)
        return FocusCompatibilityResult(0.28, "ambiguous", reasons)

    # Comparison may intentionally mix products — before product-family gates.
    if focus == "comparison":
        if overlap >= 0.34:
            return FocusCompatibilityResult(0.7, "same_category", reasons)
        return FocusCompatibilityResult(0.45, "supporting_evidence", reasons)

    # Policy / documentation / FAQ
    if expected == "policy" or focus == "faq":
        if is_news or is_career:
            return FocusCompatibilityResult(0.14, "news_only", reasons + ["news_vs_policy"])
        if role in {"documentation", "faq", "support"} or purpose_l in {
            "documentation",
            "faq",
            "legal",
            "policy",
        }:
            if overlap >= 0.34 or expected == "policy":
                return FocusCompatibilityResult(
                    0.88, "definition_support" if expected == "policy" else "procedure_support",
                    reasons + ["policy_or_faq_page"],
                )
            return FocusCompatibilityResult(0.55, "supporting_evidence", reasons)
        if role in _ORG_ROLES and expected == "policy":
            return FocusCompatibilityResult(0.32, "ambiguous", reasons + ["about_weak_for_policy"])
        if overlap >= 0.5:
            return FocusCompatibilityResult(0.6, "supporting_evidence", reasons)
        return FocusCompatibilityResult(0.28, "ambiguous", reasons)

    # Rates / pricing / product specification / eligibility / product family
    productish = focus in {
        "product_specification",
        "rates",
        "eligibility",
        "listing",
    } or scope in {"product_family", "exact_subject"}
    if productish:
        if role in _NEWS_ROLES or dtype in _NEWS_TYPES:
            if _has_historical_signal(source_terms):
                return FocusCompatibilityResult(0.18, "historical", reasons + ["stale_or_news"])
            return FocusCompatibilityResult(0.16, "news_only", reasons + ["news_vs_product"])
        if role in {"marketing"} or purpose_l in {"promotion", "landing page"}:
            return FocusCompatibilityResult(0.18, "marketing_only", reasons)

        primary = {t for t in focus_terms if t not in _GENERIC_STOP and len(t) >= 4}
        distinctive = {t for t in primary if len(t) >= 5}
        distinctive_hit = _overlap_ratio(distinctive, source_terms) if distinctive else 1.0
        extra = source_terms - focus_terms - _GENERIC_STOP
        conflicting = {
            t
            for t in extra
            if len(t) >= 5
            and not any(t.startswith(f[:5]) or f.startswith(t[:5]) for f in primary if len(f) >= 4)
        }
        # Adjacent product family: missing distinctive focus terms + other product tokens.
        if (
            distinctive
            and distinctive_hit < 0.5
            and role in _PRODUCT_ROLES
            and (conflicting or overlap < 0.66)
        ):
            return FocusCompatibilityResult(
                0.14, "adjacent_incompatible", reasons + ["product_family_mismatch"]
            )
        if primary and overlap < 0.5 and conflicting and role in _PRODUCT_ROLES:
            return FocusCompatibilityResult(
                0.14, "adjacent_incompatible", reasons + ["product_family_mismatch"]
            )
        if missing_short and role in _PRODUCT_ROLES:
            return FocusCompatibilityResult(
                0.18, "adjacent_incompatible", reasons + ["missing_short_focus"]
            )
        if overlap >= 0.66 and not missing_short and distinctive_hit >= 0.5:
            label = "same_product" if role in _PRODUCT_ROLES else "exact_match"
            return FocusCompatibilityResult(0.96, label, reasons + ["strong_focus"])
        if overlap >= 0.45 and distinctive_hit >= 0.5:
            return FocusCompatibilityResult(0.72, "same_category", reasons + ["category_overlap"])
        if overlap >= 0.34 and distinctive_hit >= 0.34:
            return FocusCompatibilityResult(0.58, "category_support", reasons)
        if overlap > 0 and distinctive_hit >= 0.34:
            return FocusCompatibilityResult(0.34, "ambiguous", reasons)
        if role in _PRODUCT_ROLES or role in {"pricing"}:
            return FocusCompatibilityResult(
                0.12, "adjacent_incompatible", reasons + ["no_focus_overlap"]
            )
        return FocusCompatibilityResult(0.26, "ambiguous", reasons)

    # Generic fallback
    if overlap >= 0.66 and not missing_short:
        return FocusCompatibilityResult(0.92, "exact_match", reasons)
    if overlap >= 0.34:
        return FocusCompatibilityResult(0.6, "category_support", reasons)
    if overlap > 0:
        return FocusCompatibilityResult(0.36, "ambiguous", reasons)
    if role in _PRODUCT_ROLES or role in _NEWS_ROLES:
        return FocusCompatibilityResult(0.14, "adjacent_incompatible", reasons)
    return FocusCompatibilityResult(0.28, "ambiguous", reasons)
