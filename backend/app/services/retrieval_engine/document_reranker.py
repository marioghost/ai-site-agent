"""Document-level reranking with semantic diversity and human explanations."""
from __future__ import annotations

from difflib import SequenceMatcher

from app.models.source import Source
from app.services.retrieval_engine.focus_compatibility import is_negative_compatibility
from app.services.retrieval_engine.explanation_builder import ExplanationBuilder
from app.services.retrieval_engine.query_understanding import QueryUnderstanding
from app.services.retrieval_engine.semantic_compatibility import SemanticCompatibilityResult
from app.services.retrieval_engine.types import RankedDocument
from app.services.source_intelligence_service import SourceIntelligenceService, SourceProfile


_STRICT_FOCI = frozenset(
    {
        "organization_profile",
        "product_specification",
        "rates",
        "eligibility",
        "definition",
        "locator",
        "contact",
    }
)
_ALLOW_NEWS_FOCI = frozenset({"comparison"})  # news/promotion intents handled via answer type


class DocumentReranker:
    """Select top documents and explain why others were rejected."""

    def rerank(
        self,
        documents: list[RankedDocument],
        *,
        limit: int,
        minimum_score: float,
        understanding: QueryUnderstanding,
        sources: dict[int, Source] | None = None,
    ) -> tuple[list[RankedDocument], list[RankedDocument]]:
        if not documents:
            return [], []

        scored = sorted(documents, key=lambda d: d.score.final_score, reverse=True)
        is_broad = understanding.expected_answer_type == "overview" or understanding.ambiguity >= 0.6
        focus = getattr(understanding, "semantic_focus", "") or "general"
        allow_adjacent = (
            understanding.expected_answer_type in {"comparison", "listing"}
            or understanding.legacy_intent in {"news_query"}
            or "promotion" in (understanding.legacy_intent or "")
            or focus in _ALLOW_NEWS_FOCI
        )

        selected: list[RankedDocument] = []
        rejected: list[RankedDocument] = []
        seen_purposes: set[str] = set()
        seen_topics: set[str] = set()
        soft_negatives: list[RankedDocument] = []

        for doc in scored:
            compat = self._compat_from_doc(doc)
            profile = self._profile_for(doc, sources)
            label = compat.compatibility_label

            if (
                not allow_adjacent
                and focus in _STRICT_FOCI
                and is_negative_compatibility(label)
            ):
                # Hard-drop news/marketing; keep adjacent as last-resort pool so we do not
                # empty retrieval when the site lacks a perfect focus page.
                if label in {"news_only", "marketing_only", "historical"}:
                    doc.selected = False
                    reason = f"negative evidence for focus ({focus}:{label})"
                    doc.why_rejected = ExplanationBuilder.why_rejected(
                        doc,
                        understanding=understanding,
                        compatibility=compat,
                        profile=profile,
                        reason_code=reason,
                    )
                    rejected.append(doc)
                    continue
                soft_negatives.append(doc)
                continue

            if doc.score.final_score < minimum_score:
                doc.selected = False
                reason = (
                    f"below minimum score ({doc.score.final_score:.3f} < {minimum_score:.3f})"
                )
                doc.why_rejected = ExplanationBuilder.why_rejected(
                    doc,
                    understanding=understanding,
                    compatibility=compat,
                    profile=profile,
                    reason_code=reason,
                )
                rejected.append(doc)
                continue

            purpose = self._semantic_purpose(doc, profile)
            topic_key = (profile.topics[0] if profile and profile.topics else doc.title or "").lower()

            if is_broad and len(selected) >= limit:
                reason = "overview diversity limit reached"
                doc.selected = False
                doc.why_rejected = ExplanationBuilder.why_rejected(
                    doc,
                    understanding=understanding,
                    compatibility=compat,
                    profile=profile,
                    reason_code=reason,
                )
                rejected.append(doc)
                continue

            overlap = self._content_overlap(doc, selected)

            if (
                is_broad
                and purpose
                and purpose in seen_purposes
                and overlap >= 0.78
                and not (profile and profile.canonical)
                and len(selected) >= max(1, limit // 2)
            ):
                reason = f"duplicate semantic purpose ({purpose})"
                doc.selected = False
                doc.why_rejected = ExplanationBuilder.why_rejected(
                    doc,
                    understanding=understanding,
                    compatibility=compat,
                    profile=profile,
                    reason_code=reason,
                )
                rejected.append(doc)
                continue

            if (
                is_broad
                and topic_key
                and topic_key in seen_topics
                and overlap >= 0.84
                and not (profile and profile.canonical)
            ):
                reason = f"duplicate topic coverage ({topic_key[:48]})"
                doc.selected = False
                doc.why_rejected = ExplanationBuilder.why_rejected(
                    doc,
                    understanding=understanding,
                    compatibility=compat,
                    profile=profile,
                    reason_code=reason,
                )
                rejected.append(doc)
                continue

            if len(selected) >= limit:
                break

            doc.selected = True
            doc.why_selected = ExplanationBuilder.why_selected(
                doc, understanding=understanding, compatibility=compat, profile=profile
            )
            selected.append(doc)
            if purpose:
                seen_purposes.add(purpose)
            if topic_key:
                seen_topics.add(topic_key)

        # Last resort: if strict focus wiped the pool, admit best adjacent (never news/marketing).
        if not selected and soft_negatives and focus in _STRICT_FOCI:
            for doc in soft_negatives:
                if len(selected) >= max(1, min(limit, 2)):
                    break
                compat = self._compat_from_doc(doc)
                profile = self._profile_for(doc, sources)
                doc.selected = True
                doc.why_selected = ExplanationBuilder.why_selected(
                    doc, understanding=understanding, compatibility=compat, profile=profile
                )
                selected.append(doc)
            soft_rejected = [d for d in soft_negatives if d not in selected]
            for doc in soft_rejected:
                doc.selected = False
                compat = self._compat_from_doc(doc)
                profile = self._profile_for(doc, sources)
                doc.why_rejected = ExplanationBuilder.why_rejected(
                    doc,
                    understanding=understanding,
                    compatibility=compat,
                    profile=profile,
                    reason_code=f"negative evidence for focus ({focus}:adjacent_incompatible)",
                )
                rejected.append(doc)
        else:
            for doc in soft_negatives:
                doc.selected = False
                compat = self._compat_from_doc(doc)
                profile = self._profile_for(doc, sources)
                doc.why_rejected = ExplanationBuilder.why_rejected(
                    doc,
                    understanding=understanding,
                    compatibility=compat,
                    profile=profile,
                    reason_code=f"negative evidence for focus ({focus}:adjacent_incompatible)",
                )
                rejected.append(doc)

        # Reject remaining unscored tail.
        selected_ids = {id(d) for d in selected}
        rejected_ids = {id(d) for d in rejected}
        for doc in scored:
            if id(doc) in selected_ids or id(doc) in rejected_ids:
                continue
            if len(selected) < limit and doc.score.final_score >= minimum_score:
                continue
            doc.selected = False
            if not doc.why_rejected:
                compat = self._compat_from_doc(doc)
                profile = self._profile_for(doc, sources)
                doc.why_rejected = ExplanationBuilder.why_rejected(
                    doc,
                    understanding=understanding,
                    compatibility=compat,
                    profile=profile,
                    reason_code="not selected in top documents",
                )
            rejected.append(doc)

        return selected, rejected

    @staticmethod
    def _compat_from_doc(doc: RankedDocument) -> SemanticCompatibilityResult:
        breakdown = doc.score_breakdown or {}
        return SemanticCompatibilityResult(
            compatibility_score=doc.score.compatibility_score,
            evidence_score=doc.score.evidence_score,
            intent_match_score=doc.score.intent_boost,
            topic_match_score=doc.score.topic_match_score,
            focus_match_score=float(breakdown.get("focus_match_score") or 0.0),
            source_quality_score=doc.score.quality_boost,
            answerability_score=doc.score.answerability_score,
            confidence_score=doc.score.confidence,
            compatibility_label=str(breakdown.get("compatibility_label") or "ambiguous"),
            si_incomplete=bool(breakdown.get("si_incomplete")),
            si_warning=str(breakdown.get("si_warning") or ""),
            signals=list(breakdown.get("signals") or []),
        )

    @staticmethod
    def _profile_for(doc: RankedDocument, sources: dict[int, Source] | None) -> SourceProfile | None:
        if not sources:
            return None
        source = sources.get(doc.source_id)
        if source is None:
            return None
        profile = SourceIntelligenceService.profile_from_source(source)
        if profile is None:
            profile = SourceIntelligenceService.build_profile(source)
        return profile

    @staticmethod
    def _semantic_purpose(doc: RankedDocument, profile: SourceProfile | None) -> str:
        semantic = SourceIntelligenceService.semantic_from_profile(profile) if profile else None
        if semantic and semantic.document_purpose:
            return semantic.document_purpose
        return doc.document_type or "unknown"

    @staticmethod
    def apply_to_representative_chunks(selected: list[RankedDocument]) -> list:
        """Return one SearchHit per selected document with full diagnostics."""
        hits = []
        for doc in selected:
            hit = doc.representative_chunk
            hit.final_score = doc.score.final_score
            hit.score = doc.score.final_score
            hit.metadata_boost = doc.score.metadata_boost
            hit.intent_boost = doc.score.intent_boost
            hit.selection_reason = doc.why_selected or doc.ranking_reason
            hit.rejection_reason = ""
            hit.score_breakdown = doc.score_breakdown
            hits.append(hit)
        return hits

    @staticmethod
    def _content_overlap(doc: RankedDocument, selected: list[RankedDocument]) -> float:
        if not selected:
            return 0.0
        sample = DocumentReranker._doc_sample(doc)
        if not sample:
            return 0.0
        best = 0.0
        for item in selected:
            other = DocumentReranker._doc_sample(item)
            if not other:
                continue
            best = max(best, SequenceMatcher(None, sample, other).ratio())
        return best

    @staticmethod
    def _doc_sample(doc: RankedDocument) -> str:
        parts: list[str] = []
        for chunk in doc.all_chunks[:3]:
            text = (chunk.text or "").strip()
            if text:
                parts.append(text[:500])
        if not parts and doc.representative_chunk.text:
            parts.append(doc.representative_chunk.text[:500])
        return "\n".join(parts).lower()
