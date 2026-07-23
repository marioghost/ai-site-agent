"""Shared types for the retrieval engine."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScoreBreakdown:
    dense: float = 0.0
    lexical: float = 0.0
    title: float = 0.0
    heading: float = 0.0
    main_content: float = 0.0
    url: float = 0.0
    document_type: float = 0.0
    content_hint: float = 0.0
    category: float = 0.0
    intent: float = 0.0
    source_intelligence: float = 0.0
    canonical: float = 0.0
    freshness: float = 0.0
    boilerplate_penalty: float = 0.0
    navigation_penalty: float = 0.0
    quality_penalty: float = 0.0
    final: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "dense": round(self.dense, 4),
            "lexical": round(self.lexical, 4),
            "title": round(self.title, 4),
            "heading": round(self.heading, 4),
            "main_content": round(self.main_content, 4),
            "url": round(self.url, 4),
            "document_type": round(self.document_type, 4),
            "content_hint": round(self.content_hint, 4),
            "category": round(self.category, 4),
            "intent": round(self.intent, 4),
            "source_intelligence": round(self.source_intelligence, 4),
            "canonical": round(self.canonical, 4),
            "freshness": round(self.freshness, 4),
            "boilerplate_penalty": round(self.boilerplate_penalty, 4),
            "navigation_penalty": round(self.navigation_penalty, 4),
            "quality_penalty": round(self.quality_penalty, 4),
            "final": round(self.final, 4),
        }


@dataclass
class DocumentQualityMetrics:
    content_length: int = 0
    information_density: float = 0.0
    boilerplate_ratio: float = 0.0
    navigation_ratio: float = 0.0
    template_ratio: float = 0.0
    duplicate_ratio: float = 0.0
    quality_score: float = 1.0

    def to_dict(self) -> dict:
        return {
            "content_length": self.content_length,
            "information_density": round(self.information_density, 3),
            "boilerplate_ratio": round(self.boilerplate_ratio, 3),
            "navigation_ratio": round(self.navigation_ratio, 3),
            "template_ratio": round(self.template_ratio, 3),
            "duplicate_ratio": round(self.duplicate_ratio, 3),
            "quality_score": round(self.quality_score, 3),
        }


@dataclass
class ExpansionResult:
    variants: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    strategy: str = "semantic"
    rejected_terms: list[str] = field(default_factory=list)


@dataclass
class ContextBudget:
    num_ctx: int
    system_tokens: int
    user_query_tokens: int
    answer_reserve_tokens: int
    available_context_tokens: int

    def to_dict(self) -> dict:
        return {
            "num_ctx": self.num_ctx,
            "system_tokens": self.system_tokens,
            "user_query_tokens": self.user_query_tokens,
            "answer_reserve_tokens": self.answer_reserve_tokens,
            "available_context_tokens": self.available_context_tokens,
        }


@dataclass
class DocumentScoreComponents:
    """Weighted score components for a document candidate."""

    dense_score: float = 0.0
    lexical_score: float = 0.0
    metadata_boost: float = 0.0
    intent_boost: float = 0.0
    quality_boost: float = 0.0
    freshness_boost: float = 0.0
    source_intelligence_boost: float = 0.0
    compatibility_score: float = 0.0
    evidence_score: float = 0.0
    topic_match_score: float = 0.0
    answerability_score: float = 0.0
    final_score: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "dense_score": round(self.dense_score, 4),
            "lexical_score": round(self.lexical_score, 4),
            "semantic_score": round(self.dense_score, 4),
            "compatibility_score": round(self.compatibility_score, 4),
            "evidence_score": round(self.evidence_score, 4),
            "intent_match_score": round(self.intent_boost, 4),
            "topic_match_score": round(self.topic_match_score, 4),
            "quality_score": round(self.quality_boost, 4),
            "answerability_score": round(self.answerability_score, 4),
            "metadata_boost": round(self.metadata_boost, 4),
            "freshness_boost": round(self.freshness_boost, 4),
            "source_intelligence_boost": round(self.source_intelligence_boost, 4),
            "final_score": round(self.final_score, 4),
            "confidence_score": round(self.confidence, 4),
        }


@dataclass
class RankedDocument:
    """One document with its representative chunk and full ranking metadata."""

    source_id: int
    url: str
    title: str
    document_type: str
    representative_chunk: "SearchHit"  # forward ref — SearchHit from qdrant_service
    all_chunks: list["SearchHit"] = field(default_factory=list)
    score: DocumentScoreComponents = field(default_factory=DocumentScoreComponents)
    why_selected: str = ""
    why_rejected: str = ""
    ranking_reason: str = ""
    score_breakdown: dict | None = None
    selected: bool = False

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "url": self.url,
            "title": self.title,
            "document_type": self.document_type,
            "dense_score": self.score.dense_score,
            "lexical_score": self.score.lexical_score,
            "semantic_score": self.score.dense_score,
            "compatibility_score": self.score.compatibility_score,
            "evidence_score": self.score.evidence_score,
            "intent_match_score": self.score.intent_boost,
            "topic_match_score": self.score.topic_match_score,
            "quality_score": self.score.quality_boost,
            "final_score": self.score.final_score,
            "confidence": self.score.confidence,
            "why_selected": self.why_selected,
            "why_rejected": self.why_rejected,
            "ranking_reason": self.ranking_reason,
            "score_breakdown": self.score_breakdown,
            "selected": self.selected,
            "chunk_count": len(self.all_chunks),
        }


@dataclass
class RetrievalQualityMetrics:
    documents_found: int = 0
    documents_after_deduplication: int = 0
    documents_after_reranking: int = 0
    documents_sent_to_llm: int = 0
    chunks_retrieved: int = 0
    duplicate_documents_removed: int = 0
    filtered_by_intent: int = 0
    filtered_by_quality: int = 0
    filtered_by_minimum_score: int = 0
    avg_semantic_score: float = 0.0
    avg_lexical_score: float = 0.0
    avg_final_score: float = 0.0
    avg_source_intelligence_confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "documents_found": self.documents_found,
            "documents_after_deduplication": self.documents_after_deduplication,
            "documents_after_reranking": self.documents_after_reranking,
            "documents_sent_to_llm": self.documents_sent_to_llm,
            "chunks_retrieved": self.chunks_retrieved,
            "duplicate_documents_removed": self.duplicate_documents_removed,
            "filtered_by_intent": self.filtered_by_intent,
            "filtered_by_quality": self.filtered_by_quality,
            "filtered_by_minimum_score": self.filtered_by_minimum_score,
            "avg_semantic_score": round(self.avg_semantic_score, 4),
            "avg_lexical_score": round(self.avg_lexical_score, 4),
            "avg_final_score": round(self.avg_final_score, 4),
            "avg_source_intelligence_confidence": round(
                self.avg_source_intelligence_confidence, 4
            ),
        }
