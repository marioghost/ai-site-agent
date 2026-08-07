"""Build comprehensive retrieval diagnostics for chat and observability."""
from __future__ import annotations

from app.services.retrieval_engine.types import RankedDocument, RetrievalQualityMetrics


class DiagnosticsBuilder:
    """Assemble retrieval quality metrics and document-level explanations."""

    @staticmethod
    def build_quality_metrics(
        *,
        chunks_retrieved: int,
        documents_found: int,
        documents_after_deduplication: int,
        selected: list[RankedDocument],
        rejected: list[RankedDocument],
        duplicate_documents_removed: int,
        filtered_by_intent: int = 0,
        filtered_by_quality: int = 0,
        filtered_by_minimum_score: int = 0,
    ) -> RetrievalQualityMetrics:
        all_scored = selected + rejected
        avg_sem = (
            sum(d.score.dense_score for d in all_scored) / len(all_scored) if all_scored else 0.0
        )
        avg_lex = (
            sum(d.score.lexical_score for d in all_scored) / len(all_scored) if all_scored else 0.0
        )
        avg_final = (
            sum(d.score.final_score for d in all_scored) / len(all_scored) if all_scored else 0.0
        )
        avg_si = (
            sum(d.score.confidence for d in all_scored) / len(all_scored) if all_scored else 0.0
        )
        return RetrievalQualityMetrics(
            documents_found=documents_found,
            documents_after_deduplication=documents_after_deduplication,
            documents_after_reranking=len(selected),
            documents_sent_to_llm=len(selected),
            chunks_retrieved=chunks_retrieved,
            duplicate_documents_removed=duplicate_documents_removed,
            filtered_by_intent=filtered_by_intent,
            filtered_by_quality=filtered_by_quality,
            filtered_by_minimum_score=filtered_by_minimum_score,
            avg_semantic_score=avg_sem,
            avg_lexical_score=avg_lex,
            avg_final_score=avg_final,
            avg_source_intelligence_confidence=avg_si,
        )

    @staticmethod
    def document_summaries(documents: list[RankedDocument]) -> list[dict]:
        return [doc.to_dict() for doc in documents]

    @staticmethod
    def score_breakdowns(documents: list[RankedDocument]) -> list[dict]:
        out: list[dict] = []
        for doc in documents:
            if doc.score_breakdown:
                out.append(
                    {
                        "url": doc.url,
                        "title": doc.title,
                        "document_type": doc.document_type,
                        **doc.score_breakdown,
                    }
                )
        return out

    @staticmethod
    def rejected_candidates(rejected: list[RankedDocument]) -> list[dict]:
        return [
            {
                "url": doc.url,
                "title": doc.title,
                "document_type": doc.document_type,
                "final_score": round(doc.score.final_score, 4),
                "why_rejected": doc.why_rejected,
                "ranking_reason": doc.ranking_reason,
                "score_breakdown": doc.score_breakdown,
            }
            for doc in rejected[:20]
        ]

    @staticmethod
    def selected_candidates(selected: list[RankedDocument]) -> list[dict]:
        out = []
        for doc in selected:
            breakdown = doc.score_breakdown or {}
            out.append(
                {
                    "url": doc.url,
                    "title": doc.title,
                    "document_type": doc.document_type,
                    "page_role": doc.representative_chunk.page_role,
                    "importance": doc.representative_chunk.importance,
                    "content_quality": doc.representative_chunk.content_quality,
                    "dense_score": round(doc.score.dense_score, 4),
                    "lexical_score": round(doc.score.lexical_score, 4),
                    "metadata_boost": round(doc.score.metadata_boost, 4),
                    "intent_boost": round(doc.score.intent_boost, 4),
                    "quality_boost": round(doc.score.quality_boost, 4),
                    "freshness_boost": round(doc.score.freshness_boost, 4),
                    "final_score": round(doc.score.final_score, 4),
                    "confidence": round(doc.score.confidence, 4),
                    "compatibility_label": breakdown.get("compatibility_label")
                    or "ambiguous",
                    "focus_match_score": breakdown.get("focus_match_score"),
                    "why_selected": doc.why_selected,
                    "ranking_reason": doc.ranking_reason,
                    "score_breakdown": doc.score_breakdown,
                }
            )
        return out
