"""Resolve retrieval budget from plan, strategy, and settings."""
from __future__ import annotations

from app.models.settings import Settings
from app.services.rag_planning.contracts import KnowledgePlan, RetrievalBudget, RetrievalStrategy


def resolve_retrieval_budget(
    knowledge_plan: KnowledgePlan,
    strategy: RetrievalStrategy,
    settings: Settings,
) -> RetrievalBudget:
    configured = int(getattr(settings, "retrieval_candidate_count", 30) or 30)
    chunk_pool = max(strategy.top_k_dense, strategy.top_k_lexical, configured // 2)
    chunk_pool = min(chunk_pool, max(configured, 12))

    document_limit = strategy.document_limit
    rerank_limit = strategy.rerank_limit
    inject_limit = 12 if strategy.enable_broad_inject else 0
    max_chunks = int(getattr(settings, "max_chunks_per_page", 2) or 2)
    reasons: list[str] = [f"retrieval_candidate_count={configured}"]

    if strategy.prefer_broad_pool:
        chunk_pool = max(chunk_pool, 50)
        document_limit = max(document_limit, 20)
        reasons.append("broad_pool_budget")
    elif strategy.prefer_faq_roles or knowledge_plan.answer_type == "contact":
        chunk_pool = min(chunk_pool, 20)
        document_limit = min(document_limit, 8)
        reasons.append("narrow_pool_budget")
    elif strategy.prefer_documentation_roles:
        chunk_pool = max(chunk_pool, 40)
        document_limit = max(document_limit, 15)
        reasons.append("documentation_pool_budget")
    elif strategy.prefer_overview_roles:
        chunk_pool = max(24, min(chunk_pool, 32))
        document_limit = max(document_limit, 10)
        reasons.append("overview_pool_budget")

    return RetrievalBudget(
        chunk_pool_size=chunk_pool,
        document_limit=document_limit,
        rerank_limit=rerank_limit,
        inject_limit=inject_limit,
        max_chunks_per_document=max_chunks,
        budget_reasons=tuple(reasons),
    )
