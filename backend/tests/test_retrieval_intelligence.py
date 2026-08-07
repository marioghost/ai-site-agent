"""Retrieval Intelligence — semantic focus, compatibility, consistency, goal satisfaction."""
from __future__ import annotations

import pytest

from app.models.settings import Settings
from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.evidence_planning.planner import EvidencePlanner
from app.services.qdrant_service import SearchHit
from app.services.retrieval_engine.focus_compatibility import evaluate_focus_compatibility
from app.services.retrieval_engine.query_understanding import QueryUnderstandingService
from app.services.retrieval_intent_service import RetrievalIntentResult
from tests._rag_planning_helpers import planner_decision_for_test

pytestmark = pytest.mark.unit


def _hit(
    source_id: int,
    *,
    title: str,
    text: str,
    document_type: str = "generic_page",
    page_role: str = "generic",
    score: float = 0.7,
    url: str = "",
) -> SearchHit:
    return SearchHit(
        score=score,
        source_id=source_id,
        chunk_index=0,
        title=title,
        url=url or f"https://tenant.example/{source_id}",
        source_type="page",
        text=text,
        document_type=document_type,
        page_role=page_role,
        final_score=score,
        source_language="en",
    )


def _plan(hits: list[SearchHit], query: str, *, intent: str = "entity_overview", broad: bool = True):
    return EvidencePlanner(None).plan(
        hits,
        planner_decision=planner_decision_for_test(
            query,
            intent=intent,
            broad=broad,
            profile=KnowledgeProfile(),
            settings=Settings(llm_mode_profile="high_quality"),
            query_language="en",
        ),
        profile=KnowledgeProfile(),
        query=query,
        query_language="en",
        settings=Settings(llm_mode_profile="high_quality"),
    )


def test_benefits_query_uses_organization_profile_not_listing():
    u = QueryUnderstandingService.analyze(
        "What are the benefits of Example Org?",
        intent_result=RetrievalIntentResult(
            intent="entity_overview",
            legacy_intent="entity_overview",
            is_broad=True,
            answer_strategy="overview",
            confidence=0.8,
        ),
        query_language="en",
    )
    assert u.semantic_focus == "organization_profile"
    assert u.expected_answer_type == "overview"
    assert u.expected_evidence_type == "organization_profile"
    assert u.scope_type == "organization_overview"


def test_saas_org_benefits_reject_pricing_tier_pages():
    about = _hit(
        1,
        title="About Example Cloud",
        text="Example Cloud helps teams collaborate securely worldwide.",
        document_type="about_page",
        page_role="organization_overview",
        score=0.7,
    )
    pricing = _hit(
        2,
        title="Pro plan pricing",
        text="Pro plan includes advanced analytics and API access.",
        document_type="pricing_page",
        page_role="pricing",
        score=0.85,
    )
    plan = _plan([pricing, about], "What are the benefits of Example Cloud?")
    assert plan.selected
    assert plan.selected[0].candidate.document_type == "about_page"
    rejected = {r.candidate.title: r.candidate.compatibility_label for r in plan.rejected}
    assert rejected.get("Pro plan pricing") in {
        "adjacent_incompatible",
        "marketing_only",
    }


def test_ecommerce_product_a_rejects_adjacent_product_b():
    a = _hit(
        1,
        title="Trail Runner shoes terms",
        text="Trail Runner shoes: sizes, materials, return window and warranty.",
        document_type="product_page",
        page_role="product_details",
        score=0.76,
    )
    b = _hit(
        2,
        title="City Walker shoes",
        text="City Walker shoes for daily commuting with cushioned soles.",
        document_type="product_page",
        page_role="product_details",
        score=0.8,
    )
    plan = _plan(
        [b, a],
        "What are the Trail Runner shoes conditions?",
        intent="product_query",
        broad=False,
    )
    assert plan.selected
    assert "Trail Runner" in plan.selected[0].candidate.title
    selected_titles = {s.candidate.title for s in plan.selected}
    assert "City Walker shoes" not in selected_titles


