"""Tests for boilerplate-aware retrieval, document types, timeout, and reprocess."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from tests._dbutil import make_engine
from app.models.settings import Settings
from app.models.source import Source
from app.schemas.knowledge_profile import AppliedKnowledgeConfig
from app.services.boilerplate_detector_service import BoilerplateDetectorService
from app.services.context_builder_service import BuiltContext, ContextBuilderService
from app.services.document_type_service import detect_document_type
from app.services.html_parser_service import HtmlParserService
from app.services.knowledge_profile_service import PRESETS, KnowledgeProfileService
from app.services.ollama_service import OllamaError
from app.services.qdrant_service import SearchHit
from app.services.rag_service import LLM_TIMEOUT_MESSAGE, RagService
from app.services.reprocess_service import ReprocessOptions, ReprocessService, mark_sources_needs_reprocess
from app.services.retrieval_engine.diagnostics_builder import DiagnosticsBuilder
from app.services.retrieval_engine.document_scorer import DocumentScorer
from app.services.retrieval_engine.query_understanding import QueryUnderstandingService
from app.services.retrieval_engine.types import RankedDocument
from app.services.retrieval_intent_service import RetrievalIntentResult
from app.services.retrieval_scoring_service import score_content_match


PROMO_HTML = """
<html><head><title>Cashback bonus</title></head>
<body>
<nav>Приватним особам Бізнесу Відділення Про банк Реквізити Історія банку</nav>
<main><h1>10% cashback</h1><p>Get bonus on purchases this month.</p></main>
<footer>© Bank. Privacy Terms Contacts</footer>
</body></html>
"""

ABOUT_HTML = """
<html><head><title>Про банк</title></head>
<body>
<nav>Приватним особам Бізнесу Відділення Про банк</nav>
<main><h1>Про банк</h1><p>Ми — сучасний банк з повним спектром послуг.</p></main>
</body></html>
"""


@pytest.fixture()
def db_session():
    engine = make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def sample_source(db_session):
    source = Source(url="https://example.com/page", source_type="page", status="indexed")
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


@pytest.mark.unit
def test_promo_page_not_classified_as_about():
    profile = PRESETS["generic_corporate"]
    doc_type = detect_document_type(
        url="https://example.com/actions/get-10-percent-cashback",
        title="Cashback bonus",
        headings="10% cashback",
        profile=profile,
    )
    assert doc_type in {"promotion_page", "action_page", "offer_page"}
    assert doc_type != "about_page"


@pytest.mark.unit
def test_main_content_extraction_removes_navigation():
    profile = PRESETS["generic_corporate"]
    parser = HtmlParserService(profile=profile)
    promo = parser.parse(PROMO_HTML, "https://example.com/actions/cashback")
    about = parser.parse(ABOUT_HTML, "https://example.com/about-bank/")
    assert "Про банк" in promo.navigation_text
    assert "Про банк" not in promo.main_content_text
    assert "Про банк" in about.main_content_text
    assert "cashback" in promo.main_content_text.lower()


@pytest.mark.unit
def test_navigation_only_match_penalized():
    polluted_tail = "Приватним особam Бізнесu Відділення Про банк Реквізити Історія банку"
    body = ("Get bonus on purchases this month with partner merchants nationwide. " * 3) + polluted_tail
    _title_s, main_s, _url_s, _bp_pen, nav_pen, reason = score_content_match(
        query_tokens={"банк", "про"},
        title="Cashback bonus",
        heading="10% cashback",
        text=body,
        url="https://example.com/actions/cashback",
        title_boost=0.15,
        heading_boost=0.15,
    )
    assert nav_pen > 0
    assert reason in {"query_terms_nav_only", "query_terms_tail_only"}
    assert main_s == 0.0


@pytest.mark.unit
def test_boilerplate_detector_finds_repeated_phrases():
    detector = BoilerplateDetectorService()
    nav = "Приватним особam Бізнесu Відділення Про банк Реквізити Історія банку"
    sources = []
    for _i in range(5):
        s = MagicMock()
        s.status = "indexed"
        s.navigation_text = nav
        s.footer_text = "Privacy Terms"
        s.header_text = ""
        s.boilerplate_text = ""
        sources.append(s)

    db = MagicMock()
    db.scalars.return_value.all.return_value = sources
    detector.db = db
    phrases = detector.build_from_sources()
    assert phrases
    cleaned = detector.strip_boilerplate(f"Intro {nav} details")
    assert "Приватним особam" not in cleaned


@pytest.mark.unit
def test_entity_overview_deprioritizes_promotion_page():
    profile = PRESETS["generic_corporate"]
    doc_boosts, _ = KnowledgeProfileService.build_boost_tables(profile)
    boosts = doc_boosts.get("entity_overview", {})
    assert boosts.get("about_page", 0) > 0
    assert boosts.get("promotion_page", 0) < 0


@pytest.mark.unit
def test_document_scorer_populates_content_and_boilerplate_diagnostics():
    """DocumentScorer owns content-vs-boilerplate scoring fields (formerly hybrid _brief)."""
    settings = Settings(
        title_match_boost=0.15,
        heading_match_boost=0.15,
        homepage_boost_enabled=False,
    )
    hit = SearchHit(
        score=0.5,
        source_id=1,
        chunk_index=0,
        title="About us",
        url="https://example.com/about/",
        source_type="page",
        text="We provide services nationwide with a full product catalog.",
        heading="About us",
        document_type="about_page",
        dense_score=0.4,
        lexical_score=0.3,
        boilerplate_ratio=0.1,
    )
    understanding = QueryUnderstandingService.analyze(
        "about the company",
        intent_result=RetrievalIntentResult(
            intent="entity_overview",
            legacy_intent="entity_overview",
            is_broad=True,
        ),
    )
    doc = RankedDocument(
        source_id=1,
        url=hit.url,
        title=hit.title,
        document_type=hit.document_type,
        representative_chunk=hit,
        all_chunks=[hit],
    )
    DocumentScorer(settings).score_document(
        doc,
        query="about the company",
        understanding=understanding,
        query_tokens={"about", "company"},
    )

    assert hit.main_content_score >= 0
    assert hit.boilerplate_score >= 0
    assert doc.score_breakdown is not None
    assert "compatibility_score" in doc.score_breakdown

    preview = DiagnosticsBuilder.selected_candidates([doc])[0]
    assert preview["score_breakdown"] is not None
    assert preview["final_score"] > 0
    assert preview["why_selected"] or preview["ranking_reason"]


@pytest.mark.unit
def test_document_scorer_favors_meaningful_content_over_boilerplate():
    """Document-first scoring prefers substantive about content over boilerplate-heavy promo pages."""
    settings = Settings(
        title_match_boost=0.15,
        heading_match_boost=0.15,
        homepage_boost_enabled=False,
    )
    understanding = QueryUnderstandingService.analyze(
        "about the company",
        intent_result=RetrievalIntentResult(
            intent="entity_overview",
            legacy_intent="entity_overview",
            is_broad=True,
        ),
    )
    scorer = DocumentScorer(settings)
    query_tokens = {"about", "company"}

    about_hit = SearchHit(
        score=0.5,
        source_id=2,
        chunk_index=0,
        title="About us",
        url="https://example.com/about/",
        source_type="page",
        text="We are a modern company offering a full range of services.",
        heading="About us",
        document_type="about_page",
        dense_score=0.45,
        lexical_score=0.4,
        boilerplate_ratio=0.1,
    )
    promo_hit = SearchHit(
        score=0.5,
        source_id=1,
        chunk_index=0,
        title="Summer promo",
        url="https://example.com/promo",
        source_type="page",
        text="Get bonus on purchases.",
        heading="10% off",
        document_type="promotion_page",
        dense_score=0.55,
        lexical_score=0.5,
        boilerplate_ratio=0.7,
    )

    about_doc = RankedDocument(
        source_id=2,
        url=about_hit.url,
        title=about_hit.title,
        document_type=about_hit.document_type,
        representative_chunk=about_hit,
        all_chunks=[about_hit],
    )
    promo_doc = RankedDocument(
        source_id=1,
        url=promo_hit.url,
        title=promo_hit.title,
        document_type=promo_hit.document_type,
        representative_chunk=promo_hit,
        all_chunks=[promo_hit],
    )

    about_score, _ = scorer.score_document(
        about_doc,
        query="about the company",
        understanding=understanding,
        query_tokens=query_tokens,
    )
    promo_score, _ = scorer.score_document(
        promo_doc,
        query="about the company",
        understanding=understanding,
        query_tokens=query_tokens,
    )
    assert about_score.final_score > promo_score.final_score


def test_llm_timeout_returns_timeout_not_fallback(db_session):
    settings = Settings(
        top_k=3,
        similarity_threshold=0.0,
        qdrant_collection="site",
        embedding_model="bge-m3",
        fallback_answer="Я не знайшов цієї інформації на сайті.",
        llm_model="test-model",
        system_prompt="sys",
        temperature=0.1,
        max_tokens=512,
        ollama_generation_timeout_seconds=90,
        enable_source_links=True,
        enable_sources=True,
        enable_semantic_answer_cache=False,
        enable_retrieval_cache=False,
        enable_reranking=False,
        enable_ukrainian_polish_pass=False,
        enable_chat_debug_payload=False,
        enable_tracing=False,
        enable_trace_storage=False,
        knowledge_version=1,
        enable_broad_question_mode=False,
        enable_canonical_source_selection=False,
        enable_context_builder=True,
        enable_query_expansion=False,
        enable_intent_aware_retrieval=False,
    )
    db_session.add(settings)
    db_session.commit()

    rag = RagService(db_session, settings)
    hit = SearchHit(
        score=0.8,
        source_id=1,
        chunk_index=0,
        title="About",
        url="https://example.com/about",
        source_type="page",
        text="About us content",
    )
    context = ContextBuilderService().build([hit])
    intent = RetrievalIntentResult(intent="unknown", legacy_intent="unknown")

    @dataclass
    class FakePipeResult:
        hits: list[SearchHit]
        context: BuiltContext
        diagnostics: MagicMock
        intent_result: RetrievalIntentResult
        applied_config: AppliedKnowledgeConfig

    fake = FakePipeResult(
        hits=[hit],
        context=context,
        diagnostics=MagicMock(
            retrieval_debug=None,
            expanded_queries=[],
            to_dict=lambda: {},
        ),
        intent_result=intent,
        applied_config=AppliedKnowledgeConfig(),
    )

    with patch("app.services.rag_service.RetrievalPipelineService") as pipeline_cls:
        pipeline_cls.return_value.run.return_value = fake
        with patch.object(
            rag.ollama,
            "chat",
            side_effect=OllamaError("Chat request timed out after 90s"),
        ):
            result = rag.answer("розкажи про банк", None, request_id="t1", bypass_cache=True)
    assert result.error_type == "llm_timeout"
    assert result.answer == LLM_TIMEOUT_MESSAGE
    assert result.used_context is True
    assert result.sources


def test_mark_sources_needs_reprocess(db_session, sample_source):
    sample_source.status = "indexed"
    sample_source.extraction_version = "old"
    db_session.commit()
    count = mark_sources_needs_reprocess(db_session)
    assert count >= 1
    db_session.refresh(sample_source)
    assert sample_source.needs_reprocess is True


def test_reprocess_dry_run_does_not_modify(db_session, sample_source):
    from app.repositories.settings_repository import SettingsRepository

    sample_source.status = "indexed"
    db_session.commit()
    settings = SettingsRepository(db_session).get_or_create()
    service = ReprocessService(db_session, settings)
    preview = service.preview(
        ReprocessOptions(scope="selected", source_ids=[sample_source.id])
    )
    assert preview.selected_sources == 1
    result = service.run(
        ReprocessOptions(scope="selected", source_ids=[sample_source.id], dry_run=True)
    )
    assert result["dry_run"] is True
