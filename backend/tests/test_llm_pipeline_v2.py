"""Tests for LLM runtime profiler, prompt v2, mode profiles, and validation."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.models.settings import Settings
from app.services.context_builder_service import ContextBuilderService
from app.services.context_builder_service import BuiltContext, PageContextBlock
from app.services.llm_generation_service import LlmGenerationService
from app.services.llm_mode_service import effective_generation_settings, get_mode_profile
from app.services.llm_options_service import resolve_llm_options
from app.services.polish_policy_service import evaluate_polish, should_polish
from app.services.retrieval_engine.prompt_builder import CompactPromptBuilder
from app.services.rag_planning.plan_builders import build_answer_plan, build_knowledge_plan
from app.services.qdrant_service import SearchHit
from app.services.response_validator_service import ResponseValidatorService
from app.services.source_intelligence_router import SourceIntelligenceRouter
from app.services.source_intelligence_service import SourceProfile


def test_prompt_builder_excludes_debug_trace():
    settings = Settings()
    hits = [
        SearchHit(
            score=0.9,
            source_id=1,
            chunk_index=0,
            title="About",
            url="https://example.com/about/",
            source_type="page",
            text="Company overview text.",
        )
    ]
    kp = build_knowledge_plan(information_need="entity_overview", understanding=None, profile=None)
    ap = build_answer_plan(knowledge_plan=kp)
    system, user = CompactPromptBuilder.build(
        message="про банк",
        hits=hits,
        built_context=None,
        settings=settings,
        answer_plan=ap,
    )
    combined = system + user
    assert not CompactPromptBuilder.contains_debug_trace(combined)
    assert "trace_steps" not in combined.lower()


def test_prompt_builder_respects_max_prompt_chars_via_mode():
    fast = Settings(fast_mode_enabled=True)
    hq = Settings(llm_mode_profile="high_quality")
    assert effective_generation_settings(fast)["llm_max_prompt_chars"] <= 4500
    assert effective_generation_settings(hq)["llm_max_prompt_chars"] >= 4500


def test_ukrainian_query_excludes_english_duplicate():
    uk = SearchHit(
        score=0.8,
        source_id=1,
        chunk_index=0,
        title="Головна",
        url="https://example.com/",
        source_type="page",
        text="UA",
        source_language="uk",
    )
    en = SearchHit(
        score=0.85,
        source_id=2,
        chunk_index=0,
        title="Home",
        url="https://example.com/en",
        source_type="page",
        text="EN",
        source_language="en",
    )
    kept, excluded = ContextBuilderService.dedupe_bilingual_hits_with_report([en, uk], "uk")
    assert len(kept) == 1
    assert kept[0].source_language == "uk"
    assert len(excluded) == 1
    assert excluded[0]["reason"].startswith("language_duplicate")


def test_overview_penalizes_faq_relative_to_homepage():
    settings = MagicMock()
    settings.source_intelligence_importance_threshold = 70
    settings.prefer_user_language_sources = True
    faq = SourceProfile(
        source_id=1,
        url="https://example.com/faq/",
        document_type="faq_page",
        page_role="faq",
        importance=60,
        canonical=True,
        content_quality=70,
    )
    home = SourceProfile(
        source_id=2,
        url="https://example.com/",
        document_type="homepage",
        page_role="organization_overview",
        importance=95,
        canonical=True,
        content_quality=85,
        should_answer_company=True,
    )
    faq_hit = SearchHit(score=0.6, source_id=1, chunk_index=0, title="FAQ", url=faq.url, source_type="page", text="q")
    home_hit = SearchHit(score=0.55, source_id=2, chunk_index=0, title="Home", url=home.url, source_type="page", text="h")
    faq_boost, _ = SourceIntelligenceRouter.boost_for_hit(faq_hit, faq, routing="overview", settings=settings)
    home_boost, _ = SourceIntelligenceRouter.boost_for_hit(home_hit, home, routing="overview", settings=settings)
    assert home_boost > faq_boost


def test_polishing_off_by_default():
    settings = Settings(polish_mode="off")
    assert should_polish(settings, answer="Long " * 500, language="uk", fast_mode=False, generation_ms=5000) is False


def test_auto_polish_skips_when_generation_slow():
    settings = Settings(polish_mode="auto", polish_min_answer_chars=100, polish_skip_if_generation_ms_over=15000)
    long_answer = "word " * 600
    assert should_polish(settings, answer=long_answer, language="uk", fast_mode=False, generation_ms=20000) is False


def test_ollama_options_include_keep_alive_and_num_predict():
    settings = Settings()
    opts = resolve_llm_options(settings, prompt_chars=1500)
    assert opts["keep_alive"] == "30m"
    assert opts["num_predict"] == 160
    assert opts["top_p"] == 0.9
    assert opts["generation_timeout_seconds"] == 45


def test_polish_skips_overview_in_auto_mode():
    settings = Settings(polish_mode="auto", polish_min_answer_chars=100)
    long_answer = "word " * 600
    decision = evaluate_polish(
        settings,
        answer=long_answer,
        language="uk",
        fast_mode=False,
        generation_ms=5000,
        is_overview=True,
    )
    assert decision.enabled is False
    assert decision.reason == "overview_query"


def test_content_sanitizer_strips_ui_junk():
    from app.services.retrieval_engine.content_sanitizer import clean_context_text, strip_ui_junk

    raw = "Про банк | UKRSIBBANK — Про банк ×\nДетальніше\nРеальний текст про банк."
    cleaned = strip_ui_junk(raw)
    assert "×" not in cleaned
    assert "Детальніше" not in cleaned.lower()
    assert "Реальний текст" in cleaned
    lead = clean_context_text(raw, max_chars=500)
    assert len(lead) > 10


def test_fast_mode_builds_smaller_context_than_high_quality():
    fast_eff = effective_generation_settings(Settings(fast_mode_enabled=True))
    hq_eff = effective_generation_settings(Settings(llm_mode_profile="high_quality"))
    assert fast_eff["max_total_context_chars"] < hq_eff["max_total_context_chars"]
    assert fast_eff["llm_num_predict"] < hq_eff["llm_num_predict"]


def test_validator_catches_malformed_ukrainian():
    result = ResponseValidatorService().validate(
        "Ми обслуговуємо середньомалим бізнесом.",
        query="про банк",
    )
    assert any("malformed" in w for w in result.warnings)
    assert "малим і середнім" in result.cleaned_answer


def test_one_llm_call_by_default_no_polish():
    settings = Settings(polish_mode="off")
    assert get_mode_profile(settings).polish_mode == "off"


def test_dynamic_num_ctx_4096_for_small_prompt():
    settings = Settings(llm_num_ctx_mode="auto")
    opts = resolve_llm_options(settings, prompt_chars=2000)
    assert opts["num_ctx"] == 4096


def test_retry_compact_prefers_pipeline_context_order_over_raw_hit_order():
    hits = [
        SearchHit(score=0.9, source_id=10, chunk_index=0, title="News", url="https://site/news", source_type="page", text="news"),
        SearchHit(score=0.8, source_id=20, chunk_index=0, title="About", url="https://site/about", source_type="page", text="about"),
        SearchHit(score=0.7, source_id=30, chunk_index=0, title="Services", url="https://site/services", source_type="page", text="services"),
    ]
    ctx = BuiltContext(
        blocks=[
            PageContextBlock(source_id=20, title="About", url="https://site/about", chunks_used=1, text="about", score=0.8),
            PageContextBlock(source_id=30, title="Services", url="https://site/services", chunks_used=1, text="services", score=0.7),
        ],
        prompt_text="",
        total_chunks=2,
        page_count=2,
    )
    compact = LlmGenerationService._select_compact_hits(hits, ctx)
    assert [hit.source_id for hit in compact] == [20, 30]
