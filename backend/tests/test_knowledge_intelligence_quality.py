"""Knowledge intelligence quality — SI/KP metadata regressions (architecture frozen)."""
from __future__ import annotations

import pytest

from app.models.source import Source
from app.services.evidence_planning.normalizer import normalize_hits
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.qdrant_service import SearchHit
from app.services.rag_planning.purpose_catalog import (
    normalize_content_hint_to_purpose,
    purpose_from_metadata,
)
from app.services.source_intelligence_service import SourceIntelligenceService
from app.services.source_semantic_rules import build_rules_semantic

pytestmark = pytest.mark.unit


def test_si_summary_is_content_derived_not_template():
    source = Source(
        url="https://example.com/about/",
        source_type="page",
        status="indexed",
        title="About us",
        document_type="about_page",
        main_content_text=(
            "We provide platform services across multiple regions.\n\n"
            "Our teams deliver reliable infrastructure for customers worldwide."
        ),
        main_content_chars=1200,
        boilerplate_ratio=0.1,
    )
    profile = SourceIntelligenceService.build_profile(source)
    assert profile.llm_summary
    assert not profile.llm_summary.lower().startswith("this page describes")
    assert "provide platform" in profile.llm_summary.lower() or "about us" in profile.llm_summary.lower()


def test_thin_about_is_not_canonical():
    source = Source(
        url="https://example.com/about/",
        source_type="page",
        status="indexed",
        title="About",
        document_type="about_page",
        main_content_text="Hi",
        main_content_chars=20,
        boilerplate_ratio=0.6,
    )
    profile = SourceIntelligenceService.build_profile(source)
    assert profile.canonical is False


def test_generic_page_not_auto_general_answerable():
    source = Source(
        url="https://example.com/misc/page",
        source_type="page",
        status="indexed",
        title="Misc",
        document_type="generic_page",
        main_content_text="Random paragraph about nothing in particular here today.",
        main_content_chars=400,
        boilerplate_ratio=0.1,
    )
    profile = SourceIntelligenceService.build_profile(source)
    assert profile.page_role in {"generic", "organization_overview", "marketing"}
    # Without about/company purpose, generic must not flood broad inject.
    if (profile.semantic or {}).get("document_purpose") == "general information":
        assert profile.should_answer_general is False or profile.page_role != "generic"


def test_contact_purpose_does_not_set_support_flag():
    source = Source(
        url="https://example.com/contact/",
        source_type="page",
        status="indexed",
        title="Contact",
        document_type="contact_page",
        main_content_text="Email support@example.com phone +1 555 0100 office hours Monday.",
        main_content_chars=500,
        boilerplate_ratio=0.1,
    )
    profile = SourceIntelligenceService.build_profile(source)
    assert profile.page_role == "contact"
    assert profile.should_answer_support is False
    assert profile.canonical is False


def test_rules_topic_prefers_title_over_lang_slug():
    source = Source(
        url="https://example.com/uk/about-us",
        title="About the organization | Site",
        main_content_chars=500,
    )
    sem = build_rules_semantic(
        source,
        page_role="organization_overview",
        document_type="about_page",
        keywords=["services", "platform"],
        site_section="uk",
    )
    assert sem.main_topic.lower().startswith("about")
    assert sem.main_topic.lower() != "uk"
    assert sem.document_purpose == "about company"


def test_purpose_catalog_is_single_owner_for_rules():
    assert purpose_from_metadata(
        page_role="organization_overview", document_type="homepage"
    ) == "about company"
    assert normalize_content_hint_to_purpose("about") == "about company"
    assert normalize_content_hint_to_purpose("contacts") == "contact information"


def test_evidence_normalizer_uses_si_document_purpose():
    hit = SearchHit(
        score=0.8,
        source_id=1,
        chunk_index=0,
        title="About",
        url="https://example.com/about",
        source_type="page",
        text="We provide services.",
        document_type="about_page",
        page_role="organization_overview",
        content_type_hint="generic",
        document_purpose="about company",
        content_quality=80,
        boilerplate_ratio=0.1,
    )
    cands = normalize_hits([hit], intent="entity_overview")
    assert len(cands) == 1
    assert cands[0].source_purpose == "about company"
    assert cands[0].quality_score > 0.5


def test_generic_kp_has_no_bank_about_patterns():
    profile = KnowledgeProfileService.default_profile()
    dumped = " ".join(
        p for rule in profile.document_type_rules for p in rule.url_patterns + rule.title_patterns
    ).lower()
    assert "about-bank" not in dumped
    assert "pro-bank" not in dumped
    assert "про банк" not in dumped
    rates_hints = [
        r for r in profile.content_hint_rules if r.content_type_hint == "rates"
    ]
    assert rates_hints == []


def test_keywords_prefer_title_and_drop_stopwords():
    from app.services.source_intelligence_service import _extract_keywords

    kws = _extract_keywords(
        "Platform Services Overview",
        "the and for with platform services deliver reliable infrastructure for customers",
    )
    assert "platform" in kws
    assert "services" in kws
    assert "the" not in kws
    assert "and" not in kws


def test_no_kp_entity_type_leak_into_si():
    from app.schemas.knowledge_profile import KnowledgeProfile

    source = Source(
        url="https://example.com/x",
        source_type="page",
        status="indexed",
        title="Page",
        document_type="generic_page",
        main_content_text="Generic content about a topic with enough characters here.",
        main_content_chars=400,
        boilerplate_ratio=0.1,
    )
    # Industry entity_type on KP must not pollute SI entity_types when semantic has none override.
    kp = KnowledgeProfile(entity_type="bank")
    profile = SourceIntelligenceService.build_profile(source, profile=kp)
    assert "bank" not in profile.entity_types
