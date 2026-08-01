"""Tests for profile-driven broad-query handling (RFC-100 Step 009).

Validates production document-first retrieval architecture — not legacy
HybridRetrievalService chunk-first fusion or boost tables.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.models.settings import Settings
from app.schemas.knowledge_profile import AppliedKnowledgeConfig
from app.services.broad_question_service import BroadQuestionService
from app.services.canonical_source_service import CanonicalSourceService
from app.services.document_type_service import detect_document_type
from app.services.knowledge_profile_service import PRESETS
from app.services.qdrant_service import SearchHit
from app.services.query_intent_service import QueryIntentService
from app.services.retrieval_engine.document_aggregator import DocumentAggregator
from app.services.retrieval_engine.document_reranker import DocumentReranker
from app.services.retrieval_engine.document_scorer import DocumentScorer
from app.services.retrieval_engine.pipeline import DocumentRetrievalResult
from app.services.retrieval_engine.query_understanding import QueryUnderstandingService
from app.services.retrieval_engine.types import DocumentScoreComponents, RankedDocument, RetrievalQualityMetrics
from app.services.retrieval_intent_service import RetrievalIntentResult, RetrievalIntentService

pytestmark = pytest.mark.unit


def _overview_intent(*, broad: bool = True) -> RetrievalIntentResult:
    return RetrievalIntentResult(
        intent="entity_overview",
        legacy_intent="entity_overview",
        answer_strategy="overview",
        is_broad=broad,
    )


def _hit(
    source_id: int,
    chunk_index: int = 0,
    *,
    document_type: str = "generic_page",
    title: str = "Page",
    url: str = "",
    text: str = "Organization overview content.",
    dense: float = 0.5,
    lexical: float = 0.2,
    heading: str = "",
) -> SearchHit:
    return SearchHit(
        score=0.0,
        source_id=source_id,
        chunk_index=chunk_index,
        title=title,
        url=url or f"https://example.com/{source_id}",
        source_type="page",
        text=text,
        heading=heading,
        document_type=document_type,
        dense_score=dense,
        lexical_score=lexical,
    )


def _ranked_doc(
    source_id: int,
    *,
    document_type: str,
    final_score: float,
    title: str | None = None,
) -> RankedDocument:
    hit = _hit(
        source_id,
        document_type=document_type,
        title=title or document_type.replace("_", " ").title(),
    )
    doc = RankedDocument(
        source_id=source_id,
        url=hit.url,
        title=hit.title,
        document_type=document_type,
        representative_chunk=hit,
        all_chunks=[hit],
    )
    doc.score = DocumentScoreComponents(final_score=final_score, dense_score=final_score)
    doc.score_breakdown = {
        "final_score": final_score,
        "compatibility_score": 0.4,
        "signals": [],
    }
    doc.ranking_reason = "semantic retrieval signals"
    return doc


def test_entity_brand_query_with_configured_alias():
    profile = PRESETS["generic_corporate"].model_copy(deep=True)
    profile.organization_name = "Acme Corporation"
    profile.organization_aliases = ["acmecorp", "acme corp"]
    assert QueryIntentService.classify("acmecorp", profile=profile) == "entity_overview"
    assert QueryIntentService.classify("info about acmecorp", profile=profile) == "entity_overview"


def test_topic_intents_from_profile():
    profile = PRESETS["ecommerce"]
    assert QueryIntentService.classify("delivery", profile=profile) == "topic_overview"
    assert QueryIntentService.classify("returns policy", profile=profile) == "topic_overview"


def test_document_type_from_profile_rules():
    profile = PRESETS["generic_corporate"]
    assert (
        detect_document_type(
            url="https://example.com/about-us",
            title="About us",
            profile=profile,
        )
        == "about_page"
    )


def test_broad_overview_query_detected_by_retrieval_intent():
    profile = PRESETS["generic_corporate"].model_copy(deep=True)
    profile.organization_name = "Acme Corporation"
    result = RetrievalIntentService.classify("tell me about Acme Corporation", profile=profile)
    assert result.legacy_intent == "entity_overview"
    assert result.is_broad is True
    assert BroadQuestionService.is_broad_question("tell me about the company", profile=profile)


def test_news_deprioritized_for_entity_overview():
    """Canonical selection prefers overview evidence over high-scoring news pages."""
    settings = Settings(
        enable_canonical_source_selection=True,
        enable_news_deprioritization_for_overview_queries=True,
    )
    profile = PRESETS["generic_corporate"]
    about = SearchHit(
        score=0.62,
        source_id=1,
        chunk_index=0,
        title="About",
        url="https://example.com/about",
        source_type="page",
        text="Example company overview",
        document_type="about_page",
        final_score=0.62,
    )
    news = SearchHit(
        score=0.88,
        source_id=2,
        chunk_index=0,
        title="News",
        url="https://example.com/news/1",
        source_type="page",
        text="Company mentioned in news",
        document_type="news_page",
        final_score=0.88,
    )
    selected = CanonicalSourceService.select_context(
        [news, about], "entity_overview", top_k=2, settings=settings, profile=profile
    )
    assert selected[0].document_type == "about_page"
    assert news.excluded_as_news is True


def test_document_aggregator_collapses_duplicate_source_chunks_for_broad_query():
    """Multiple chunks from one source must not dominate document candidates."""
    chunks = [
        _hit(1, document_type="about_page", title="About", text="Company overview", lexical=0.9),
        _hit(
            1,
            chunk_index=1,
            document_type="about_page",
            title="About",
            text="Mission statement",
            lexical=0.5,
        ),
        _hit(
            2,
            document_type="news_page",
            title="News",
            text="Promotional news mention",
            lexical=0.85,
        ),
    ]
    documents, removed = DocumentAggregator.aggregate(chunks)
    assert len(documents) == 2
    assert removed == 1
    assert documents[0].representative_chunk.document_type == "about_page"


def test_document_scorer_does_not_apply_legacy_document_type_boost_tables():
    """Equal retrieval signals must not be skewed by legacy boost-table mechanics."""
    settings = Settings(enable_intent_aware_retrieval=True)
    understanding = QueryUnderstandingService.analyze(
        "tell me about the company",
        intent_result=_overview_intent(),
    )
    scorer = DocumentScorer(settings)

    about_doc = RankedDocument(
        source_id=1,
        url="https://example.com/about",
        title="About",
        document_type="about_page",
        representative_chunk=_hit(1, document_type="about_page"),
        all_chunks=[_hit(1, document_type="about_page")],
    )
    news_doc = RankedDocument(
        source_id=2,
        url="https://example.com/news",
        title="News",
        document_type="news_page",
        representative_chunk=_hit(2, document_type="news_page"),
        all_chunks=[_hit(2, document_type="news_page")],
    )

    about_components, _ = scorer.score_document(
        about_doc, query="tell me about the company", understanding=understanding
    )
    news_components, _ = scorer.score_document(
        news_doc, query="tell me about the company", understanding=understanding
    )

    assert about_doc.score_breakdown is not None
    assert news_doc.score_breakdown is not None
    assert "compatibility_score" in about_doc.score_breakdown
    assert about_components.final_score == news_components.final_score


def test_document_reranker_explains_broad_overview_selection():
    understanding = QueryUnderstandingService.analyze(
        "tell me about the company",
        intent_result=_overview_intent(),
    )
    about = _ranked_doc(1, document_type="about_page", final_score=0.72, title="About us")
    promo = _ranked_doc(2, document_type="promotion_page", final_score=0.88, title="Summer promo")
    blog = _ranked_doc(3, document_type="blog_page", final_score=0.55, title="Company blog")

    selected, rejected = DocumentReranker().rerank(
        [promo, about, blog],
        limit=2,
        minimum_score=0.35,
        understanding=understanding,
    )

    assert len(selected) == 2
    assert all(doc.why_selected for doc in selected)
    assert all(doc.score_breakdown for doc in selected)
    assert any(doc.document_type == "about_page" for doc in selected)
    assert all(doc.why_rejected for doc in rejected)


def test_retrieval_pipeline_records_broad_overview_diagnostics(monkeypatch):
    """RetrievalPipelineService surfaces broad intent via document-first diagnostics."""
    from app.services.retrieval_pipeline_service import RetrievalPipelineService

    about_hit = _hit(
        1,
        document_type="about_page",
        title="About",
        text="Company overview for broad query.",
        dense=0.7,
        lexical=0.6,
    )
    about_hit.final_score = 0.72
    selected_doc = _ranked_doc(1, document_type="about_page", final_score=0.72)
    selected_doc.representative_chunk = about_hit
    selected_doc.why_selected = "overview evidence selected"
    quality = RetrievalQualityMetrics(
        documents_found=1,
        documents_after_deduplication=1,
        documents_after_reranking=1,
        documents_sent_to_llm=1,
        chunks_retrieved=2,
        duplicate_documents_removed=1,
        avg_final_score=0.72,
    )

    class _FakeDocumentPipeline:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, **kwargs):
            return DocumentRetrievalResult(
                selected_hits=[about_hit],
                all_documents=[selected_doc],
                selected_documents=[selected_doc],
                rejected_documents=[],
                quality_metrics=quality,
                pipeline_stages=[
                    {"stage": "chunk_retrieval", "status": "completed"},
                    {"stage": "document_aggregation", "status": "completed"},
                    {"stage": "document_scoring", "status": "completed"},
                    {"stage": "document_reranking", "status": "completed"},
                ],
                chunk_debug={"match_query": "company & overview"},
            )

    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.DocumentFirstRetrievalPipeline",
        _FakeDocumentPipeline,
    )
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.evidence_assembly_enabled",
        lambda: False,
    )

    settings = Settings(
        top_k=5,
        enable_intent_aware_retrieval=True,
        enable_query_expansion=False,
        enable_broad_question_mode=True,
        enable_canonical_source_selection=False,
        enable_context_builder=False,
    )
    pipeline = RetrievalPipelineService(MagicMock(), settings, MagicMock(), MagicMock())
    result = pipeline.run("tell me about the company", "tell me about the company")

    assert result.intent_result.legacy_intent == "entity_overview"
    assert result.diagnostics.is_broad is True
    assert result.diagnostics.retrieval_pipeline_stages
    assert result.diagnostics.quality_metrics is not None
    assert result.diagnostics.category_boosts_applied == []
    assert result.diagnostics.score_breakdowns
    assert result.hits[0].document_type == "about_page"
    assert isinstance(result.applied_config, AppliedKnowledgeConfig)
