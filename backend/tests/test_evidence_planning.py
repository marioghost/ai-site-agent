"""Evidence planning architecture — behavior-focused regression tests."""
from __future__ import annotations

import pytest

from app.models.settings import Settings
from app.schemas.knowledge_profile import KnowledgeProfile, SourcePriorityRule
from app.services.rag_planning.plan_builders import build_knowledge_plan
from app.services.evidence_planning.planner import EvidencePlanner
from app.services.qdrant_service import SearchHit
from app.services.retrieval_engine.context_budget import ContextBudgetService
from app.services.retrieval_engine.context_builder import RetrievalContextBuilder
from app.services.retrieval_engine.prompt_builder import CompactPromptBuilder
from app.services.retrieval_intent_service import RetrievalIntentResult
from tests._rag_planning_helpers import planner_decision_for_test


def _hit(
    source_id: int,
    *,
    document_type: str = "generic_page",
    score: float = 0.5,
    url: str = "",
    title: str = "",
    is_homepage: bool = False,
    page_role: str = "",
    source_canonical: bool = False,
    selection_reason: str = "",
    text: str = "body",
    source_language: str = "uk",
) -> SearchHit:
    return SearchHit(
        score=score,
        source_id=source_id,
        chunk_index=0,
        title=title or document_type,
        url=url or f"https://tenant.example/{source_id}",
        source_type="page",
        text=text,
        heading="",
        is_homepage=is_homepage,
        document_type=document_type,
        final_score=score,
        page_role=page_role,
        source_canonical=source_canonical,
        selection_reason=selection_reason,
        source_language=source_language,
    )


def _intent(intent: str = "entity_overview", *, broad: bool = True) -> RetrievalIntentResult:
    return RetrievalIntentResult(
        intent=intent,
        legacy_intent=intent,
        is_broad=broad,
        answer_strategy="overview" if "overview" in intent else "generic",
    )


def _profile_a() -> KnowledgeProfile:
    return KnowledgeProfile(
        organization_name="Tenant A",
        source_priority_rules=[
            SourcePriorityRule(
                query_intent="entity_overview",
                boost_document_types=["about_page", "homepage"],
                deprioritize_document_types=["news_page", "promotion_page", "blog_post"],
            )
        ],
    )


def _plan(
    hits: list[SearchHit],
    *,
    query: str,
    intent: str = "entity_overview",
    intent_result: RetrievalIntentResult | None = None,
    profile: KnowledgeProfile | None = None,
    settings: Settings | None = None,
    query_language: str = "en",
    system_prompt: str = "",
) -> object:
    settings = settings or Settings()
    profile = profile or KnowledgeProfile()
    ir = intent_result or _intent(intent)
    return EvidencePlanner(None).plan(
        hits,
        planner_decision=planner_decision_for_test(
            query,
            intent=ir.legacy_intent or intent,
            broad=ir.is_broad,
            profile=profile,
            settings=settings,
            query_language=query_language,
        ),
        profile=profile,
        query=query,
        query_language=query_language,
        settings=settings,
        system_prompt=system_prompt,
    )


@pytest.mark.unit
def test_tenant_a_profile_beats_injected_homepage():
    about = _hit(
        1,
        document_type="about_page",
        score=0.56,
        page_role="organization_overview",
        text="We are an organization providing financial services to clients.",
        url="https://tenant-a.example/about",
    )
    homepage = _hit(
        2,
        document_type="homepage",
        score=0.94,
        is_homepage=True,
        selection_reason="broad_inject:source_intelligence",
        text="Limited offer! Subscribe now!",
        url="https://tenant-a.example/",
    )
    news = _hit(3, document_type="news_page", score=0.88, text="Breaking news headline")
    plan = _plan(
        [homepage, news, about],
        query="Tell me about the organization",
        profile=_profile_a(),
        query_language="uk",
        settings=Settings(llm_mode_profile="high_quality"),
    )
    assert plan.selected
    assert plan.selected[0].candidate.document_type == "about_page"
    assert all(s.candidate.document_type != "news_page" for s in plan.selected)


@pytest.mark.unit
def test_tenant_b_homepage_primary_when_only_overview():
    homepage = _hit(
        1,
        document_type="homepage",
        score=0.62,
        is_homepage=True,
        page_role="organization_overview",
        text="We are a public information portal serving citizens.",
        url="https://tenant-b.example/",
    )
    plan = _plan(
        [homepage],
        query="What is this site?",
        query_language="en",
        settings=Settings(llm_mode_profile="high_quality"),
    )
    assert plan.selected[0].candidate.document_type == "homepage"
    assert plan.sufficiency.level in {"sufficient", "partial"}


@pytest.mark.unit
def test_tenant_c_documentation_portal_no_company_bias():
    intro = _hit(
        1,
        document_type="documentation_page",
        score=0.7,
        page_role="documentation",
        text="API concepts and architecture overview for developers.",
        url="https://docs.example/intro",
    )
    release = _hit(
        2,
        document_type="news_page",
        score=0.65,
        page_role="news",
        text="Release notes version 2.4",
        url="https://docs.example/releases",
    )
    plan = _plan(
        [release, intro],
        intent="topic_overview",
        intent_result=_intent("topic_overview"),
        query="Explain the platform",
        query_language="en",
    )
    assert plan.selected[0].candidate.page_role == "documentation"


@pytest.mark.unit
def test_tenant_d_promotion_primary_for_offer_intent():
    promo = _hit(
        1,
        document_type="promotion_page",
        score=0.55,
        page_role="campaign",
        text="Special offer: 20% discount this month.",
    )
    about = _hit(
        2,
        document_type="about_page",
        score=0.8,
        page_role="organization_overview",
        text="Company identity and history.",
    )
    plan = _plan(
        [about, promo],
        intent="news_query",
        intent_result=RetrievalIntentResult(intent="news_query", legacy_intent="news_query"),
        query="current offer",
        query_language="en",
    )
    assert plan.selected[0].candidate.document_type in {"promotion_page", "news_page"}


