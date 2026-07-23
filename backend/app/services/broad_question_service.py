"""Detect broad informational questions using profile configuration."""
from __future__ import annotations

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.knowledge_profile_service import KnowledgeProfileService

# Language-agnostic structural markers (not domain-specific).
_STRUCTURAL_BROAD_MARKERS = (
    "tell me about",
    "what is this",
    "what do you do",
    "who are you",
    "about us",
    "about company",
    "describe your",
    "overview",
    "introduction",
    "розкажи",
    "розкажіть",
    "опиши",
    "опишіть",
    "що таке",
    "що ви",
    "чим займа",
    "про нас",
    "про компані",
    "про організа",
    "про сайт",
    "хто ви",
    "яка компан",
    "інформаці",
    "загальн",
)


class BroadQuestionService:
    @staticmethod
    def is_broad_question(
        query: str,
        *,
        profile: KnowledgeProfile | None = None,
    ) -> bool:
        raw = (query or "").strip().lower()
        if not raw:
            return False

        profile = profile or KnowledgeProfileService.default_profile()

        for pattern in profile.overview_query_patterns:
            p = pattern.lower().strip()
            if p and p in raw:
                return True

        if any(m in raw for m in _STRUCTURAL_BROAD_MARKERS):
            return True

        org_hits = KnowledgeProfileService.match_organization_markers(raw, profile)
        if org_hits and len(raw.split()) <= 8:
            return True

        return False

    @staticmethod
    def injection_queries(profile: KnowledgeProfile | None = None) -> list[str]:
        profile = profile or KnowledgeProfileService.default_profile()
        queries: list[str] = []
        seen: set[str] = set()

        def add(q: str) -> None:
            q = q.strip()
            if q and q.lower() not in seen:
                seen.add(q.lower())
                queries.append(q)

        org = profile.organization_name or profile.site_display_name or ""
        if org:
            add(org)
            add(f"about {org}")

        for rule in profile.query_expansion_rules:
            if rule.trigger_intent and rule.trigger_intent != "entity_overview":
                continue
            for term in rule.add_terms:
                for expanded in KnowledgeProfileService.expand_placeholders(term, profile):
                    add(expanded)

        preferred_types = ("homepage", "about_page", "documentation_page", "product_page")
        for doc_rule in profile.document_type_rules:
            if doc_rule.document_type in preferred_types:
                for p in doc_rule.title_patterns[:3]:
                    add(p)
                for p in doc_rule.url_patterns[:2]:
                    add(p.replace("/", " ").strip())

        add("about us")
        add("overview")
        add("homepage")
        return queries
