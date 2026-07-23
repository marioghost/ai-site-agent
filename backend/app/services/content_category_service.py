"""Generic content category detection driven by profile rules."""
from __future__ import annotations

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.content_signals import is_homepage_url
from app.services.knowledge_profile_service import KnowledgeProfileService

ContentCategory = str


def detect_content_category(
    *,
    url: str = "",
    title: str = "",
    heading: str = "",
    document_type: str = "generic_page",
    content_type_hint: str = "generic",
    is_homepage: bool = False,
    profile: KnowledgeProfile | None = None,
) -> ContentCategory:
    profile = profile or KnowledgeProfileService.default_profile()

    if is_homepage or is_homepage_url(url) or document_type == "homepage":
        return "homepage"

    if document_type and document_type not in {"generic_page", ""}:
        return document_type

    hint = (content_type_hint or "generic").lower()
    if hint not in {"generic", "general", ""}:
        return hint

    matched_doc = KnowledgeProfileService.match_document_type(
        profile,
        url=url,
        title=title,
        headings=heading,
        is_homepage=is_homepage,
    )
    if matched_doc and matched_doc != "generic_page":
        return matched_doc

    matched_hint = KnowledgeProfileService.match_content_hint(profile, url, title, heading)
    if matched_hint and matched_hint != "generic":
        return matched_hint

    return "generic_page"


def category_boost(
    routing_intent: str,
    category: str,
    *,
    profile: KnowledgeProfile | None = None,
    document_type: str | None = None,
    content_hint: str | None = None,
    amplified: bool = False,
) -> float:
    profile = profile or KnowledgeProfileService.default_profile()
    rule = KnowledgeProfileService.priority_rule_for_intent(profile, routing_intent)
    if rule is None or category in {"generic_page", "generic"}:
        return 0.0

    boost = 0.0
    base = rule.score_boost
    dt = document_type or category
    if dt in rule.boost_document_types:
        idx = rule.boost_document_types.index(dt)
        boost = max(boost, base - idx * 0.06)
    elif dt in rule.deprioritize_document_types:
        idx = rule.deprioritize_document_types.index(dt)
        boost = min(boost, -0.28 - idx * 0.02)

    hint = content_hint or (category if category not in {"generic_page", "homepage"} else "")
    if hint and hint in rule.boost_content_hints:
        idx = rule.boost_content_hints.index(hint)
        boost = max(boost, base * 0.85 - idx * 0.03)
    elif hint and hint in rule.deprioritize_content_hints:
        idx = rule.deprioritize_content_hints.index(hint)
        boost = min(boost, -0.20 - idx * 0.02)

    if amplified and boost > 0:
        boost *= 1.4
    return boost