@pytest.mark.unit
def test_coverage_prefers_new_aspect_over_duplicate():
    about1 = _hit(
        1,
        document_type="about_page",
        score=0.8,
        page_role="organization_overview",
        text="We are Org A. Our identity is public service.",
    )
    about2 = _hit(
        2,
        document_type="about_page",
        score=0.79,
        page_role="organization_overview",
        text="We are Org A. Our identity is public service.",
        url="https://tenant.example/about-copy",
    )
    services = _hit(
        3,
        document_type="service_page",
        score=0.6,
        page_role="service_overview",
        text="Services include consulting, support, and training programs.",
    )
    plan = _plan(
        [about1, about2, services],
        query="Tell me about the organization",
        settings=Settings(max_sources_in_prompt=2, llm_mode_profile="high_quality"),
    )
    types = [s.candidate.document_type for s in plan.selected]
    assert "service_page" in types or len(plan.selected) == 1


@pytest.mark.unit
def test_multilingual_prefers_user_language():
    uk = _hit(
        1,
        document_type="about_page",
        score=0.7,
        page_role="organization_overview",
        text="Ми організація.",
        source_language="uk",
    )
    en = _hit(
        1,
        document_type="about_page",
        score=0.69,
        page_role="organization_overview",
        text="We are an organization.",
        source_language="en",
        url="https://tenant.example/about",
    )
    plan = _plan(
        [en, uk],
        query="розкажи про організацію",
        query_language="uk",
    )
    assert plan.selected[0].candidate.language == "uk"


@pytest.mark.unit
def test_sufficiency_weak_when_only_incidental():
    news = _hit(1, document_type="news_page", score=0.7, page_role="news", text="News headline")
    promo = _hit(2, document_type="promotion_page", score=0.65, page_role="campaign", text="Sale!")
    plan = _plan(
        [news, promo],
        query="overview",
        profile=_profile_a(),
    )
    assert plan.sufficiency.level in {"weak", "partial", "no_evidence"}


@pytest.mark.unit
def test_budget_uses_real_system_prompt():
    short = Settings(system_prompt="Short.", llm_mode_profile="high_quality", max_context_tokens=0)
    long = Settings(
        system_prompt="Long operator prompt. " * 200,
        llm_mode_profile="high_quality",
        max_context_tokens=0,
    )
    sb = ContextBudgetService.compute(short, system_prompt=short.system_prompt, user_message="Q?")
    lb = ContextBudgetService.compute(long, system_prompt=long.system_prompt, user_message="Q?")
    assert lb.system_tokens > sb.system_tokens


@pytest.mark.unit
def test_diagnostics_order_matches_selected():
    about = _hit(1, document_type="about_page", score=0.7, page_role="organization_overview")
    home = _hit(
        2,
        document_type="homepage",
        score=0.9,
        is_homepage=True,
        selection_reason="broad_inject:source_intelligence",
    )
    plan = _plan(
        [home, about],
        query="overview",
        profile=_profile_a(),
    )
    diag_urls = plan.to_diagnostics()["final_order_urls"]
    selected_urls = [s.candidate.url for s in plan.selected]
    assert diag_urls == selected_urls


@pytest.mark.unit
def test_context_builder_preserves_evidence_plan_order():
    about = _hit(
        1,
        document_type="about_page",
        score=0.7,
        page_role="organization_overview",
        text="About the organization and what it does.",
        url="https://tenant.example/about",
    )
    home = _hit(
        2,
        document_type="homepage",
        score=0.9,
        is_homepage=True,
        selection_reason="broad_inject:source_intelligence",
        text="Promotional homepage copy.",
        url="https://tenant.example/",
    )
    plan = _plan(
        [home, about],
        query="overview",
        profile=_profile_a(),
    )
    context, report = RetrievalContextBuilder(None).build_from_plan(
        plan,
        settings=Settings(),
        user_message="overview",
    )
    assert context.blocks[0].url == plan.selected[0].candidate.url
    assert report.selected_blocks[0]["url"] == plan.selected[0].candidate.url


@pytest.mark.unit
def test_banking_regression_secondary_fixture():
    about = _hit(
        10,
        document_type="about_page",
        score=0.56,
        page_role="organization_overview",
        url="https://example.org/about-institution",
        text="Institution profile and activity description.",
    )
    home = _hit(
        11,
        document_type="homepage",
        score=0.94,
        is_homepage=True,
        selection_reason="broad_inject:source_intelligence",
        text="Promotional homepage content.",
        url="https://example.org/",
    )
    plan = _plan(
        [home, about],
        query="то що ти скажеш про банк",
        profile=_profile_a(),
        query_language="uk",
        settings=Settings(system_prompt="Custom.", llm_mode_profile="high_quality"),
        system_prompt="Custom.",
    )
    assert plan.selected[0].candidate.document_type == "about_page"
    _, user = CompactPromptBuilder.build(
        message="то що ти скажеш про банк",
        hits=plan.ordered_hits,
        built_context=None,
        intent="entity_overview",
        settings=Settings(system_prompt="Custom.", llm_mode_profile="high_quality"),
    )
    assert "Question: то що ти скажеш про банк" in user


@pytest.mark.unit
def test_knowledge_plan_slots_for_overview():
    knowledge = build_knowledge_plan(information_need="entity_overview", understanding=None, profile=None)
    assert "identity" in knowledge.required_slots
    assert "offer" in knowledge.forbidden_slots
