"""Route queries using Source Intelligence — domain-agnostic semantic compatibility."""
from __future__ import annotations

import re

from app.models.settings import Settings
from app.schemas.source_intelligence import SourceSemanticProfile
from app.services.qdrant_service import SearchHit
from app.services.retrieval_engine.query_understanding import QueryUnderstandingService
from app.services.retrieval_engine.semantic_compatibility import SemanticCompatibilityScorer
from app.services.retrieval_intent_service import RetrievalIntentResult
from app.services.settings_flags import setting_bool
from app.services.source_intelligence_service import SourceIntelligenceService, SourceProfile

from app.services.rag_planning.purpose_catalog import purpose_expectations_for_answer_type
from app.services.rag_planning.intent_taxonomy import (
    CONTACT_INTENTS,
    OVERVIEW_INTENTS,
    PRODUCT_INTENTS,
    SUPPORT_INTENTS,
    POLICY_INTENTS as LEGAL_INTENTS,
)

_ROUTING_ANSWER_TYPE: dict[str, str] = {
    "overview": "overview",
    "contact": "contact",
    "support": "faq",
    "product": "listing",
    "legal": "documentation",
    "generic": "general",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


class SourceIntelligenceRouter:
    """Apply profile-aware semantic compatibility boosts before final ranking."""

    _compatibility = SemanticCompatibilityScorer()

    @staticmethod
    def route_intent(intent: str) -> str:
        if intent in OVERVIEW_INTENTS:
            return "overview"
        if intent in CONTACT_INTENTS:
            return "contact"
        if intent in SUPPORT_INTENTS:
            return "support"
        if intent in PRODUCT_INTENTS:
            return "product"
        if intent in LEGAL_INTENTS:
            return "legal"
        return "generic"

    @classmethod
    def _understanding(
        cls,
        *,
        routing: str,
        query: str,
        query_intent: str,
    ) -> QueryUnderstanding:
        answer_type = _ROUTING_ANSWER_TYPE.get(routing, "general")
        intent_result = RetrievalIntentResult(
            intent=query_intent or routing,
            legacy_intent=query_intent or routing,
            answer_strategy=answer_type,
            is_broad=routing == "overview",
            confidence=0.75,
        )
        understanding = QueryUnderstandingService.analyze(
            query,
            intent_result=intent_result,
        )
        if understanding.expected_answer_type != answer_type:
            preferred, unsuitable = purpose_expectations_for_answer_type(answer_type)
            preferred_evidence, unsuitable_evidence = QueryUnderstandingService._evidence_expectations(
                query,
                answer_type,
                understanding.topic,
                None,
                intent_result,
            )
            understanding.expected_answer_type = answer_type
            understanding.preferred_purposes = preferred
            understanding.unsuitable_purposes = unsuitable
            understanding.preferred_evidence = preferred_evidence
            understanding.unsuitable_evidence = unsuitable_evidence
        return understanding

    @staticmethod
    def _compat_to_boost(compatibility_score: float) -> float:
        return max(-0.45, min(0.45, (compatibility_score - 0.48) * 0.95))

    @staticmethod
    def _reason_from_compat(signals: list[str]) -> str:
        parts: list[str] = []
        for signal in signals:
            if signal.startswith("purpose:"):
                parts.append(signal)
            elif signal.startswith("unsuitable_purpose:"):
                purpose = signal.split(":", 1)[-1]
                parts.append(f"avoid_purpose:{purpose}")
            elif signal == "canonical_source":
                parts.append("canonical")
            elif signal == "intent_supported":
                parts.append("should_answer_intent")
            elif signal in {"topic_overlap", "marked_suitable", "marked_unsuitable"}:
                parts.append(signal)
            elif "incomplete" in signal:
                parts.append(signal)
        return "; ".join(dict.fromkeys(parts))

    @classmethod
    def semantic_boost(
        cls,
        semantic: SourceSemanticProfile | None,
        *,
        routing: str,
        query: str,
        query_intent: str,
    ) -> tuple[float, str]:
        if semantic is None:
            return 0.0, ""

        understanding = cls._understanding(
            routing=routing,
            query=query,
            query_intent=query_intent,
        )
        profile = SourceProfile(
            source_id=0,
            url="",
            semantic=semantic.to_storage_dict(),
            content_quality=int((semantic.confidence or 0.5) * 100),
            confidence=semantic.confidence or 0.5,
        )
        compat = cls._compatibility.score(
            understanding=understanding,
            profile=profile,
            source=None,
            hit=SearchHit(
                score=0.0,
                source_id=0,
                chunk_index=0,
                title=semantic.main_topic or "",
                url="",
                source_type="page",
                text=semantic.main_topic or "",
            ),
        )
        boost = cls._compat_to_boost(compat.compatibility_score)
        return boost, cls._reason_from_compat(compat.signals)

    @classmethod
    def boost_for_hit(
        cls,
        hit: SearchHit,
        profile: SourceProfile | None,
        *,
        routing: str,
        settings: Settings,
        query_language: str = "unknown",
        query: str = "",
        query_intent: str = "unknown",
    ) -> tuple[float, str]:
        if profile is None:
            return 0.0, ""

        understanding = cls._understanding(
            routing=routing,
            query=query or hit.title or "",
            query_intent=query_intent,
        )
        compat = cls._compatibility.score(
            understanding=understanding,
            profile=profile,
            source=None,
            hit=hit,
            query_language=query_language,
        )
        boost = cls._compat_to_boost(compat.compatibility_score)
        reasons: list[str] = list(compat.signals)

        if profile.content_quality >= 70:
            boost += 0.03
            reasons.append("high_content_quality")
        if profile.boilerplate_ratio >= 0.55:
            boost -= 0.08
            reasons.append("high_boilerplate")

        if setting_bool(settings, "prefer_user_language_sources", default=True):
            if query_language in {"uk", "en"} and profile.source_language == query_language:
                boost += 0.08
                reasons.append(f"lang:{query_language}")
            elif query_language in {"uk", "en"} and profile.source_language == "mixed":
                boost += 0.02
            elif (
                query_language in {"uk", "en"}
                and profile.source_language not in {query_language, "mixed", "unknown"}
            ):
                boost -= 0.06
                reasons.append(f"lang_mismatch:{profile.source_language}")

        if compat.si_incomplete:
            boost = min(boost, 0.12)
            reasons.append("incomplete_source_intelligence")

        reason = cls._reason_from_compat(reasons)
        return boost, reason

    @classmethod
    def rejection_reason(
        cls,
        profile: SourceProfile | None,
        *,
        routing: str,
        query: str = "",
        query_intent: str = "unknown",
    ) -> str:
        if profile is None:
            return ""

        understanding = cls._understanding(
            routing=routing,
            query=query,
            query_intent=query_intent,
        )
        hit = SearchHit(
            score=0.0,
            source_id=profile.source_id,
            chunk_index=0,
            title=profile.llm_summary or profile.url,
            url=profile.url,
            source_type="page",
            text=profile.llm_summary or "",
            document_type=profile.document_type,
        )
        compat = cls._compatibility.score(
            understanding=understanding,
            profile=profile,
            source=None,
            hit=hit,
        )
        semantic = SourceIntelligenceService.semantic_from_profile(profile)

        if compat.si_incomplete and compat.compatibility_score < 0.3:
            return "incomplete_source_intelligence"

        if semantic and semantic.confidence >= 0.5:
            if "marked_unsuitable" in compat.signals:
                return "semantic:not_suitable_for"
            purpose = _norm(semantic.document_purpose)
            if (
                purpose
                and purpose in understanding.unsuitable_purposes
                and (semantic.document_purpose_confidence or 0) >= 0.55
            ):
                return f"semantic:purpose:{purpose}"

        if compat.compatibility_score < 0.22:
            return f"semantic:low_compatibility:{compat.compatibility_score:.2f}"

        return ""
