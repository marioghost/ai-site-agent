"""Structured HTML extraction, heading-aware chunking, and document-first retrieval.

RFC-100 Step 008 — migrated from legacy HybridRetrievalService to production
architecture:

  HybridChunkRetriever → DocumentAggregator → DocumentScorer → DocumentReranker
  (orchestrated by DocumentFirstRetrievalPipeline)

Tests assert document-first invariants, not chunk-first fusion or document_type boosts.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import sessionmaker

from tests._dbutil import make_engine
from app.models.chunk import Chunk
from app.models.settings import Settings
from app.models.source import Source
from app.services.chunking_service import ChunkingService
from app.services.html_parser_service import HtmlParserService
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.qdrant_service import SearchHit
from app.services.retrieval_engine.document_aggregator import DocumentAggregator
from app.services.retrieval_engine.pipeline import DocumentFirstRetrievalPipeline
from app.services.retrieval_engine.retrievers import HybridChunkRetriever
from app.services.retrieval_intent_service import RetrievalIntentResult

_HOMEPAGE_HTML = """
<html><head><title>Home</title></head>
<body>
<header><nav>Menu About Contact</nav></header>
<main>
  <h2>Exchange rates</h2>
  <table>
    <tr><th>Currency</th><th>Buy</th><th>Sell</th></tr>
    <tr><td>USD</td><td>41.00</td><td>41.50</td></tr>
    <tr><td>EUR</td><td>44.00</td><td>44.80</td></tr>
  </table>
  <h2>Office hours</h2>
  <p>Branches open Mon-Fri from 9:00 to 18:00.</p>
