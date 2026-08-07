"""Release 1.1 — corpus / authority / evidence quality regressions (no architecture)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.source import Source
from app.models.settings import Settings
from app.services.document_type_service import detect_document_type
from app.services.evidence_planning.diversity import dedupe_language_candidates
from app.services.evidence_planning.normalizer import _duplicate_group
from app.services.evidence_planning.types import EvidenceCandidate
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.rag_planning.purpose_catalog import infer_knowledge_slots
from app.services.retrieval_engine.context_builder import RetrievalContextBuilder
from app.services.retrieval_engine.document_scorer import DocumentScorer
from app.services.retrieval_engine.focus_compatibility import _has_historical_signal
from app.services.retrieval_engine.query_understanding import QueryUnderstandingService
from app.services.retrieval_intent_service import RetrievalIntentResult
from app.services.source_intelligence_constants import CANONICAL_DOCUMENT_TYPES
from app.services.source_intelligence_service import SourceIntelligenceService
from app.services.context_builder_service import PageContextBlock

pytestmark = pytest.mark.unit


def test_content_hash_collapses_duplicate_group():
    a = _duplicate_group("https://a.example/x", "text a", "abc123")
    b = _duplicate_group("https://b.example/y", "text b", "abc123")
    assert a == b == "hash:abc123"
    assert _duplicate_group("https://a.example/x", "same", "") != "hash:abc123"


def test_canonical_types_are_identity_surfaces_only():
    assert "homepage" in CANONICAL_DOCUMENT_TYPES
    assert "about_page" in CANONICAL_DOCUMENT_TYPES
    assert "faq_page" not in CANONICAL_DOCUMENT_TYPES
    assert "pricing_page" not in CANONICAL_DOCUMENT_TYPES
    assert "product_page" not in CANONICAL_DOCUMENT_TYPES


def test_thin_homepage_is_not_canonical():
    source = Source(
        url="https://example.com/",
        source_type="page",
        status="indexed",
        title="Home",
        document_type="homepage",
        main_content_text="Welcome",
        main_content_chars=20,
        boilerplate_ratio=0.8,
    )
    profile = SourceIntelligenceService.build_profile(source)
    assert profile.document_type == "homepage"
    assert profile.canonical is False


def test_about_url_patterns_do_not_steal_news_slugs():
    profile = KnowledgeProfileService.default_profile()
    assert (
        detect_document_type(
            url="https://example.com/news/company-wins-award",
            title="Company wins award",
            profile=profile,
        )
        == "news_page"
    )
    assert (
        detect_document_type(
            url="https://example.com/company/",
            title="Our company",
            profile=profile,
        )
        == "about_page"
    )


def test_org_aspects_require_text_cues_beyond_identity():
    thin = infer_knowledge_slots(
        page_role="organization_overview",
        document_type="about_page",
        source_purpose="about company",
        heading="About",
        text="About us.",
    )
    assert "identity" in thin
    assert "capabilities" not in thin

    rich = infer_knowledge_slots(
        page_role="organization_overview",
        document_type="about_page",
        source_purpose="about company",
        heading="About",
        text=(
            "We provide platform services and product solutions across regions. "
            "Our mission is to deliver capability and activity for customers."
        ),
    )
    assert {"identity", "activity", "capabilities"} <= rich


def test_historical_years_beyond_fixed_list():
    assert _has_historical_signal({"2012", "product"})
    assert _has_historical_signal(set(), blob="archived rates from 2005")
    current = datetime.now(timezone.utc).year
    assert not _has_historical_signal({str(current), "rates"})


def test_product_benefits_focus_not_forced_to_org_profile():
    u = QueryUnderstandingService.analyze(
        "What are the benefits of the Premium Plan?",
        intent_result=RetrievalIntentResult(
            intent="product_query",
            legacy_intent="product_query",
            is_broad=False,
            answer_strategy="specific",
            confidence=0.8,
            matched_topic=None,
        ),
        query_language="en",
    )
    assert u.semantic_focus == "product_specification"


def test_template_summaries_skipped_in_context():
    text = RetrievalContextBuilder._compose_block_text(
        "Real paragraph about services and coverage.",
        section_text="",
        summary="This page describes the organization and its main activity.",
        page_role="organization_overview",
        max_chars=800,
    )
    assert "This page describes" not in text
    assert "Real paragraph" in text


def test_language_dedupe_prefers_query_language_twin():
    en = EvidenceCandidate(
        candidate_id="1",
        source_id=1,
        chunk_index=0,
        url="https://example.com/en/about",
        title="About",
        heading="",
        text="About the company",
        document_type="about_page",
        page_role="organization_overview",
        source_purpose="about company",
        language="en",
        authority_fitness=0.5,
        duplicate_group="hash:aaa",
    )
    uk = EvidenceCandidate(
        candidate_id="2",
        source_id=2,
        chunk_index=0,
        url="https://example.com/uk/about",
        title="Про нас",
        heading="",
        text="Про компанію",
        document_type="about_page",
        page_role="organization_overview",
        source_purpose="about company",
        language="uk",
        authority_fitness=0.55,
        duplicate_group="hash:bbb",
    )
    kept, excluded = dedupe_language_candidates([en, uk], "uk")
    assert len(kept) == 1
    assert kept[0].language == "uk"
    assert excluded and excluded[0]["reason"] == "language_duplicate"


def test_freshness_suppressed_for_news_on_overview():
    scorer = DocumentScorer(Settings())
    boost = scorer._freshness_boost(
        datetime.now(timezone.utc),
        page_role="news",
        document_type="news_page",
        semantic_focus="organization_profile",
        legacy_intent="entity_overview",
    )
    assert boost == 0.0
    news_boost = scorer._freshness_boost(
        datetime.now(timezone.utc),
        page_role="news",
        document_type="news_page",
        semantic_focus="news",
        legacy_intent="news_query",
    )
    assert news_boost > 0.0


def test_prompt_omits_type_role_headers():
    prompt = RetrievalContextBuilder._format_prompt(
        [
            PageContextBlock(
                source_id=1,
                title="About",
                url="https://example.com/about",
                chunks_used=1,
                text="Company overview body.",
                score=0.9,
                document_type="about_page",
                page_role="organization_overview",
            )
        ]
    )
    assert "Type:" not in prompt
    assert "Role:" not in prompt
    assert "Company overview body" in prompt


def test_entity_overview_priority_drops_contact_docs():
    rule = KnowledgeProfileService.priority_rule_for_intent(
        KnowledgeProfileService.default_profile(),
        "entity_overview",
    )
    assert rule is not None
    assert "about_page" in rule.boost_document_types
    assert "homepage" in rule.boost_document_types
    assert "contact_page" not in rule.boost_document_types
    assert "documentation_page" not in rule.boost_document_types
    assert "contact_page" in rule.deprioritize_document_types