def test_university_definition_prefers_program_overview_over_news():
    program = _hit(
        1,
        title="Data Science MSc overview",
        text="The Data Science MSc is a graduate program covering statistics and machine learning.",
        document_type="documentation_page",
        page_role="documentation",
        score=0.7,
    )
    news = _hit(
        2,
        title="Campus news: new labs open",
        text="The university opened new labs this month for several faculties.",
        document_type="news_page",
        page_role="news",
        score=0.82,
    )
    plan = _plan(
        [news, program],
        "What is the Data Science MSc?",
        intent="product_query",
        broad=False,
    )
    assert plan.selected
    assert plan.selected[0].candidate.title == "Data Science MSc overview"
    assert plan.selected[0].candidate.compatibility_label in {
        "definition_support",
        "exact_match",
        "same_product",
        "same_category",
    }


def test_clinic_locator_prefers_locator_page_over_promo_address_list():
    locator = _hit(
        1,
        title="Find a clinic location",
        text="Use the clinic locator to search by city and filter by service.",
        document_type="contact_page",
        page_role="contact",
        score=0.72,
    )
    promo = _hit(
        2,
        title="New downtown clinic opens",
        text="Visit us at 12 Main Street this weekend for free screenings.",
        document_type="news_page",
        page_role="news",
        score=0.8,
    )
    plan = _plan(
        [promo, locator],
        "Where can I find a clinic near downtown?",
        intent="contacts_query",
        broad=False,
    )
    assert plan.selected
    assert plan.selected[0].candidate.title == "Find a clinic location"
    assert plan.selected[0].candidate.compatibility_label == "navigation_support"


def test_docs_portal_definition_prefers_versioned_page_over_homepage():
    docs = _hit(
        1,
        title="Widgets API v2 overview",
        text="Widgets API v2 defines endpoints for creating and listing widgets.",
        document_type="documentation_page",
        page_role="documentation",
        score=0.7,
    )
    home = _hit(
        2,
        title="Developer portal home",
        text="Welcome to the developer portal. Explore our products and docs.",
        document_type="homepage",
        page_role="organization_overview",
        score=0.9,
    )
    plan = _plan(
        [home, docs],
        "What is Widgets API v2?",
        intent="product_query",
        broad=False,
    )
    assert plan.selected
    assert "Widgets API v2" in plan.selected[0].candidate.title


def test_comparison_intent_may_keep_multiple_products():
    pro = _hit(
        1,
        title="Pro plan",
        text="Pro plan includes analytics.",
        document_type="pricing_page",
        page_role="pricing",
        score=0.75,
    )
    enterprise = _hit(
        2,
        title="Enterprise plan",
        text="Enterprise plan includes SSO.",
        document_type="pricing_page",
        page_role="pricing",
        score=0.74,
    )
    plan = _plan(
        [pro, enterprise],
        "Compare Pro plan vs Enterprise plan",
        intent="product_query",
        broad=False,
    )
    titles = {s.candidate.title for s in plan.selected}
    assert "Pro plan" in titles
    assert "Enterprise plan" in titles


def test_goal_satisfaction_exposed_on_sufficiency():
    about = _hit(
        1,
        title="About Org",
        text="Org provides public services.",
        document_type="about_page",
        page_role="organization_overview",
    )
    plan = _plan([about], "Tell me about the organization")
    assert plan.sufficiency.goal_satisfaction >= 0.3
    diag = plan.to_diagnostics()
    assert "goal_satisfaction" in diag["sufficiency"]
    assert diag["semantic_focus"]


def test_focus_compatibility_marks_historical_rate_page():
    u = QueryUnderstandingService.analyze(
        "What is the deposit rate?",
        intent_result=RetrievalIntentResult(
            intent="product_query",
            legacy_intent="product_query",
            answer_strategy="fact",
            confidence=0.8,
        ),
        query_language="en",
    )
    result = evaluate_focus_compatibility(
        u,
        title="Deposit rates archive 2014",
        purpose="news",
        page_role="news",
        document_type="news_page",
        text="In 2014 the promotional deposit rate reached 15%.",
    )
    assert result.label in {"historical", "news_only"}
