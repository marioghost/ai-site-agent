"""Human-readable retrieval explanations from semantic metadata."""
from __future__ import annotations

from app.services.retrieval_engine.query_understanding import QueryUnderstanding
from app.services.retrieval_engine.semantic_compatibility import SemanticCompatibilityResult
from app.services.retrieval_engine.types import RankedDocument
from app.services.source_intelligence_service import SourceIntelligenceService, SourceProfile


class ExplanationBuilder:
    @staticmethod
    def why_selected(
        doc: RankedDocument,
        *,
        understanding: QueryUnderstanding,
        compatibility: SemanticCompatibilityResult,
        profile: SourceProfile | None,
    ) -> str:
        parts: list[str] = []
        semantic = SourceIntelligenceService.semantic_from_profile(profile) if profile else None

        if compatibility.topic_match_score >= 0.4:
            topic = semantic.main_topic if semantic and semantic.main_topic else understanding.topic
            if topic:
                parts.append(f"directly relates to topic «{topic}»")
            else:
                parts.append("matches the query topic")

        if compatibility.compatibility_label == "exact_match":
            parts.append("matches the same subject or product family")
        elif compatibility.compatibility_label == "organization_support":
            parts.append("supports an organization-level answer")
        elif compatibility.compatibility_label == "navigation_support":
            parts.append("supports a practical navigation answer")
        elif compatibility.compatibility_label == "category_support":
            parts.append("supports the same category but may need scope qualification")

        if semantic and semantic.document_purpose:
            purpose = semantic.document_purpose
            if understanding.expected_answer_type == "listing" and purpose in {
                "product listing",
                "product details",
                "service description",
                "pricing",
            }:
                parts.append(f"appears to enumerate options ({purpose})")
            elif understanding.expected_answer_type == "overview" and purpose in {
                "about company",
                "landing page",
                "general information",
            }:
                parts.append(f"suitable for overview questions ({purpose})")
            elif compatibility.evidence_score >= 0.5:
                parts.append(f"document purpose fits: {purpose}")

        if compatibility.intent_match_score >= 0.75:
            parts.append("supports this query intent")
        elif compatibility.intent_match_score >= 0.4:
            parts.append("partially matches query intent")

        if doc.score.dense_score >= 0.45:
            parts.append("strong semantic similarity to query")
        elif doc.score.lexical_score >= 0.4:
            parts.append("strong keyword relevance")

        if compatibility.source_quality_score >= 0.6:
            parts.append("high source quality")
        if profile and profile.canonical:
            parts.append("canonical page for this subject")

        if compatibility.si_incomplete:
            parts.append("note: Source Intelligence profile incomplete")

        if not parts:
            parts.append("best available semantic match among candidates")

        return "; ".join(dict.fromkeys(parts))

    @staticmethod
    def why_rejected(
        doc: RankedDocument,
        *,
        understanding: QueryUnderstanding,
        compatibility: SemanticCompatibilityResult,
        profile: SourceProfile | None,
        reason_code: str,
    ) -> str:
        if reason_code.startswith("below minimum score"):
            return (
                f"score too low for this query ({doc.score.final_score:.2f}); "
                f"compatibility {compatibility.compatibility_score:.2f}"
            )
        if reason_code == "lower score than selected documents":
            return "other documents matched the query intent and evidence type better"
        if "duplicate" in reason_code:
            return "similar page already selected for context diversity"
        if compatibility.compatibility_label == "adjacent_incompatible":
            return "adjacent product or page type does not answer the same question"

        semantic = SourceIntelligenceService.semantic_from_profile(profile) if profile else None
        parts: list[str] = []

        if semantic and semantic.document_purpose:
            purpose = semantic.document_purpose
            if (
                understanding.expected_answer_type == "listing"
                and purpose in {"news", "promotion", "about company", "general information"}
            ):
                parts.append(f"discusses «{purpose}» rather than listing available options")
            elif purpose in understanding.unsuitable_purposes:
                parts.append(f"purpose «{purpose}» is less suitable for this query")

        if "marked_unsuitable" in compatibility.signals:
            parts.append("marked as not suitable for this kind of question")
        if "unsuitable_purpose" in " ".join(compatibility.signals):
            parts.append("semantic profile indicates low suitability")

        if compatibility.topic_match_score < 0.2 and understanding.topic:
            parts.append(f"weak topic match for «{understanding.topic}»")

        if compatibility.si_incomplete:
            parts.append("incomplete Source Intelligence — confidence reduced")

        if not parts:
            parts.append(reason_code.replace("_", " "))

        return "; ".join(dict.fromkeys(parts))
