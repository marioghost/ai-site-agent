"""Resolve declarative retrieval strategy from plan + settings."""
from __future__ import annotations

from app.models.settings import Settings
from app.services.rag_planning.contracts import KnowledgePlan, RetrievalStrategy
from app.services.rag_planning.intent_taxonomy import (
    CONTACT_INTENTS,
    FAQ_INTENTS,
    NEWS_INTENTS,
    POLICY_INTENTS,
    is_overview_intent,
)
from app.services.retrieval_engine.config import load_retrieval_profile


def resolve_retrieval_strategy(
    knowledge_plan: KnowledgePlan,
    settings: Settings,
    *,
    is_broad: bool = False,
) -> RetrievalStrategy:
    base = load_retrieval_profile(settings)
    intent = knowledge_plan.information_need.lower()
    answer_type = knowledge_plan.answer_type
    reasons: list[str] = [f"profile={base.name}"]

    prefer_overview = is_overview_intent(intent) or answer_type == "overview"
    prefer_documentation = answer_type == "documentation" or intent in POLICY_INTENTS
    prefer_faq = answer_type == "faq" or intent in FAQ_INTENTS
    prefer_broad_pool = answer_type in {"comparison", "listing"}
    enable_broad_inject = is_broad or is_overview_intent(intent)

    top_k_dense = base.top_k_dense
    top_k_lexical = base.top_k_lexical
    document_limit = base.document_limit
    minimum_score = base.minimum_score

    if prefer_faq or intent in CONTACT_INTENTS:
        top_k_dense = min(top_k_dense, 18)
        top_k_lexical = min(top_k_lexical, 18)
        document_limit = min(document_limit, 6)
        reasons.append("narrow_precision_strategy")
        enable_broad_inject = False
    elif prefer_documentation or intent in POLICY_INTENTS:
        top_k_dense = max(top_k_dense, 40)
        top_k_lexical = max(top_k_lexical, 40)
        document_limit = max(document_limit, 12)
        reasons.append("documentation_breadth_strategy")
        enable_broad_inject = False
    elif prefer_broad_pool:
        top_k_dense = max(top_k_dense, 50)
        top_k_lexical = max(top_k_lexical, 50)
        document_limit = max(document_limit, 15)
        minimum_score = min(minimum_score, 0.30)
        reasons.append("comparison_breadth_strategy")
        enable_broad_inject = False
    elif prefer_overview:
        top_k_dense = max(24, min(top_k_dense, 32))
        top_k_lexical = max(24, min(top_k_lexical, 32))
        document_limit = max(document_limit, 8)
        reasons.append("overview_strategy")
    elif intent in NEWS_INTENTS:
        enable_broad_inject = False
        reasons.append("news_strategy")

    return RetrievalStrategy(
        profile_name=base.name,
        top_k_dense=top_k_dense,
        top_k_lexical=top_k_lexical,
        document_limit=document_limit,
        rerank_limit=max(document_limit, base.rerank_limit),
        minimum_score=minimum_score,
        enable_broad_inject=enable_broad_inject,
        prefer_overview_roles=prefer_overview,
        prefer_documentation_roles=prefer_documentation,
        prefer_faq_roles=prefer_faq,
        prefer_broad_pool=prefer_broad_pool,
        strategy_reasons=tuple(reasons),
    )
