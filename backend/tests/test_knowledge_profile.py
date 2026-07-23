"""Tests for configurable Agent Knowledge Profile."""
from __future__ import annotations

from app.schemas.knowledge_profile import ImportantTopic, KnowledgeProfile
from app.services.document_type_service import detect_document_type
from app.services.knowledge_profile_service import KnowledgeProfileService, PRESETS
from app.services.query_intent_service import QueryIntentService


def test_generic_preset_has_no_bank_hardcoding_in_defaults():
    profile = PRESETS["generic_corporate"]
    dumped = profile.model_dump_json().lower()
    assert "ukrsib" not in dumped
    assert "укрсиб" not in dumped


def test_bank_preset_classifies_rates_topic():
    profile = PRESETS["bank_financial"]
    profile.organization_aliases = ["ukrsibbank", "укрсиббанк"]
    profile.organization_name = "Example Bank"
    result = QueryIntentService.classify_detailed("курси валют", profile=profile)
    assert result.intent == "topic_overview"
    assert result.matched_topic is not None
    assert result.matched_topic.key == "rates"


def test_entity_overview_from_organization_alias():
    profile = KnowledgeProfile(
        organization_name="Acme Corp",
        organization_aliases=["acme", "acme corp"],
        overview_query_patterns=["tell me about"],
    )
    assert QueryIntentService.classify("tell me about acme", profile=profile) == "entity_overview"


def test_document_type_from_profile_rules():
    profile = KnowledgeProfile(
        document_type_rules=[
            {
                "document_type": "about_page",
                "url_patterns": ["about-us"],
                "title_patterns": ["About us"],
                "priority": 90,
            }
        ]
    )
    assert (
        detect_document_type(
            url="https://example.com/about-us",
            title="About us",
            profile=profile,
        )
        == "about_page"
    )


def test_ecommerce_delivery_topic():
    profile = PRESETS["ecommerce"]
    result = QueryIntentService.classify_detailed("shipping options", profile=profile)
    assert result.intent == "topic_overview"
    assert result.matched_topic is not None
    assert result.matched_topic.key == "delivery"


def test_validation_catches_duplicate_topic_keys():
    profile = KnowledgeProfile(
        important_topics=[
            ImportantTopic(key="x", label="A", aliases=["a"]),
            ImportantTopic(key="x", label="B", aliases=["b"]),
        ]
    )
    errors = KnowledgeProfileService.validate_profile(profile)
    assert any("unique" in e.lower() for e in errors)


def test_placeholder_expansion():
    profile = KnowledgeProfile(
        organization_name="Acme",
        organization_aliases=["acme store"],
        site_display_name="Acme Shop",
    )
    terms = KnowledgeProfileService.expand_placeholders(
        "{{organization_name}} {{organization_aliases}}", profile
    )
    assert "Acme acme store" in terms or "Acme" in terms
    assert "acme store" in terms