</main>
</body></html>
"""

_SITE_URL = "https://www.example.com/"


def _lexical_settings(**overrides) -> Settings:
    base = dict(
        qdrant_collection="test",
        retrieval_mode="lexical",
        similarity_threshold=0.55,
        enable_reranking=True,
        enable_query_expansion=True,
        enable_intent_aware_retrieval=False,
        homepage_boost_enabled=True,
        title_match_boost=0.15,
        heading_match_boost=0.15,
        homepage_boost_value=0.10,
        retrieval_profile="automatic",
    )
    base.update(overrides)
    return Settings(**base)


def _rates_intent() -> RetrievalIntentResult:
    return RetrievalIntentResult(
        intent="general_information",
        legacy_intent="unknown",
        answer_strategy="generic",
    )


@pytest.mark.unit
def test_html_extraction_preserves_structured_section():
    parsed = HtmlParserService().parse(_HOMEPAGE_HTML, _SITE_URL)
    assert parsed.is_homepage is True
    rates = [b for b in parsed.blocks if b.heading == "Exchange rates"]
    assert rates, "structured section should be extracted as a block"
    block = rates[0]
    assert "USD" in block.text and "41.00" in block.text
    assert block.content_type_hint == "rates"
    assert block.is_structured_block is True


@pytest.mark.unit
def test_chunking_attaches_title_and_heading():
    parsed = HtmlParserService().parse(_HOMEPAGE_HTML, _SITE_URL)
    chunks = ChunkingService().chunk_blocks(parsed.blocks, parsed.title)
    rate_chunks = [c for c in chunks if "USD" in c.text]
    assert rate_chunks
    chunk = rate_chunks[0]
    assert "Home" in chunk.text and "Exchange rates" in chunk.text
    assert chunk.content_type_hint == "rates"


@pytest.mark.unit
def test_document_aggregator_groups_same_source_chunks():
    """Duplicate chunks from one source collapse to a single document candidate."""
    chunks = [
        SearchHit(
            score=0.0,
            source_id=1,
            chunk_index=0,
            title="Home",
            url=_SITE_URL,
            source_type="page",
            text="Home — Exchange rates USD 41.00",
            heading="Exchange rates",
            lexical_score=0.9,
        ),
        SearchHit(
            score=0.0,
            source_id=1,
            chunk_index=1,
            title="Home",
            url=_SITE_URL,
            source_type="page",
            text="Home — Office hours Mon-Fri 9-18",
            heading="Office hours",
            lexical_score=0.4,
        ),
        SearchHit(
            score=0.0,
            source_id=2,
            chunk_index=0,
            title="About",
            url="https://www.example.com/about",
            source_type="page",
            text="About the organization",
            heading="About",
            lexical_score=0.3,
        ),
    ]
    documents, removed = DocumentAggregator.aggregate(chunks)
    assert len(documents) == 2
    assert removed == 1
    homepage = next(d for d in documents if d.source_id == 1)
    assert len(homepage.all_chunks) == 2
    assert homepage.representative_chunk.heading == "Exchange rates"


@pytest.fixture()
def lexical_session():
    engine = make_engine()
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


def _add_chunk(session, source, *, idx, text_value, heading, hint, homepage, structured):
    # PostgreSQL ``search_vector`` is generated — inserting the chunk is enough.
    c = Chunk(
        source_id=source.id,
        chunk_index=idx,
        title=source.title,
        url=source.url,
        text=text_value,
        vector_id=f"v{idx}",
        source_type="page",
        heading=heading,
        is_homepage=homepage,
        is_structured_block=structured,
        content_type_hint=hint,
    )
    session.add(c)
    session.commit()
    return c


def _seed_homepage_currency_fixture(session) -> Source:
    home = Source(url=_SITE_URL, source_type="page", title="Home")
    session.add(home)
    session.commit()

    _add_chunk(
        session,
        home,
        idx=0,
        text_value="Home — Exchange rates USD | 41.00 | 41.50 ; EUR | 44.00 | 44.80",
        heading="Exchange rates",
        hint="rates",
        homepage=True,
        structured=True,
    )
    _add_chunk(
        session,
        home,
        idx=1,
        text_value="Home — Office hours Branches open Mon-Fri from 9 to 18",
        heading="Office hours",
        hint="schedule",
        homepage=True,
        structured=True,
    )
    return home


def test_lexical_chunk_retriever_finds_structured_homepage_section(lexical_session):
    """HybridChunkRetriever (lexical mode) returns chunk hits with debug metadata."""
    session = lexical_session
    _seed_homepage_currency_fixture(session)
    settings = _lexical_settings()

    retriever = HybridChunkRetriever(
        session,
        settings,
        embedding_service=MagicMock(),
        qdrant_service=MagicMock(),
    )
    chunks, dbg = retriever.retrieve(
        normalized_query="exchange rates",
        top_k_dense=5,
        top_k_lexical=5,
        similarity_threshold=0.55,
        query_vector=None,
        profile=KnowledgeProfileService.default_profile(),
        query_intent="unknown",
    )

    assert chunks, "lexical retrieval should find homepage chunks"
    assert dbg.match_query
    assert dbg.lexical_count >= 1
    assert any("USD" in c.text for c in chunks)
    assert all(c.source_id == chunks[0].source_id for c in chunks)


def test_document_first_pipeline_selects_rates_document(lexical_session):
    """Document-first pipeline groups chunks, scores documents, and selects rates content."""
    session = lexical_session
    _seed_homepage_currency_fixture(session)
    settings = _lexical_settings()

    pipeline = DocumentFirstRetrievalPipeline(
        session,
        settings,
        embedding=MagicMock(),
        qdrant=MagicMock(),
    )
    result = pipeline.run(
        query="exchange rates",
        normalized="exchange rates",
        intent_result=_rates_intent(),
        profile=KnowledgeProfileService.default_profile(),
        query_vector=None,
        query_language="en",
    )

    assert result.selected_hits, "pipeline should select at least one document-level hit"
    top = result.selected_hits[0]
    assert top.heading == "Exchange rates"
    assert top.is_homepage is True
    assert "USD" in top.text

    assert len(result.all_documents) == 1
    assert result.all_documents[0].representative_chunk.heading == "Exchange rates"
    assert len(result.all_documents[0].all_chunks) == 2

    assert result.quality_metrics.documents_sent_to_llm >= 1
    assert result.quality_metrics.duplicate_documents_removed >= 0

    selected_doc = result.selected_documents[0]
    assert selected_doc.score_breakdown is not None
    assert selected_doc.score_breakdown.get("final_score", 0) > 0
    assert selected_doc.why_selected

    if result.rejected_documents:
        assert all(d.why_rejected for d in result.rejected_documents)

    stage_names = [s["stage"] for s in result.pipeline_stages]
    assert "chunk_retrieval" in stage_names
    assert "document_aggregation" in stage_names
    assert "document_scoring" in stage_names
    assert "document_reranking" in stage_names

    assert result.chunk_debug is not None
    assert result.chunk_debug.get("match_query")
