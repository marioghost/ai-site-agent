"""Automatic semantic document scoring — no hardcoded category weights."""
from __future__ import annotations

from datetime import datetime, timezone

from app.models.settings import Settings
from app.models.source import Source
from app.services.content_signals import token_set
from app.services.qdrant_service import SearchHit
from app.services.retrieval_engine.document_quality import DocumentQualityService
from app.services.retrieval_engine.explanation_builder import ExplanationBuilder
from app.services.retrieval_engine.query_understanding import QueryUnderstanding
from app.services.retrieval_engine.semantic_compatibility import (
    SemanticCompatibilityResult,
    SemanticCompatibilityScorer,
)
from app.services.retrieval_engine.types import DocumentScoreComponents, RankedDocument
from app.services.retrieval_scoring_service import score_content_match
from app.services.source_intelligence_service import SourceIntelligenceService, SourceProfile


# Fixed internal blend — not exposed to administrators.
_BLEND_SEMANTIC = 0.30
_BLEND_LEXICAL = 0.20
_BLEND_COMPATIBILITY = 0.35
_BLEND_QUALITY = 0.10
_BLEND_FRESHNESS = 0.05


class DocumentScorer:
    """Score documents using retrieval signals + automatic semantic compatibility."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._compatibility = SemanticCompatibilityScorer()
        self._quality = DocumentQualityService()

    def score_document(
        self,
        doc: RankedDocument,
        *,
        query: str,
        understanding: QueryUnderstanding,
        query_tokens: set[str] | None = None,
        source: Source | None = None,
        profile: SourceProfile | None = None,
        query_language: str = "unknown",
        indexed_at: datetime | None = None,
    ) -> tuple[DocumentScoreComponents, SemanticCompatibilityResult]:
        hit = doc.representative_chunk
        tokens = query_tokens or token_set(query)
        s = self.settings

        dense = self._aggregate_signal(doc.all_chunks, "dense_score")
        lexical = self._aggregate_signal(doc.all_chunks, "lexical_score")

        if profile is None and source is not None:
            profile = SourceIntelligenceService.profile_from_source(source)
            if profile is None:
                profile = SourceIntelligenceService.build_profile(source)
            self._enrich_hit_from_profile(hit, profile)
        if source is not None:
            ch = (getattr(source, "content_hash", None) or "").strip()
            if ch:
                hit.content_hash = ch
                for chunk in doc.all_chunks:
                    if not getattr(chunk, "content_hash", ""):
                        chunk.content_hash = ch

        title_s, main_s, url_s, bp_pen, nav_pen, match_reason = score_content_match(
            query_tokens=tokens,
            title=hit.title,
            heading=hit.heading,
            text=hit.text,
            url=hit.url,
            title_boost=s.title_match_boost,
            heading_boost=s.heading_match_boost,
            boilerplate_ratio=hit.boilerplate_ratio,
        )
        hit.title_score = title_s
        hit.main_content_score = main_s
        hit.url_score = url_s
        hit.boilerplate_score = bp_pen + nav_pen
        metadata_boost = title_s + url_s + main_s - bp_pen - nav_pen
        if match_reason:
            hit.rejection_reason = match_reason

        compat = self._compatibility.score(
            understanding=understanding,
            profile=profile,
            source=source,
            hit=hit,
            query_language=query_language,
        )

        quality_metrics = self._quality.estimate(
            text=hit.text,
            title=hit.title,
            heading=hit.heading,
            boilerplate_ratio=hit.boilerplate_ratio,
        )
        quality_penalty = self._quality.ranking_penalty(quality_metrics)
        quality_score = max(0.0, compat.source_quality_score - quality_penalty * 0.3)

        freshness_boost = self._freshness_boost(
            indexed_at or getattr(source, "updated_at", None),
            page_role=(hit.page_role or getattr(profile, "page_role", "") or ""),
            document_type=(hit.document_type or ""),
            semantic_focus=getattr(understanding, "semantic_focus", "") or "",
            legacy_intent=getattr(understanding, "legacy_intent", "") or "",
        )

        # Normalized final score — always populated when any signal exists
        final = (
            _BLEND_SEMANTIC * dense
            + _BLEND_LEXICAL * lexical
            + _BLEND_COMPATIBILITY * compat.compatibility_score
            + _BLEND_QUALITY * quality_score
            + _BLEND_FRESHNESS * freshness_boost
            + min(0.10, max(0.0, metadata_boost))
        )
        signal_present = dense > 0 or lexical > 0 or compat.compatibility_score > 0
        # Floor only for non-negative compatibility — avoid keeping junk alive.
        if signal_present and compat.compatibility_label not in {
            "news_only",
            "marketing_only",
            "historical",
            "irrelevant",
            "adjacent_incompatible",
        }:
            final = max(
                final,
                min(
                    0.12,
                    0.02
                    + 0.05 * compat.confidence_score
                    + 0.03 * max(0.0, metadata_boost),
                ),
            )
        final = min(1.0, max(0.0, final))

        confidence = max(
            compat.confidence_score,
            min(1.0, dense * 0.3 + lexical * 0.2 + compat.compatibility_score * 0.5),
        )

        components = DocumentScoreComponents(
            dense_score=dense,
            lexical_score=lexical,
            metadata_boost=metadata_boost,
            intent_boost=compat.intent_match_score,
            quality_boost=quality_score,
            freshness_boost=freshness_boost,
            source_intelligence_boost=compat.compatibility_score,
            compatibility_score=compat.compatibility_score,
            evidence_score=compat.evidence_score,
            topic_match_score=compat.topic_match_score,
            answerability_score=compat.answerability_score,
            final_score=final,
            confidence=confidence,
        )

        breakdown = {
            "semantic_score": round(dense, 4),
            "lexical_score": round(lexical, 4),
            "compatibility_score": round(compat.compatibility_score, 4),
            "evidence_score": round(compat.evidence_score, 4),
            "intent_match_score": round(compat.intent_match_score, 4),
            "topic_match_score": round(compat.topic_match_score, 4),
            "focus_match_score": round(compat.focus_match_score, 4),
            "quality_score": round(quality_score, 4),
            "answerability_score": round(compat.answerability_score, 4),
            "confidence_score": round(confidence, 4),
            "freshness_boost": round(freshness_boost, 4),
            "metadata_boost": round(metadata_boost, 4),
            "quality_penalty": round(quality_penalty, 4),
            "final_score": round(final, 4),
            "si_incomplete": compat.si_incomplete,
            "si_warning": compat.si_warning,
            "compatibility_label": compat.compatibility_label,
            "signals": compat.signals,
            "query_understanding": understanding.to_dict(),
        }

        doc.score = components
        doc.score_breakdown = breakdown
        doc.ranking_reason = ExplanationBuilder.why_selected(
            doc, understanding=understanding, compatibility=compat, profile=profile
        )

        hit.final_score = final
        hit.score = final
        hit.metadata_boost = metadata_boost
        hit.intent_boost = compat.intent_match_score
        hit.score_breakdown = breakdown
        hit.selection_reason = doc.ranking_reason

        return components, compat

    @staticmethod
    def _aggregate_signal(chunks: list[SearchHit], field: str) -> float:
        if not chunks:
            return 0.0
        values = sorted(
            (max(0.0, float(getattr(chunk, field, 0.0) or 0.0)) for chunk in chunks),
            reverse=True,
        )
        if not values:
            return 0.0
        best = values[0]
        support = sum(values[:3]) / min(3, len(values))
        return min(1.0, best * 0.7 + support * 0.3)

    @staticmethod
    def _enrich_hit_from_profile(hit: SearchHit, profile: SourceProfile) -> None:
        hit.page_role = profile.page_role
        hit.importance = profile.importance
        hit.content_quality = profile.content_quality
        hit.source_canonical = profile.canonical
        hit.source_profile_summary = profile.llm_summary
        hit.source_language = profile.source_language
        hit.document_type = profile.document_type or hit.document_type
        hit.boilerplate_ratio = profile.boilerplate_ratio or hit.boilerplate_ratio
        purpose = ""
        if profile.semantic and isinstance(profile.semantic, dict):
            purpose = str(profile.semantic.get("document_purpose") or "").strip()
        hit.document_purpose = purpose

    def _freshness_boost(
        self,
        indexed_at: datetime | None,
        *,
        page_role: str = "",
        document_type: str = "",
        semantic_focus: str = "",
        legacy_intent: str = "",
    ) -> float:
        weight = float(getattr(self.settings, "ranking_freshness_weight", 0.05) or 0.05)
        if weight <= 0 or indexed_at is None:
            return 0.0
        # Recently reindexed news/campaign must not outrank stable canonical pages
        # on non-news information needs.
        incidental = page_role in {"news", "campaign", "marketing"} or document_type in {
            "news_page",
            "blog_page",
            "blog_post",
            "promotion_page",
            "offer_page",
            "action_page",
        }
        news_need = semantic_focus in {"news", "promotion"} or legacy_intent in {
            "news_query",
            "promotion",
        }
        if incidental and not news_need:
            return 0.0
        now = datetime.now(timezone.utc)
        if indexed_at.tzinfo is None:
            indexed_at = indexed_at.replace(tzinfo=timezone.utc)
        age_days = max(0, (now - indexed_at).days)
        if age_days <= 7:
            return weight
        if age_days <= 30:
            return weight * 0.5
        if age_days <= 90:
            return weight * 0.2
        return 0.0
