"""QueryPlanner — single pre-retrieval orchestration entry."""
from __future__ import annotations

from time import perf_counter

from app.models.settings import Settings
from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.rag_planning.budget_resolver import resolve_retrieval_budget
from app.services.rag_planning.contracts import (
    GenerationDecision,
    PipelineDecisionRecord,
    PlannerDecision,
    PlanningDecision,
    RetrievalDecision,
)
from app.services.rag_planning.plan_builders import build_answer_plan, build_knowledge_plan
from app.services.rag_planning.strategy_resolver import resolve_retrieval_strategy
from app.services.retrieval_engine.query_understanding import QueryUnderstandingService
from app.services.retrieval_intent_service import RetrievalIntentResult


def _decision_chain(
    *,
    information_need: str,
    answer_type: str,
    strategy,
    budget,
) -> tuple[PipelineDecisionRecord, ...]:
    return (
        PipelineDecisionRecord(
            stage="query_planning",
            owner="QueryPlanner",
            action="planned",
            reason="knowledge_and_answer_plans_created",
            metadata={"information_need": information_need, "answer_type": answer_type},
        ),
        PipelineDecisionRecord(
            stage="retrieval_strategy",
            owner="QueryPlanner",
            action="resolved",
            reason=strategy.strategy_reasons[0] if strategy.strategy_reasons else "default",
            metadata=strategy.to_dict(),
        ),
        PipelineDecisionRecord(
            stage="retrieval_budget",
            owner="QueryPlanner",
            action="resolved",
            reason=budget.budget_reasons[0] if budget.budget_reasons else "default",
            metadata=budget.to_dict(),
        ),
    )


class QueryPlanner:
    """Compose planning modules into one immutable PlannerDecision."""

    @classmethod
    def plan(
        cls,
        query: str,
        *,
        intent_result: RetrievalIntentResult,
        profile: KnowledgeProfile,
        settings: Settings,
        query_language: str,
    ) -> PlannerDecision:
        t0 = perf_counter()
        information_need = intent_result.legacy_intent or intent_result.intent or "unknown"

        understanding = QueryUnderstandingService.analyze(
            query,
            intent_result=intent_result,
            query_language=query_language,
        )

        knowledge_plan = build_knowledge_plan(
            information_need=information_need,
            understanding=understanding,
            profile=profile,
        )
        answer_plan = build_answer_plan(knowledge_plan=knowledge_plan)
        strategy = resolve_retrieval_strategy(
            knowledge_plan,
            settings,
            is_broad=bool(intent_result.is_broad),
        )
        budget = resolve_retrieval_budget(knowledge_plan, strategy, settings)

        return PlannerDecision(
            query=query,
            query_language=query_language,
            planning=PlanningDecision(
                information_need=information_need,
                knowledge_plan=knowledge_plan,
                understanding=understanding,
            ),
            generation=GenerationDecision(answer_plan=answer_plan),
            retrieval=RetrievalDecision(strategy=strategy, budget=budget),
            plan_ms=int((perf_counter() - t0) * 1000),
            decision_chain=_decision_chain(
                information_need=information_need,
                answer_type=understanding.expected_answer_type,
                strategy=strategy,
                budget=budget,
            ),
        )
