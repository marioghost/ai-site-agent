"""Document-first retrieval pipeline — production RAG architecture."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.models.source import Source
from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.content_signals import token_set
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService, SearchHit
from app.services.rag_planning.contracts import PlannerDecision
from app.services.retrieval_engine.diagnostics_builder import DiagnosticsBuilder
from app.services.retrieval_engine.document_aggregator import DocumentAggregator
from app.services.retrieval_engine.document_reranker import DocumentReranker
from app.services.retrieval_engine.document_scorer import DocumentScorer
from app.services.retrieval_engine.pipeline_state import PipelineStateMachine
from app.services.retrieval_engine.retrieval_profiler import RetrievalProfiler
from app.services.retrieval_engine.retrievers import HybridChunkRetriever
from app.services.retrieval_engine.types import RankedDocument, RetrievalQualityMetrics
from app.services.retrieval_intent_service import RetrievalIntentResult


@dataclass
class DocumentRetrievalResult:
    """Output of document-first retrieval before context building."""

    selected_hits: list[SearchHit]
    all_documents: list[RankedDocument]
    selected_documents: list[RankedDocument]
    rejected_documents: list[RankedDocument]
    quality_metrics: RetrievalQualityMetrics
    pipeline_stages: list[dict] = field(default_factory=list)
    chunk_debug: dict | None = None
    retrieval_ms: int = 0
    evidence_assembly_path: str | None = None


class DocumentFirstRetrievalPipeline:
    """
    Document-first RAG retrieval:

    Embedding/Lexical search → top chunks → group by document →
    best chunk per document → semantic scoring → reranking → top documents.
    """

    def __init__(
        self,
        db: Session,
        settings: Settings,
        embedding: EmbeddingService,
        qdrant: QdrantService,
    ) -> None:
        self.db = db
        self.settings = settings
        self.chunk_retriever = HybridChunkRetriever(db, settings, embedding, qdrant)
        self.aggregator = DocumentAggregator()
        self.reranker = DocumentReranker()

    def run(
        self,
        *,
        query: str,
        normalized: str,
        intent_result: RetrievalIntentResult,
        profile: KnowledgeProfile,
        planner_decision: PlannerDecision,
        query_vector: list[float] | None = None,
        expansion_terms: list[str] | None = None,
        query_language: str = "unknown",
    ) -> DocumentRetrievalResult:
        t0 = perf_counter()
        state = PipelineStateMachine()
        s = self.settings

        strategy = planner_decision.retrieval_strategy
        budget = planner_decision.retrieval_budget
        top_k_dense = budget.chunk_pool_size
        top_k_lexical = budget.chunk_pool_size
        minimum_score = strategy.minimum_score
        rerank_limit = budget.rerank_limit
        profile_name = strategy.profile_name
        understanding = planner_decision.understanding
        if understanding is None:
            raise ValueError("planner_decision.understanding is required for retrieval")

        state.start("intent_detection")
        legacy_intent = intent_result.legacy_intent
        retrieval_intent = intent_result.intent
        state.complete(
            "intent_detection",
            detail=f"{retrieval_intent} → {understanding.expected_answer_type}",
        )

        state.start("query_expansion")
        if expansion_terms:
            state.complete("query_expansion", detail=f"{len(expansion_terms)} terms")
        else:
            state.skip("query_expansion", detail="disabled or empty")

        state.start("chunk_retrieval")
        chunks, chunk_debug = self.chunk_retriever.retrieve(
            normalized_query=normalized,
            top_k_dense=top_k_dense,
            top_k_lexical=top_k_lexical,
            similarity_threshold=s.similarity_threshold,
            query_vector=query_vector,
            expansion_terms=expansion_terms,
            profile=profile,
            query_intent=legacy_intent,
        )
        state.complete(
            "chunk_retrieval",
            detail=f"{len(chunks)} chunks (profile={profile_name}, pool={top_k_dense})",
        )

        state.start("document_aggregation")
        documents, dup_removed = self.aggregator.aggregate(chunks)
        state.complete(
            "document_aggregation",
            detail=f"{len(documents)} documents, {dup_removed} dup chunks removed",
        )

        state.start("document_scoring")
        scorer = DocumentScorer(s)
        sources = self._load_sources([d.source_id for d in documents])
        query_tokens = token_set(normalized)
        filtered_by_quality = 0
        for doc in documents:
            src = sources.get(doc.source_id)
            scorer.score_document(
                doc,
                query=query,
                understanding=understanding,
                query_tokens=query_tokens,
                source=src,
                query_language=query_language,
                indexed_at=getattr(src, "updated_at", None) if src else None,
            )
            if doc.score.quality_boost <= 0 and doc.representative_chunk.boilerplate_ratio > 0.7:
                filtered_by_quality += 1
        documents.sort(key=lambda d: d.score.final_score, reverse=True)
        state.complete("document_scoring", detail=f"{len(documents)} scored")

        state.start("source_intelligence")
        state.complete(
            "source_intelligence",
            detail="semantic compatibility integrated in document scoring",
        )

        state.start("document_reranking")
        if s.enable_reranking:
            selected, rejected = self.reranker.rerank(
                documents,
                limit=rerank_limit,
                minimum_score=minimum_score,
                understanding=understanding,
                sources=sources,
            )
        else:
            selected = documents[:rerank_limit]
            rejected = documents[rerank_limit:]
            for doc in selected:
                doc.selected = True
                doc.why_selected = doc.ranking_reason or "reranking disabled — top score"
                doc.why_rejected = ""
            for doc in rejected:
                doc.selected = False
                doc.why_rejected = "reranking disabled — below top limit"

        filtered_by_min = sum(
            1
            for d in rejected
            if d.why_rejected.startswith("score too low")
            or "below minimum score" in d.why_rejected
        )
        selected_hits = self.reranker.apply_to_representative_chunks(selected)
        state.complete(
            "document_reranking",
            detail=f"{len(selected)} selected, {len(rejected)} rejected",
        )

        quality = DiagnosticsBuilder.build_quality_metrics(
            chunks_retrieved=len(chunks),
            documents_found=len(documents),
            documents_after_deduplication=len(documents),
            selected=selected,
            rejected=rejected,
            duplicate_documents_removed=dup_removed,
            filtered_by_quality=filtered_by_quality,
            filtered_by_minimum_score=filtered_by_min,
        )

        return DocumentRetrievalResult(
            selected_hits=selected_hits,
            all_documents=documents,
            selected_documents=selected,
            rejected_documents=rejected,
            quality_metrics=quality,
            pipeline_stages=state.to_list(),
            chunk_debug=chunk_debug.to_dict(),
            retrieval_ms=int((perf_counter() - t0) * 1000),
        )

    def _load_sources(self, source_ids: list[int]) -> dict[int, Source]:
        if not source_ids:
            return {}
        rows = self.db.execute(select(Source).where(Source.id.in_(source_ids))).scalars().all()
        return {s.id: s for s in rows}
