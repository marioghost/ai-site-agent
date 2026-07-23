"""Semantic compatibility between query understanding and Source Intelligence profiles."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.source import Source
from app.schemas.source_intelligence import SourceSemanticProfile
from app.services.qdrant_service import SearchHit
from app.services.retrieval_engine.query_understanding import QueryUnderstanding
from app.services.source_intelligence_service import SourceIntelligenceService, SourceProfile


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[\w\u0400-\u04FF]{3,}", _norm(text))}


def _phrase_overlap(query: str, phrases: list[str]) -> float:
    if not query or not phrases:
        return 0.0
    q = _norm(query)
    q_tokens = _tokens(q)
    hits = 0.0
    for phrase in phrases:
        p = _norm(phrase)
        if not p:
            continue
        if p in q or q in p:
            hits += 2.0
            continue
        p_tokens = _tokens(p)
        overlap = len(p_tokens & q_tokens)
        if overlap:
            hits += overlap / max(len(p_tokens), 1)
    return min(1.0, hits / max(len(phrases), 1))


def _intent_overlap(query_intent: str, supported: list[str]) -> float:
    if not supported:
        return 0.0
    intent = _norm(query_intent).replace(" ", "_")
    normalized = {_norm(i).replace(" ", "_") for i in supported}
    if intent in normalized:
        return 1.0
    for s in normalized:
        if intent and (intent in s or s in intent):
            return 0.75
    return 0.0


@dataclass
class SemanticCompatibilityResult:
    compatibility_score: float = 0.0
    evidence_score: float = 0.0
    intent_match_score: float = 0.0
    topic_match_score: float = 0.0
    source_quality_score: float = 0.0
    answerability_score: float = 0.0
    confidence_score: float = 0.0
    si_incomplete: bool = False
    si_warning: str = ""
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "compatibility_score": round(self.compatibility_score, 4),
            "evidence_score": round(self.evidence_score, 4),
            "intent_match_score": round(self.intent_match_score, 4),
            "topic_match_score": round(self.topic_match_score, 4),
            "source_quality_score": round(self.source_quality_score, 4),
            "answerability_score": round(self.answerability_score, 4),
            "confidence_score": round(self.confidence_score, 4),
            "si_incomplete": self.si_incomplete,
            "si_warning": self.si_warning,
            "signals": self.signals,
        }


class SemanticCompatibilityScorer:
    """Score how well a source matches query needs using SI metadata only."""

    def score(
        self,
        *,
        understanding: QueryUnderstanding,
        profile: SourceProfile | None,
        source: Source | None,
        hit: SearchHit,
        query_language: str = "unknown",
    ) -> SemanticCompatibilityResult:
        result = SemanticCompatibilityResult()
        signals: list[str] = []

        if profile is None and source is None:
            result.si_incomplete = True
            result.si_warning = "no_source_profile"
            result.confidence_score = 0.25
            result.compatibility_score = 0.15
            result.signals = ["missing_source_intelligence"]
            return result

        if profile is None and source is not None:
            profile = SourceIntelligenceService.profile_from_source(source)
            if profile is None:
                profile = SourceIntelligenceService.build_profile(source)

        semantic = SourceIntelligenceService.semantic_from_profile(profile)
        has_semantic = semantic is not None and (semantic.confidence or 0) > 0.2
        has_structural = bool(
            profile
            and (
                profile.should_answer_product
                or profile.should_answer_company
                or profile.should_answer_support
                or profile.should_answer_general
                or profile.canonical
                or (profile.importance or 0) >= 55
            )
        )

        if not has_semantic:
            if has_structural:
                result.si_warning = "rule_based_profile_only"
                signals.append("structural_profile_only")
            else:
                result.si_incomplete = True
                result.si_warning = "incomplete_semantic_profile"
                signals.append("incomplete_source_intelligence")

        if has_semantic:
            si_conf = semantic.confidence or 0.5
        elif has_structural:
            si_conf = max(0.5, (profile.content_quality or 50) / 100.0 * 0.75)
        else:
            si_conf = (profile.content_quality or 0) / 100.0 * 0.5
        if result.si_incomplete:
            si_conf *= 0.55

        # Intent match
        intent_score = 0.0
        if semantic and semantic.supported_intents:
            intent_score = _intent_overlap(understanding.legacy_intent, semantic.supported_intents)
        elif profile:
            if self._structural_intent_match(understanding, profile):
                intent_score = 0.55
                if profile.canonical:
                    intent_score = min(1.0, intent_score + 0.12)
            else:
                intent_score = 0.15
        result.intent_match_score = intent_score
        if intent_score >= 0.75:
            signals.append("intent_supported")

        # Topic match
        topic_score = 0.0
        if semantic:
            topic_phrases = [semantic.main_topic, *semantic.subtopics, *semantic.search_keywords]
            topic_score = max(
                _phrase_overlap(understanding.query, topic_phrases),
                _phrase_overlap(understanding.topic or "", topic_phrases),
            )
            if semantic.main_topic and _norm(semantic.main_topic) in _norm(understanding.query):
                topic_score = max(topic_score, semantic.main_topic_confidence or 0.5)
        if profile and profile.topics:
            topic_score = max(topic_score, _phrase_overlap(understanding.query, profile.topics))
        result.topic_match_score = min(1.0, topic_score)
        if topic_score >= 0.4:
            signals.append("topic_overlap")

        # Evidence / purpose fit
        evidence_score = self._evidence_fit(understanding, semantic, profile, signals)

        # Suitable / not suitable from semantic profile
        if semantic:
            suitable = _phrase_overlap(
                understanding.query,
                semantic.suitable_for + understanding.preferred_evidence,
            )
            unsuitable = _phrase_overlap(
                understanding.query,
                semantic.not_suitable_for + understanding.unsuitable_evidence,
            )
            if suitable > 0:
                evidence_score = min(1.0, evidence_score + suitable * 0.35)
                signals.append("marked_suitable")
            if unsuitable >= 0.35:
                evidence_score = max(0.0, evidence_score - unsuitable * 0.45)
                signals.append("marked_unsuitable")

        result.evidence_score = min(1.0, max(0.0, evidence_score))

        # Source quality & answerability
        quality = (profile.content_quality or 50) / 100.0 if profile else 0.45
        boilerplate = profile.boilerplate_ratio if profile else hit.boilerplate_ratio
        nav_penalty = min(0.4, boilerplate or 0.0)
        answerability = self._answerability(profile, semantic)
        result.answerability_score = answerability
        result.source_quality_score = max(0.0, min(1.0, quality * answerability - nav_penalty * 0.5))
        if profile and profile.canonical:
            result.source_quality_score = min(1.0, result.source_quality_score + 0.08)
            signals.append("canonical_source")

        if query_language in {"uk", "en"} and profile:
            if profile.source_language == query_language:
                result.source_quality_score = min(1.0, result.source_quality_score + 0.06)
            elif profile.source_language not in {query_language, "mixed", "unknown"}:
                result.source_quality_score = max(0.0, result.source_quality_score - 0.08)

        # Aggregate compatibility (fixed internal blend — not user-tunable)
        result.compatibility_score = max(
            0.0,
            min(
                1.0,
                0.30 * result.intent_match_score
                + 0.30 * result.evidence_score
                + 0.25 * result.topic_match_score
                + 0.15 * result.answerability_score,
            ),
        )
        if result.si_incomplete:
            result.compatibility_score *= 0.72
        elif not has_semantic and has_structural:
            result.compatibility_score *= 0.92

        result.confidence_score = max(
            0.0,
            min(
                1.0,
                si_conf * 0.55
                + result.compatibility_score * 0.30
                + result.source_quality_score * 0.15,
            ),
        )
        result.signals = signals
        return result

    @staticmethod
    def _structural_intent_match(understanding: QueryUnderstanding, profile: SourceProfile) -> bool:
        at = understanding.expected_answer_type
        if at == "listing" and profile.should_answer_product:
            return True
        if at == "overview" and (profile.should_answer_company or profile.should_answer_general):
            return True
        if at == "contact" and profile.page_role == "contact":
            return True
        if at == "faq" and profile.should_answer_support:
            return True
        return False

    @staticmethod
    def _evidence_fit(
        understanding: QueryUnderstanding,
        semantic: SourceSemanticProfile | None,
        profile: SourceProfile | None,
        signals: list[str],
    ) -> float:
        score = 0.35
        purpose = _norm(semantic.document_purpose if semantic else "")
        purpose_conf = (semantic.document_purpose_confidence if semantic else 0.0) or 0.5

        if purpose:
            if purpose in understanding.preferred_purposes:
                score += 0.35 * purpose_conf
                signals.append(f"purpose:{purpose}")
            if purpose in understanding.unsuitable_purposes:
                score -= 0.40 * purpose_conf
                signals.append(f"unsuitable_purpose:{purpose}")

        # Listing queries: boost enumeration-like purposes, penalize news/blog-like
        if understanding.expected_answer_type == "listing":
            if purpose in {"product listing", "product details", "service description", "pricing"}:
                score += 0.25
            if purpose in {"news", "promotion", "about company"}:
                score -= 0.20
            if semantic and _phrase_overlap(understanding.query, semantic.suitable_for) > 0.3:
                score += 0.15

        if profile and understanding.expected_answer_type == "overview":
            if profile.canonical:
                score += 0.12
            if profile.importance >= 70:
                score += 0.08
            if profile.should_answer_company or profile.should_answer_general:
                score += 0.15
                signals.append("structural_overview_fit")

        return max(0.0, min(1.0, score))

    @staticmethod
    def _answerability(
        profile: SourceProfile | None, semantic: SourceSemanticProfile | None
    ) -> float:
        if profile is None:
            return 0.45
        base = 0.45
        if profile.should_answer_general:
            base += 0.15
        if profile.should_answer_product:
            base += 0.1
        if profile.should_answer_support:
            base += 0.1
        if profile.should_answer_company:
            base += 0.1
        if semantic and semantic.suitable_for:
            base += 0.05
        if profile.llm_summary:
            base += 0.05
        return min(1.0, base)
