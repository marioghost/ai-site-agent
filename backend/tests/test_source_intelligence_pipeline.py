"""Tests for Source Intelligence Layer and LLM pipeline optimizations."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import sessionmaker

from tests._dbutil import make_engine
from app.models.settings import Settings
from app.models.source import Source
from app.services.context_builder_service import ContextBuilderService
from app.services.language_resolver_service import detect_query_language
from app.services.llm_options_service import resolve_llm_options
from app.services.polish_policy_service import should_polish
from app.services.qdrant_service import SearchHit
from app.services.source_intelligence_router import SourceIntelligenceRouter
from app.services.source_intelligence_service import SourceIntelligenceService, SourceProfile
from app.schemas.source_intelligence import SourceSemanticProfile


@pytest.fixture()
def db_session():
    engine = make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_source_intelligence_builds_profile_for_indexed_source():
    source = Source(
        url="https://example.com/about-bank/",
        source_type="page",
        status="indexed",
        title="About the company",
        document_type="about_page",
        main_content_text="We provide services across multiple regions.",
        main_content_chars=1200,
        boilerplate_ratio=0.1,
    )
    profile = SourceIntelligenceService.build_profile(source)
    assert profile.document_type == "about_page"
    assert profile.page_role == "organization_overview"
    assert profile.importance >= 70
    assert profile.canonical is True
    assert profile.should_answer_company is True
    assert profile.llm_summary


def test_overview_routing_penalizes_promotion_page():
    settings = MagicMock()
    settings.source_intelligence_importance_threshold = 70
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


def test_overview_routing_boosts_about_page():
    settings = MagicMock()
    settings.source_intelligence_importance_threshold = 70
    settings.prefer_user_language_sources = True
    about = SourceProfile(
        source_id=2,
        url="https://example.com/about-bank/",
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
    assert boost > 0.2
    assert "canonical" in reason or "should_answer" in reason


def test_context_builder_respects_max_total_context_chars():
    hits = [
        SearchHit(
            score=0.9,
            source_id=i,
            chunk_index=0,
            title=f"Page {i}",
            url=f"https://example.com/p{i}",
            source_type="page",
            text="x" * 2000,
        )
        for i in range(5)
    ]
    ctx = ContextBuilderService().build(
        hits, max_pages=5, max_chars_per_source=500, max_total_context_chars=1200
    )
    assert len(ctx.prompt_text) <= 1300


def test_polish_off_by_default():
    settings = Settings(polish_mode="off", enable_ukrainian_polish_pass=False)
    assert should_polish(settings, answer="Short", language="uk", fast_mode=False, generation_ms=1000) is False


def test_auto_polish_skips_short_answers():
    settings = Settings(polish_mode="auto", polish_min_answer_chars=2000)
    assert should_polish(settings, answer="Short answer.", language="uk", fast_mode=False, generation_ms=1000) is False


def test_dynamic_num_ctx_small_prompt():
    settings = Settings(llm_num_ctx_mode="auto", llm_num_predict=512)
    opts = resolve_llm_options(settings, prompt_chars=2000)
    assert opts["num_ctx"] == 4096


def test_dynamic_num_ctx_large_prompt():
    settings = Settings(llm_num_ctx_mode="auto", llm_num_predict=512)
    opts = resolve_llm_options(settings, prompt_chars=15000)
    assert opts["num_ctx"] == 8192


def test_query_language_detection():
    assert detect_query_language("розкажи про банк") == "uk"
    assert detect_query_language("tell me about the company") == "en"


def test_bilingual_dedupe_prefers_query_language():
    uk = SearchHit(
        score=0.8,
        source_id=1,
        chunk_index=0,
        title="Про нас",
        url="https://example.com/uk/about/",
        source_type="page",
        text="UA content",
        source_language="uk",
    )
    en = SearchHit(
        score=0.75,
        source_id=2,
        chunk_index=0,
        title="About",
        url="https://example.com/en/about/",
        source_type="page",
        text="EN content",
        source_language="en",
    )
    kept = ContextBuilderService.dedupe_bilingual_hits([en, uk], "uk")
    assert len(kept) == 1
    assert kept[0].source_language == "uk"


def test_semantic_boost_prefers_product_listing_over_legal():
    product = SourceSemanticProfile(
        main_topic="Deposits",
        document_purpose="product listing",
        document_purpose_confidence=0.9,
        supported_intents=["listing", "product_query", "overview"],
        suitable_for=["list available deposits", "compare deposits"],
        not_suitable_for=["legal disputes", "company overview"],
        confidence=0.85,
    )
    legal = SourceSemanticProfile(
        main_topic="Deposits",
        document_purpose="legal information",
        document_purpose_confidence=0.9,
        suitable_for=["deposit guarantee legal terms"],
        not_suitable_for=["compare deposits", "list available deposits"],
        confidence=0.85,
    )
    query = "What deposit products do you offer?"
    routing = "product"
    intent = "product_query"

    product_boost, product_reason = SourceIntelligenceRouter.semantic_boost(
        product, routing=routing, query=query, query_intent=intent
    )
    legal_boost, legal_reason = SourceIntelligenceRouter.semantic_boost(
        legal, routing=routing, query=query, query_intent=intent
    )
    assert product_boost > legal_boost
    assert "purpose:product listing" in product_reason
    assert "avoid_purpose:legal information" in legal_reason


def test_semantic_boost_for_hit_ranks_product_above_legal():
    settings = MagicMock()
    settings.source_intelligence_importance_threshold = 70
    settings.prefer_user_language_sources = True

    product_profile = SourceProfile(
        source_id=1,
        url="https://example.com/deposits/",
        document_type="product_page",
        page_role="product",
        importance=80,
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
        document_type="legal_page",
        page_role="legal",
        importance=60,
        semantic=SourceSemanticProfile(
            main_topic="Deposits",
            document_purpose="legal information",
            document_purpose_confidence=0.9,
            not_suitable_for=["list available deposits", "compare deposits"],
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
        text="Fixed and savings deposits",
    )
    hit_legal = SearchHit(
        score=0.5,
        source_id=2,
        chunk_index=0,
        title="Deposit Guarantee Fund",
        url=legal_profile.url,
        source_type="page",
        text="Legal deposit protection information",
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


def test_generate_intelligence_updates_source(db_session):
    from app.repositories.settings_repository import SettingsRepository
    from app.services.source_intelligence_generation_service import (
        IntelligenceOptions,
        SourceIntelligenceGenerationService,
    )

    source = Source(
        url="https://example.com/about/",
        source_type="page",
        status="indexed",
        title="About",
        main_content_text="Overview text " * 50,
        main_content_chars=800,
    )
    db_session.add(source)
    db_session.commit()
    settings = SettingsRepository(db_session).get_or_create()
    service = SourceIntelligenceGenerationService(db_session, settings)
    result = service.run(IntelligenceOptions(scope="selected", source_ids=[source.id]))
    db_session.refresh(source)
    assert result["updated_sources"] == 1
    assert source.profile_version
    assert source.importance > 0
