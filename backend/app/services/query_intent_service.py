"""Profile-driven query intent classification for retrieval routing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas.knowledge_profile import ImportantTopic, KnowledgeProfile
from app.services.knowledge_profile_service import (
    BROAD_ROUTING_INTENTS,
    KnowledgeProfileService,
)

QueryIntent = Literal[
    "entity_overview",
    "topic_overview",
    "category_overview",
    "specific_fact",
    "faq_like",
    "contacts_query",
    "news_query",
    "unknown",
]

BROAD_INTENTS: frozenset[str] = BROAD_ROUTING_INTENTS | frozenset({"contacts_query"})
OVERVIEW_INTENTS: frozenset[str] = frozenset(
    {"entity_overview", "topic_overview", "category_overview"}
)


@dataclass
class IntentClassification:
    intent: QueryIntent
    matched_topic: ImportantTopic | None = None
    matched_aliases: list[str] | None = None
    matched_patterns: list[str] | None = None
    answer_strategy: str = "generic"


class QueryIntentService:
    """Heuristic intent classifier driven by Agent Knowledge Profile."""

    @staticmethod
    def classify(
        query: str,
        *,
        normalized: str | None = None,
        profile: KnowledgeProfile | None = None,
    ) -> QueryIntent:
        return QueryIntentService.classify_detailed(
            query, normalized=normalized, profile=profile
        ).intent

    @staticmethod
    def classify_detailed(
        query: str,
        *,
        normalized: str | None = None,
        profile: KnowledgeProfile | None = None,
    ) -> IntentClassification:
        profile = profile or KnowledgeProfileService.default_profile()
        raw = (normalized or query or "").strip().lower()
        if not raw:
            return IntentClassification(intent="unknown")

        match = KnowledgeProfileService.match_intent(profile, raw)
        intent = match.routing_intent
        if intent not in {
            "entity_overview",
            "topic_overview",
            "category_overview",
            "specific_fact",
            "faq_like",
            "contacts_query",
            "news_query",
            "unknown",
        }:
            intent = "unknown"

        return IntentClassification(
            intent=intent,  # type: ignore[arg-type]
            matched_topic=match.matched_topic,
            matched_aliases=match.matched_aliases or None,
            matched_patterns=match.matched_patterns or None,
            answer_strategy=match.answer_strategy,
        )

    @staticmethod
    def supplemental_queries(
        intent: QueryIntent,
        profile: KnowledgeProfile | None = None,
    ) -> list[str]:
        profile = profile or KnowledgeProfileService.default_profile()
        queries: list[str] = []
        seen: set[str] = set()

        def add(q: str) -> None:
            q = q.strip()
            if q and q.lower() not in seen:
                seen.add(q.lower())
                queries.append(q)

        for rule in profile.query_expansion_rules:
            trigger = rule.trigger_intent or rule.intent
            if trigger and trigger != intent:
                continue
            for term in rule.add_terms:
                for expanded in KnowledgeProfileService.expand_placeholders(term, profile):
                    add(expanded)

        rule_cfg = KnowledgeProfileService.priority_rule_for_intent(profile, intent)
        preferred_types = tuple(rule_cfg.boost_document_types) if rule_cfg else ()

        for doc_rule in profile.document_type_rules:
            if doc_rule.document_type in preferred_types:
                for p in doc_rule.title_patterns[:3]:
                    add(p)
                for p in doc_rule.url_patterns[:2]:
                    add(p.replace("/", " ").strip())

        if intent == "entity_overview" and profile.organization_name:
            add(f"about {profile.organization_name}")

        return queries
