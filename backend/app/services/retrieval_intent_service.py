"""Config-driven query intent classification (no domain hardcoding)."""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.knowledge_profile import ImportantTopic, KnowledgeProfile
from app.services.broad_question_service import BroadQuestionService
from app.services.knowledge_profile_service import (
    BROAD_ROUTING_INTENTS,
    IntentMatchResult,
    KnowledgeProfileService,
)


@dataclass
class RetrievalIntentResult:
    intent: str
    legacy_intent: str
    matched_topic: ImportantTopic | None = None
    matched_aliases: list[str] | None = None
    matched_patterns: list[str] | None = None
    answer_strategy: str = "generic"
    is_broad: bool = False
    confidence: float = 0.5

    @classmethod
    def from_match(
        cls,
        match: IntentMatchResult,
        *,
        is_broad: bool = False,
        confidence: float = 0.75,
    ) -> RetrievalIntentResult:
        return cls(
            intent=match.rule_key,
            legacy_intent=match.routing_intent,
            matched_topic=match.matched_topic,
            matched_aliases=match.matched_aliases or None,
            matched_patterns=match.matched_patterns or None,
            answer_strategy=match.answer_strategy,
            is_broad=is_broad,
            confidence=confidence,
        )


BROAD_RETRIEVAL_INTENTS = BROAD_ROUTING_INTENTS


class RetrievalIntentService:
    @staticmethod
    def classify(
        query: str,
        *,
        normalized: str | None = None,
        profile: KnowledgeProfile | None = None,
    ) -> RetrievalIntentResult:
        profile = profile or KnowledgeProfileService.default_profile()
        raw = (normalized or query or "").strip().lower()
        is_broad = BroadQuestionService.is_broad_question(raw, profile=profile)

        if not raw:
            return RetrievalIntentResult(
                intent="unknown",
                legacy_intent="unknown",
                is_broad=is_broad,
            )

        match = KnowledgeProfileService.match_intent(profile, raw)
        if match.routing_intent != "unknown":
            broad = is_broad or match.routing_intent in BROAD_ROUTING_INTENTS
            return RetrievalIntentResult.from_match(match, is_broad=broad)

        return RetrievalIntentResult(
            intent="unknown",
            legacy_intent="unknown",
            is_broad=is_broad,
            confidence=0.4,
        )

    @staticmethod
    def legacy_intent(result: RetrievalIntentResult) -> str:
        return result.legacy_intent or "unknown"
