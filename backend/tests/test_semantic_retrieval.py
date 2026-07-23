"""Semantic retrieval ranking — no hardcoded category weights."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

from app.schemas.source_intelligence import SourceSemanticProfile
from app.services.qdrant_service import SearchHit
from app.services.retrieval_engine.document_reranker import DocumentReranker
from app.services.retrieval_engine.document_scorer import DocumentScorer
from app.services.retrieval_engine.query_understanding import QueryUnderstandingService
from app.services.retrieval_engine.semantic_compatibility import SemanticCompatibilityScorer
from app.services.retrieval_engine.types import DocumentScoreComponents, RankedDocument
from app.services.retrieval_intent_service import RetrievalIntentResult
from app.services.source_intelligence_service import SourceIntelligenceService, SourceProfile


class _Settings:
    title_match_boost = 0.15
    heading_match_boost = 0.15
    ranking_freshness_weight = 0.05


def _source(
    source_id: int,
    *,
    title: str,
    url: str,
    document_type: str = "generic_page",
    semantic: dict | None = None,
    should_answer_product: bool = False,
    should_answer_company: bool = False,
    canonical: bool = False,
    content_quality: int = 75,
    importance: int = 60,
    profile_version: str = "v2",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=source_id,
        url=url,
        title=title,
        document_type=document_type,
        page_role="generic",
        importance=importance,
        canonical=canonical,
        content_quality=content_quality,
        boilerplate_ratio=0.1,
        site_section="general",
        topics_json=json.dumps(["кредити", "credits"]),
        entity_types_json="[]",
        should_answer_general=False,
        should_answer_product=should_answer_product,
        should_answer_support=False,
        should_answer_company=should_answer_company,
        llm_summary=title,
        keywords_json=json.dumps(["кредит", "credit"]),
        intelligence_json=json.dumps(semantic or {}, ensure_ascii=False),
        profile_confidence=0.85,
        profile_version=profile_version,
        source_language="uk",
        updated_at=None,
    )


def _listing_intent() -> RetrievalIntentResult:
    return RetrievalIntentResult(
        intent="product_query",
        legacy_intent="listing",
        matched_topic=None,
        answer_strategy="listing",
        confidence=0.85,
    )


def _hit(source_id: int, *, dense: float, lexical: float, title: str, text: str) -> SearchHit:
    return SearchHit(
        score=0.0,
        source_id=source_id,
        chunk_index=0,
        title=title,
        url=f"https://bank.example/credits/{source_id}",
        source_type="page",
        text=text,
        document_type="generic_page",
        dense_score=dense,
        lexical_score=lexical,
    )


def test_listing_query_prefers_product_listing_over_blog():
    query = "які кредити є?"
    understanding = QueryUnderstandingService.analyze(
        query,
        intent_result=_listing_intent(),
        query_language="uk",
    )
    assert understanding.expected_answer_type == "listing"

    product_source = _source(
        1,
        title="Кредити на енергозбереження",
        url="https://bank.example/credits/energy",
        should_answer_product=True,
        semantic={
            "main_topic": "кредити",
            "main_topic_confidence": 0.9,
            "document_purpose": "product listing",
            "document_purpose_confidence": 0.92,
            "supported_intents": ["listing", "product_query"],
            "suitable_for": ["available credit products", "product list"],
            "not_suitable_for": ["conceptual explanation"],
            "confidence": 0.88,
        },
    )
    blog_source = _source(
        2,
        title="Кредит чи розтермінування",
        url="https://bank.example/blog/credit-vs-installment",
        semantic={
            "main_topic": "кредит",
            "main_topic_confidence": 0.7,
            "document_purpose": "news",
            "document_purpose_confidence": 0.8,
            "supported_intents": ["topic_overview"],
            "suitable_for": ["conceptual explanation"],
            "not_suitable_for": ["product list"],
            "confidence": 0.75,
        },
    )

    product_doc = RankedDocument(
        source_id=1,
        url=product_source.url,
        title=product_source.title,
        document_type="product_page",
        representative_chunk=_hit(
            1,
            dense=0.72,
            lexical=0.55,
            title=product_source.title,
            text="Перелік кредитів: енергозбереження, авто, житло.",
        ),
    )
    blog_doc = RankedDocument(
        source_id=2,
        url=blog_source.url,
        title=blog_source.title,
        document_type="blog_page",
        representative_chunk=_hit(
            2,
            dense=0.78,
            lexical=0.62,
            title=blog_source.title,
            text="Пояснюємо різницю між кредитом і розтермінуванням.",
        ),
    )

    scorer = DocumentScorer(_Settings())
    scorer.score_document(
        product_doc,
        query=query,
        understanding=understanding,
        source=product_source,
        query_language="uk",
    )
    scorer.score_document(
        blog_doc,
        query=query,
        understanding=understanding,
        source=blog_source,
        query_language="uk",
    )

    assert product_doc.score.final_score > blog_doc.score.final_score
    assert product_doc.score.compatibility_score > blog_doc.score.compatibility_score
    assert product_doc.ranking_reason
    assert blog_doc.ranking_reason


def test_overview_query_prefers_canonical_about_page():
    query = "про компанію"
    understanding = QueryUnderstandingService.analyze(
        query,
        intent_result=RetrievalIntentResult(
            intent="entity_overview",
            legacy_intent="entity_overview",
            is_broad=True,
            answer_strategy="overview",
            confidence=0.8,
        ),
        query_language="uk",
    )
    assert understanding.expected_answer_type == "overview"

    about = _source(
        10,
        title="Про банк",
        url="https://bank.example/about",
        should_answer_company=True,
        canonical=True,
        semantic={
            "main_topic": "банк",
            "document_purpose": "about company",
            "document_purpose_confidence": 0.9,
            "supported_intents": ["entity_overview"],
            "confidence": 0.9,
        },
    )
    news = _source(
        11,
        title="Новини банку",
        url="https://bank.example/news/1",
        semantic={
            "main_topic": "банк",
            "document_purpose": "news",
            "document_purpose_confidence": 0.85,
            "confidence": 0.8,
        },
    )

    about_doc = RankedDocument(
        source_id=10,
        url=about.url,
        title=about.title,
        document_type="about_page",
        representative_chunk=_hit(10, dense=0.6, lexical=0.5, title=about.title, text="Про нас"),
    )
    news_doc = RankedDocument(
        source_id=11,
        url=news.url,
        title=news.title,
        document_type="news_page",
        representative_chunk=_hit(11, dense=0.65, lexical=0.55, title=news.title, text="News"),
    )

    scorer = DocumentScorer(_Settings())
    scorer.score_document(about_doc, query=query, understanding=understanding, source=about)
    scorer.score_document(news_doc, query=query, understanding=understanding, source=news)

    assert about_doc.score.final_score > news_doc.score.final_score


def test_missing_source_intelligence_lowers_confidence():
    understanding = QueryUnderstandingService.analyze(
        "products",
        intent_result=_listing_intent(),
    )
    compat = SemanticCompatibilityScorer().score(
        understanding=understanding,
        profile=None,
        source=None,
        hit=_hit(1, dense=0.5, lexical=0.4, title="X", text="text"),
    )
    assert compat.si_incomplete
    assert compat.confidence_score < 0.5
    assert compat.compatibility_score < 0.3


def test_incomplete_semantic_profile_reduces_compatibility():
    understanding = QueryUnderstandingService.analyze(
        "products",
        intent_result=_listing_intent(),
    )
    source = _source(
        3,
        title="Generic",
        url="https://example.com/x",
        semantic={"confidence": 0.1},
        content_quality=40,
        importance=30,
        canonical=False,
    )
    profile = SourceIntelligenceService.profile_from_source(source)
    compat = SemanticCompatibilityScorer().score(
        understanding=understanding,
        profile=profile,
        source=source,
        hit=_hit(3, dense=0.5, lexical=0.4, title="Generic", text="text"),
    )
    assert compat.si_incomplete
    assert compat.compatibility_score < 0.55


def test_repeated_chunks_deduplicated_in_aggregation():
    from app.services.retrieval_engine.document_aggregator import DocumentAggregator

    hit = _hit(1, dense=0.8, lexical=0.5, title="A", text="same text chunk")
    dup = _hit(1, dense=0.8, lexical=0.5, title="A", text="same text chunk")
    docs, removed = DocumentAggregator.aggregate([hit, dup, hit])
    assert len(docs) == 1
    assert removed >= 1


def test_final_score_and_diagnostics_always_populated():
    query = "які кредити є?"
    understanding = QueryUnderstandingService.analyze(query, intent_result=_listing_intent())
    source = _source(
        5,
        title="Кредити",
        url="https://bank.example/credits",
        should_answer_product=True,
        semantic={
            "main_topic": "кредити",
            "document_purpose": "product listing",
            "document_purpose_confidence": 0.9,
            "confidence": 0.85,
        },
    )
    doc = RankedDocument(
        source_id=5,
        url=source.url,
        title=source.title,
        document_type="product_page",
        representative_chunk=_hit(5, dense=0.7, lexical=0.5, title=source.title, text="list"),
    )
    DocumentScorer(_Settings()).score_document(
        doc,
        query=query,
        understanding=understanding,
        source=source,
        query_language="uk",
    )
    selected, rejected = DocumentReranker().rerank(
        [doc],
        limit=1,
        minimum_score=0.1,
        understanding=understanding,
        sources={5: source},
    )
    assert selected[0].score.final_score > 0
    assert selected[0].score_breakdown is not None
    assert selected[0].why_selected
    assert selected[0].why_rejected == ""

    low = RankedDocument(
        source_id=6,
        url="https://bank.example/blog",
        title="Blog",
        document_type="blog_page",
        representative_chunk=_hit(6, dense=0.2, lexical=0.1, title="Blog", text="blog"),
    )
    low.score = DocumentScoreComponents(final_score=0.05)
    low.score_breakdown = {"final_score": 0.05, "signals": []}
    _, rejected = DocumentReranker().rerank(
        [doc, low],
        limit=1,
        minimum_score=0.2,
        understanding=understanding,
        sources={5: source},
    )
    assert rejected
    assert all(r.why_rejected for r in rejected)


def test_config_module_has_no_document_type_weight_table():
    import inspect

    from app.services.retrieval_engine import config

    source = inspect.getsource(config)
    assert "product_page" not in source
    assert "blog_page" not in source
    assert "DEFAULT_DOCUMENT_PRIORITIES" not in source
    assert "DEFAULT_SCORING_WEIGHTS" not in source


def test_semantic_profile_roundtrip():
    semantic = SourceSemanticProfile(
        main_topic="кредити",
        document_purpose="product listing",
        supported_intents=["listing"],
        confidence=0.9,
    )
    profile = SourceProfile(
        source_id=1,
        url="https://example.com",
        semantic=semantic.to_storage_dict(),
        should_answer_product=True,
        content_quality=80,
    )
    parsed = SourceIntelligenceService.semantic_from_profile(profile)
    assert parsed is not None
    assert parsed.document_purpose == "product listing"


def test_router_overview_penalizes_promotion_without_hardcoded_types():
    from unittest.mock import MagicMock

    from app.services.source_intelligence_router import SourceIntelligenceRouter

    settings = MagicMock()
    settings.prefer_user_language_sources = True
    promo = SourceProfile(
        source_id=1,
        url="https://example.com/actions/cashback",
        document_type="promotion_page",
        page_role="campaign",
        importance=20,
        canonical=False,
        content_quality=40,
    )
    hit = SearchHit(
        score=0.5,
        source_id=1,
        chunk_index=0,
        title="Cashback",
        url=promo.url,
        source_type="page",
        text="Bonus offer",
    )
    boost, _ = SourceIntelligenceRouter.boost_for_hit(
        hit, promo, routing="overview", settings=settings
    )
    assert boost < 0


def test_router_overview_boosts_canonical_about_page():
    from unittest.mock import MagicMock

    from app.services.source_intelligence_router import SourceIntelligenceRouter

    settings = MagicMock()
    settings.prefer_user_language_sources = True
    about = SourceProfile(
        source_id=2,
        url="https://example.com/about/",
        document_type="about_page",
        page_role="organization_overview",
        importance=92,
        canonical=True,
        content_quality=88,
        should_answer_company=True,
    )
    hit = SearchHit(
        score=0.5,
        source_id=2,
        chunk_index=0,
        title="About",
        url=about.url,
        source_type="page",
        text="Company overview",
    )
    boost, reason = SourceIntelligenceRouter.boost_for_hit(
        hit, about, routing="overview", settings=settings
    )
    assert boost > 0
    assert "canonical" in reason


def test_router_semantic_listing_beats_legal():
    from unittest.mock import MagicMock

    from app.services.source_intelligence_router import SourceIntelligenceRouter

    settings = MagicMock()
    settings.prefer_user_language_sources = True
    product_profile = SourceProfile(
        source_id=1,
        url="https://example.com/deposits/",
        should_answer_product=True,
        semantic=SourceSemanticProfile(
            main_topic="Deposits",
            document_purpose="product listing",
            document_purpose_confidence=0.9,
            supported_intents=["listing", "product_query"],
            suitable_for=["list available deposits"],
            confidence=0.85,
        ).to_storage_dict(),
    )
    legal_profile = SourceProfile(
        source_id=2,
        url="https://example.com/deposit-guarantee/",
        semantic=SourceSemanticProfile(
            main_topic="Deposits",
            document_purpose="legal information",
            document_purpose_confidence=0.9,
            not_suitable_for=["list available deposits"],
            confidence=0.85,
        ).to_storage_dict(),
    )
    query = "What deposit products do you offer?"
    hit_product = SearchHit(
        score=0.5,
        source_id=1,
        chunk_index=0,
        title="Deposits",
        url=product_profile.url,
        source_type="page",
        text="Fixed deposits",
    )
    hit_legal = SearchHit(
        score=0.5,
        source_id=2,
        chunk_index=0,
        title="Deposit Guarantee",
        url=legal_profile.url,
        source_type="page",
        text="Legal info",
    )
    product_boost, _ = SourceIntelligenceRouter.boost_for_hit(
        hit_product,
        product_profile,
        routing="product",
        settings=settings,
        query=query,
        query_intent="product_query",
    )
    legal_boost, _ = SourceIntelligenceRouter.boost_for_hit(
        hit_legal,
        legal_profile,
        routing="product",
        settings=settings,
        query=query,
        query_intent="product_query",
    )
    assert product_boost > legal_boost


def test_pipeline_service_has_no_overview_hardcode():
    import inspect

    from app.services import retrieval_pipeline_service as mod

    source = inspect.getsource(mod)
    assert "PRIMARY_OVERVIEW_DOCUMENT_TYPES" not in source
    assert "OVERVIEW_DEPRIORITIZED" not in source
    assert "career" not in source.lower()


def test_intent_retrieval_boosts_module_removed():
    import importlib.util

    assert importlib.util.find_spec("app.services.intent_retrieval_boosts") is None


def test_router_has_no_hardcoded_document_type_tables():
    import inspect

    from app.services import source_intelligence_router as mod

    source = inspect.getsource(mod)
    assert "PRIMARY_OVERVIEW_DOCUMENT_TYPES" not in source
    assert "PREFERRED_PURPOSES" not in source
    assert "career" not in source.lower()
    assert "blog_page" not in source
