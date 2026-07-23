"""Unit tests for document-first retrieval engine components."""
from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.qdrant_service import SearchHit
from app.services.retrieval_engine.config import RETRIEVAL_PROFILES, load_retrieval_profile
from app.services.retrieval_engine.diagnostics_builder import DiagnosticsBuilder
from app.services.retrieval_engine.document_aggregator import DocumentAggregator
from app.services.retrieval_engine.document_reranker import DocumentReranker
from app.services.retrieval_engine.document_scorer import DocumentScorer
from app.services.retrieval_engine.pipeline_state import PipelineStateMachine, StageStatus
from app.services.retrieval_engine.query_understanding import QueryUnderstandingService
from app.services.retrieval_engine.types import DocumentScoreComponents, RankedDocument
from app.services.retrieval_intent_service import RetrievalIntentResult


class _Settings:
    enable_intent_aware_retrieval = True
    enable_source_intelligence = True
    homepage_boost_enabled = True
    homepage_boost_value = 0.1
    title_match_boost = 0.15
    heading_match_boost = 0.15
    ranking_freshness_weight = 0.05
    retrieval_profile = "automatic"


def _hit(
    source_id: int,
    chunk_index: int,
    *,
    dense: float = 0.0,
    lexical: float = 0.0,
    document_type: str = "generic_page",
    url: str = "",
    title: str = "",
    text: str = "Product details and pricing information for customers.",
) -> SearchHit:
    return SearchHit(
        score=0.0,
        source_id=source_id,
        chunk_index=chunk_index,
        title=title or f"Title {source_id}",
        url=url or f"https://example.com/{source_id}",
        source_type="page",
        text=text,
        document_type=document_type,
        dense_score=dense,
        lexical_score=lexical,
    )


def _intent(**kwargs) -> RetrievalIntentResult:
    defaults = dict(
        intent="product_query",
        legacy_intent="product_search",
        answer_strategy="listing",
        confidence=0.8,
    )
    defaults.update(kwargs)
    return RetrievalIntentResult(**defaults)


def test_document_aggregator_groups_by_source():
    chunks = [
        _hit(1, 0, dense=0.8),
        _hit(1, 1, dense=0.5),
        _hit(2, 0, dense=0.7),
    ]
    docs, removed = DocumentAggregator.aggregate(chunks)
    assert len(docs) == 2
    assert removed == 1
    assert docs[0].representative_chunk.chunk_index == 0
    assert docs[0].source_id == 1


def test_document_scorer_populates_final_score_and_breakdown():
    doc = RankedDocument(
        source_id=1,
        url="https://example.com/product",
        title="Product",
        document_type="product_page",
        representative_chunk=_hit(1, 0, dense=0.75, lexical=0.6, document_type="product_page"),
        all_chunks=[_hit(1, 0, dense=0.75, lexical=0.6, document_type="product_page")],
    )
    understanding = QueryUnderstandingService.analyze(
        "product pricing",
        intent_result=_intent(),
        query_language="en",
    )
    scorer = DocumentScorer(_Settings())
    components, _compat = scorer.score_document(
        doc,
        query="product pricing",
        understanding=understanding,
        source=None,
    )
    assert components.final_score > 0
    assert doc.score_breakdown is not None
    assert doc.score_breakdown["final_score"] > 0
    assert doc.representative_chunk.final_score > 0
    assert doc.why_selected == ""  # set by reranker
    assert doc.ranking_reason


def test_document_reranker_explains_selection_and_rejection():
    understanding = QueryUnderstandingService.analyze(
        "available products",
        intent_result=_intent(),
    )
    docs = []
    for i, (dtype, score) in enumerate(
        [("product_page", 0.9), ("blog_page", 0.85), ("news_page", 0.2)]
    ):
        doc = RankedDocument(
            source_id=i + 1,
            url=f"https://example.com/{i}",
            title=f"Doc {i}",
            document_type=dtype,
            representative_chunk=_hit(i + 1, 0, document_type=dtype),
        )
        doc.score = DocumentScoreComponents(final_score=score, dense_score=score)
        doc.score_breakdown = {"final_score": score, "signals": []}
        doc.ranking_reason = "test reason"
        docs.append(doc)

    selected, rejected = DocumentReranker().rerank(
        docs,
        limit=2,
        minimum_score=0.35,
        understanding=understanding,
    )
    assert len(selected) == 2
    assert all(d.why_selected for d in selected)
    assert all(r.why_rejected for r in rejected)


def test_diagnostics_builder_quality_metrics():
    selected = [
        RankedDocument(
            source_id=1,
            url="https://a",
            title="A",
            document_type="product_page",
            representative_chunk=_hit(1, 0),
            score=DocumentScoreComponents(
                dense_score=0.8, lexical_score=0.5, final_score=0.7, confidence=0.75
            ),
        )
    ]
    metrics = DiagnosticsBuilder.build_quality_metrics(
        chunks_retrieved=3,
        documents_found=2,
        documents_after_deduplication=2,
        selected=selected,
        rejected=[],
        duplicate_documents_removed=1,
    )
    assert metrics.documents_sent_to_llm == 1
    assert metrics.avg_final_score > 0


def test_pipeline_state_machine_no_stale_pending():
    sm = PipelineStateMachine()
    sm.start("chunk_retrieval")
    sm.complete("chunk_retrieval")
    sm.start("document_scoring")
    sm.complete("document_scoring")
    stages = sm.to_list()
    assert all(
        s["status"] != StageStatus.PENDING.value
        for s in stages
        if s["stage"] != "context_building"
    )


def test_retrieval_profiles_include_automatic():
    assert "automatic" in RETRIEVAL_PROFILES
    profile = load_retrieval_profile(_Settings())
    assert profile.name == "automatic"


def test_automatic_profile_is_default_when_unset():
    class EmptySettings:
        pass

    profile = load_retrieval_profile(EmptySettings())
    assert profile.name == "automatic"
