"""Shared RAG planning helpers for unit tests."""
from __future__ import annotations

from app.models.settings import Settings
from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.rag_planning.contracts import PlannerDecision
from app.services.rag_planning.query_planner import QueryPlanner
from app.services.retrieval_intent_service import RetrievalIntentResult


def planner_decision_for_test(
    query: str = "overview",
    *,
    intent: str = "entity_overview",
    broad: bool = True,
    profile: KnowledgeProfile | None = None,
    settings: Settings | None = None,
    query_language: str = "en",
) -> PlannerDecision:
    return QueryPlanner.plan(
        query,
        intent_result=RetrievalIntentResult(
            intent=intent,
            legacy_intent=intent,
            is_broad=broad,
            answer_strategy="overview" if "overview" in intent else "generic",
        ),
        profile=profile or KnowledgeProfile(),
        settings=settings or Settings(),
        query_language=query_language,
    )
