"""RAG Architecture Evolution v2 — contract and wiring tests."""
from __future__ import annotations

import pytest

from app.models.settings import Settings
from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.evidence_planning.planner import EvidencePlanner
from app.services.qdrant_service import SearchHit
from app.services.rag_planning.budget_resolver import resolve_retrieval_budget
from app.services.rag_planning.contracts import KnowledgePlan
from app.services.rag_planning.coverage_validator import (
    build_coverage_snapshot,
    validate_knowledge_coverage,
)
from app.services.rag_planning.plan_builders import build_answer_plan, build_knowledge_plan
from app.services.rag_planning.query_planner import QueryPlanner
from app.services.rag_planning.rag_contract import RAG_CONTRACT_VERSION, RAG_PIPELINE_STAGES
from app.services.rag_planning.strategy_resolver import resolve_retrieval_strategy
from app.services.retrieval_intent_service import RetrievalIntentResult


def _settings(**overrides) -> Settings:
    base = Settings()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _intent(intent: str = "entity_overview", *, broad: bool = True) -> RetrievalIntentResult:
    return RetrievalIntentResult(
        intent=intent,
        legacy_intent=intent,
        is_broad=broad,
        answer_strategy="overview",
    )


@pytest.mark.unit
def test_query_planner_runs_understanding_once():
    decision = QueryPlanner.plan(
        "What is this organization?",
        intent_result=_intent(),
        profile=KnowledgeProfile(),
        settings=_settings(),
        query_language="en",
    )
    assert decision.understanding is not None
    assert decision.knowledge_plan.required_slots
    assert decision.answer_plan.scope_instruction
    assert decision.retrieval_strategy.top_k_dense > 0
    assert decision.retrieval_budget.chunk_pool_size >= 12
    assert len(decision.decision_chain) >= 3
    assert decision.understanding.semantic_focus
    assert decision.understanding.expected_evidence_type
    assert decision.knowledge_plan.semantic_focus == decision.understanding.semantic_focus
    assert (
        decision.knowledge_plan.expected_evidence_type
        == decision.understanding.expected_evidence_type
    )


@pytest.mark.unit
def test_benefits_query_plans_organization_profile_focus():
    decision = QueryPlanner.plan(
        "What are the benefits of Example Org?",
        intent_result=_intent("entity_overview"),
        profile=KnowledgeProfile(),
        settings=_settings(),
        query_language="en",
    )
    assert decision.understanding.semantic_focus == "organization_profile"
    assert decision.understanding.expected_answer_type == "overview"
    assert decision.knowledge_plan.expected_evidence_type == "organization_profile"

@pytest.mark.unit
def test_retrieval_candidate_count_affects_budget():
    low = resolve_retrieval_budget(
        build_knowledge_plan(
            information_need="entity_overview",
            understanding=None,
            profile=None,
        ),
        resolve_retrieval_strategy(
            build_knowledge_plan(
                information_need="entity_overview",
                understanding=None,
                profile=None,
            ),
            _settings(retrieval_candidate_count=12),
        ),
        _settings(retrieval_candidate_count=12),
    )
    high = resolve_retrieval_budget(
        build_knowledge_plan(
            information_need="entity_overview",
            understanding=None,
            profile=None,
        ),
        resolve_retrieval_strategy(
            build_knowledge_plan(
                information_need="entity_overview",
                understanding=None,
                profile=None,
            ),
            _settings(retrieval_candidate_count=60),
        ),
        _settings(retrieval_candidate_count=60),
    )
    assert high.chunk_pool_size > low.chunk_pool_size


@pytest.mark.unit
def test_knowledge_plan_separate_from_answer_plan():
    kp = build_knowledge_plan(
        information_need="entity_overview",
        understanding=None,
        profile=None,
    )
    ap = build_answer_plan(knowledge_plan=kp)
    assert kp.required_slots
    assert ap.scope_instruction
    assert ap.answer_type == kp.answer_type
    assert kp.plan_reasons != ap.plan_reasons or ap.plan_reasons


@pytest.mark.unit
def test_evidence_planner_accepts_planner_decision():
    decision = QueryPlanner.plan(
        "overview",
        intent_result=_intent(),
        profile=KnowledgeProfile(),
        settings=_settings(),
        query_language="en",
    )
    hit = SearchHit(
        score=0.7,
        source_id=1,
        chunk_index=0,
        title="About",
        url="https://example.com/about",
        source_type="page",
        text="We provide services to clients worldwide.",
        document_type="about_page",
        page_role="organization_overview",
        final_score=0.7,
        source_language="en",
    )
    plan = EvidencePlanner(db=None).plan(
        [hit],
        planner_decision=decision,
        profile=KnowledgeProfile(),
        query="overview",
        query_language="en",
        settings=_settings(),
    )
    assert plan.selected
    assert set(plan.knowledge_plan.required_slots) == set(decision.knowledge_plan.required_slots)


@pytest.mark.unit
def test_coverage_validator_deterministic():
    kp = KnowledgePlan(
        information_need="entity_overview",
        answer_type="overview",
        required_slots=("identity", "activity"),
        optional_slots=(),
        forbidden_slots=(),
    )
    from app.services.evidence_planning.types import (
        EvidenceCandidate,
        EvidencePlan,
        EvidencePlanSufficiency,
        SelectedEvidence,
    )

    cand = EvidenceCandidate(
        candidate_id="1:0",
        source_id=1,
        chunk_index=0,
        url="https://x",
        title="About",
        heading="",
        text="identity activity",
        document_type="about_page",
        page_role="organization_overview",
        source_purpose="about company",
        language="en",
        available_aspects=frozenset({"identity", "activity"}),
    )
    selected = [
        SelectedEvidence(
            candidate=cand,
            aspects_new=("identity", "activity"),
            aspects_covered=("identity", "activity"),
            marginal_value=1.0,
            selection_reason="test",
            final_order=1,
        )
    ]
    evidence_plan = EvidencePlan(
        intent="entity_overview",
        knowledge_plan=kp,
        selected=selected,
        rejected=[],
        sufficiency=EvidencePlanSufficiency(
            level="sufficient",
            required_aspects_covered=("identity", "activity"),
            required_aspects_missing=(),
        ),
        contradictions=[],
        packing_decisions=[],
        candidate_count=1,
    )
    knowledge_cov = validate_knowledge_coverage(selected, kp)
    assert knowledge_cov.coverage_pct == 1.0
    snapshot = build_coverage_snapshot(
        evidence_plan=evidence_plan,
        knowledge_plan=kp,
        answer_text="This organization provides services.",
    )
    assert snapshot.answer is not None
    assert snapshot.answer.coverage_pct >= 0.0


@pytest.mark.unit
def test_rag_contract_documents_stages():
    assert RAG_CONTRACT_VERSION == "rag-v2.1"
    owners = {stage: owner for stage, owner in RAG_PIPELINE_STAGES}
    assert owners["query_planning"] == "QueryPlanner"
    assert owners["evidence_planning"] == "EvidencePlanner"
    assert owners["coverage_validation"] == "AnswerCoverageValidator"
