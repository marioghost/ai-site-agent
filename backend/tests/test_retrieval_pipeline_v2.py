"""Tests for config-driven retrieval pipeline (domain-agnostic)."""
from __future__ import annotations

import pathlib

from app.services.broad_question_service import BroadQuestionService
from app.services.content_category_service import detect_content_category
from app.services.context_builder_service import ContextBuilderService
from app.services.knowledge_profile_service import PRESETS, KnowledgeProfileService
from app.services.qdrant_service import SearchHit
from app.services.retrieval_expansion_service import RetrievalExpansionService
from app.services.retrieval_intent_service import RetrievalIntentService

RETRIEVAL_SERVICE_FILES = [
    "retrieval_intent_service.py",
    "retrieval_expansion_service.py",
    "broad_question_service.py",
    "content_category_service.py",
    "retrieval_pipeline_service.py",
    "query_intent_service.py",
]

FORBIDDEN_DOMAIN_STRINGS = (
    "ukrsibbank",
    "credit",
    "loan",
    "deposit",
    "currency",
    "bank",
    "card",
    "branch",
    "atm",
    "кредит",
    "депозит",
    "банкомат",
    "банк",
)

ALLOWED_PATH_FRAGMENTS = (
    "/tests/",
    "/presets/",
    "knowledge_profile_service.py",
    "query_expansion_service.py",
    "document_type_service.py",
    "rag_service.py",
)


def test_broad_question_detection_generic_markers():
    profile = PRESETS["generic_corporate"]
    assert BroadQuestionService.is_broad_question("tell me about the company", profile=profile)
    assert BroadQuestionService.is_broad_question("розкажи про компанію", profile=profile)
    assert not BroadQuestionService.is_broad_question("specific product sku 12345", profile=profile)


def test_bank_preset_entity_overview_via_profile_not_code():
    profile = PRESETS["bank_financial"]
    profile.organization_aliases = ["ukrsibbank", "укрсиббанк"]
    profile.entity_type = "bank"
    result = RetrievalIntentService.classify("розкажи про банк", profile=profile)
    assert result.legacy_intent == "entity_overview"
    assert result.is_broad is True


def test_bank_topic_intent_from_profile_aliases():
    profile = PRESETS["bank_financial"]
    result = RetrievalIntentService.classify("курси валют", profile=profile)
    assert result.legacy_intent == "topic_overview"
    assert result.matched_topic is not None
    assert result.matched_topic.key == "rates"


def test_bank_expansion_uses_profile_rules():
    profile = PRESETS["bank_financial"]
    result = RetrievalIntentService.classify("курси валют", profile=profile)
    terms = RetrievalExpansionService(profile).expand_terms("курси валют", intent_result=result)
    assert "курси" in terms or "валют" in terms
    assert any(t in terms for t in ("rates", "exchange", "курси валют"))


def test_ecommerce_preset_delivery_topic():
    profile = PRESETS["ecommerce"]
    result = RetrievalIntentService.classify("shipping options", profile=profile)
    assert result.legacy_intent == "topic_overview"
    assert result.matched_topic is not None
    assert result.matched_topic.key == "delivery"


def test_documentation_portal_docs_topic():
    profile = PRESETS["saas"]
    result = RetrievalIntentService.classify("api documentation", profile=profile)
    assert result.legacy_intent == "topic_overview"
    assert result.matched_topic is not None
    assert result.matched_topic.key == "docs"


def test_corporate_about_page_from_profile_rules():
    profile = PRESETS["generic_corporate"]
    cat = detect_content_category(
        url="https://example.com/about-us",
        title="About us",
        profile=profile,
    )
    assert cat == "about_page"


def test_unknown_content_hint_auto_created():
    from app.schemas.knowledge_profile import ImportantTopic

    profile = PRESETS["generic_corporate"]
    profile.important_topics = [
        ImportantTopic(key="custom", label="Custom", preferred_content_hints=["custom_hint_xyz"])
    ]
    repaired, warnings = KnowledgeProfileService.auto_repair_profile(profile)
    assert any("custom_hint_xyz" in w for w in warnings)
    assert any(r.content_type_hint == "custom_hint_xyz" for r in repaired.content_hint_rules)


def test_retrieval_services_contain_no_forbidden_domain_strings():
    services_dir = pathlib.Path(__file__).resolve().parents[1] / "app" / "services"
    violations: list[str] = []
    for filename in RETRIEVAL_SERVICE_FILES:
        path = services_dir / filename
        if not path.exists():
            continue
        rel = str(path)
        if any(fragment in rel for fragment in ALLOWED_PATH_FRAGMENTS):
            continue
        text = path.read_text(encoding="utf-8").lower()
        for forbidden in FORBIDDEN_DOMAIN_STRINGS:
            if forbidden in text:
                violations.append(f"{filename}: contains '{forbidden}'")
    assert not violations, "Domain-specific strings in retrieval logic:\n" + "\n".join(violations)


def test_content_category_homepage():
    cat = detect_content_category(
        url="https://example.com/",
        title="Home",
        is_homepage=True,
    )
    assert cat == "homepage"


def test_context_builder_groups_by_page():
    hits = [
        SearchHit(
            score=0.9,
            source_id=1,
            chunk_index=0,
            title="Home",
            url="https://x/",
            source_type="page",
            text="Welcome to our site",
            is_homepage=True,
            final_score=0.9,
        ),
        SearchHit(
            score=0.85,
            source_id=1,
            chunk_index=1,
            title="Home",
            url="https://x/",
            source_type="page",
            text="We offer many services",
            is_homepage=True,
            final_score=0.85,
        ),
        SearchHit(
            score=0.7,
            source_id=2,
            chunk_index=0,
            title="News",
            url="https://x/news",
            source_type="page",
            text="Some news item",
            final_score=0.7,
        ),
    ]
    built = ContextBuilderService().build(hits, max_pages=2, max_chunks_per_page=3)
    assert built.page_count == 2
    assert built.total_chunks >= 2
    assert "Welcome to our site" in built.prompt_text
    assert "URL: https://x/" in built.prompt_text
