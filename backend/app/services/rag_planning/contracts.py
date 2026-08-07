"""RAG planning contracts — single source of truth for v2 architecture."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.retrieval_engine.query_understanding import QueryUnderstanding


@dataclass(frozen=True)
class KnowledgePlan:
    """WHAT information should be found (retrieval + evidence selection)."""

    information_need: str
    answer_type: str
    required_slots: tuple[str, ...]
    optional_slots: tuple[str, ...]
    forbidden_slots: tuple[str, ...]
    preferred_purposes: tuple[str, ...] = ()
    unsuitable_purposes: tuple[str, ...] = ()
    preferred_document_types: frozenset[str] = frozenset()
    deprioritized_document_types: frozenset[str] = frozenset()
    semantic_focus: str = "general"
    expected_evidence_type: str = "general"
    plan_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "information_need": self.information_need,
            "answer_type": self.answer_type,
            "required_slots": list(self.required_slots),
            "optional_slots": list(self.optional_slots),
            "forbidden_slots": list(self.forbidden_slots),
            "preferred_purposes": list(self.preferred_purposes),
            "unsuitable_purposes": list(self.unsuitable_purposes),
            "preferred_document_types": sorted(self.preferred_document_types),
            "deprioritized_document_types": sorted(self.deprioritized_document_types),
            "semantic_focus": self.semantic_focus,
            "expected_evidence_type": self.expected_evidence_type,
            "plan_reasons": list(self.plan_reasons),
        }


@dataclass(frozen=True)
class AnswerPlan:
    """HOW the answer should be composed — no retrieval slots."""

    answer_type: str
    scope_instruction: str = ""
    required_slot_order: tuple[str, ...] = ()
    optional_slot_order: tuple[str, ...] = ()
    optional_slot_limit: int = 0
    target_words: int = 0
    target_sentences: int = 0
    compact_retry_instruction: str = ""
    plan_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer_type": self.answer_type,
            "scope_instruction": self.scope_instruction,
            "required_slot_order": list(self.required_slot_order),
            "optional_slot_order": list(self.optional_slot_order),
            "optional_slot_limit": self.optional_slot_limit,
            "target_words": self.target_words,
            "target_sentences": self.target_sentences,
            "compact_retry_instruction": self.compact_retry_instruction,
            "plan_reasons": list(self.plan_reasons),
        }

    def for_compact_retry(self) -> "AnswerPlan":
        retry_sentences = max(2, self.target_sentences - 1) if self.target_sentences else 3
        retry_words = max(60, int(self.target_words * 0.7)) if self.target_words else 90
        return AnswerPlan(
            answer_type=self.answer_type,
            scope_instruction=self.compact_retry_instruction or self.scope_instruction,
            required_slot_order=self.required_slot_order,
            optional_slot_order=self.optional_slot_order,
            optional_slot_limit=0,
            target_words=retry_words,
            target_sentences=retry_sentences,
            compact_retry_instruction=self.compact_retry_instruction or self.scope_instruction,
            plan_reasons=(*self.plan_reasons, "compact_retry"),
        )


@dataclass(frozen=True)
class RetrievalStrategy:
    """Declarative retrieval behaviour resolved into numeric limits by budget."""

    profile_name: str
    top_k_dense: int
    top_k_lexical: int
    document_limit: int
    rerank_limit: int
    minimum_score: float
    enable_broad_inject: bool
    prefer_overview_roles: bool
    prefer_documentation_roles: bool
    prefer_faq_roles: bool
    prefer_broad_pool: bool
    strategy_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_name": self.profile_name,
            "top_k_dense": self.top_k_dense,
            "top_k_lexical": self.top_k_lexical,
            "document_limit": self.document_limit,
            "rerank_limit": self.rerank_limit,
            "minimum_score": self.minimum_score,
            "enable_broad_inject": self.enable_broad_inject,
            "prefer_overview_roles": self.prefer_overview_roles,
            "prefer_documentation_roles": self.prefer_documentation_roles,
            "prefer_faq_roles": self.prefer_faq_roles,
            "prefer_broad_pool": self.prefer_broad_pool,
            "strategy_reasons": list(self.strategy_reasons),
        }


@dataclass(frozen=True)
class RetrievalBudget:
    """Resolved retrieval pool limits — sole numeric input for DFP."""

    chunk_pool_size: int
    document_limit: int
    rerank_limit: int
    inject_limit: int
    max_chunks_per_document: int
    budget_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_pool_size": self.chunk_pool_size,
            "document_limit": self.document_limit,
            "rerank_limit": self.rerank_limit,
            "inject_limit": self.inject_limit,
            "max_chunks_per_document": self.max_chunks_per_document,
            "budget_reasons": list(self.budget_reasons),
        }


@dataclass(frozen=True)
class PlanningDecision:
    information_need: str
    knowledge_plan: KnowledgePlan
    understanding: QueryUnderstanding | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "information_need": self.information_need,
            "knowledge_plan": self.knowledge_plan.to_dict(),
            "understanding": self.understanding.to_dict() if self.understanding else None,
        }


@dataclass(frozen=True)
class GenerationDecision:
    answer_plan: AnswerPlan

    def to_dict(self) -> dict[str, Any]:
        return {"answer_plan": self.answer_plan.to_dict()}


@dataclass(frozen=True)
class RetrievalDecision:
    strategy: RetrievalStrategy
    budget: RetrievalBudget

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.to_dict(),
            "budget": self.budget.to_dict(),
        }


@dataclass(frozen=True)
class PipelineDecisionRecord:
    stage: str
    owner: str
    action: str
    reason: str
    candidate_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "owner": self.owner,
            "action": self.action,
            "reason": self.reason,
            "candidate_id": self.candidate_id,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class PlannerDecision:
    """Immutable plan propagated through the entire RAG pipeline."""

    query: str
    query_language: str
    planning: PlanningDecision
    generation: GenerationDecision
    retrieval: RetrievalDecision
    plan_ms: int = 0
    decision_chain: tuple[PipelineDecisionRecord, ...] = ()

    @property
    def information_need(self) -> str:
        return self.planning.information_need

    @property
    def knowledge_plan(self) -> KnowledgePlan:
        return self.planning.knowledge_plan

    @property
    def understanding(self):
        return self.planning.understanding

    @property
    def answer_plan(self) -> AnswerPlan:
        return self.generation.answer_plan

    @property
    def retrieval_strategy(self) -> RetrievalStrategy:
        return self.retrieval.strategy

    @property
    def retrieval_budget(self) -> RetrievalBudget:
        return self.retrieval.budget

    def to_diagnostics(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "query_language": self.query_language,
            "information_need": self.information_need,
            "knowledge_plan": self.knowledge_plan.to_dict(),
            "answer_plan": self.answer_plan.to_dict(),
            "retrieval_strategy": self.retrieval_strategy.to_dict(),
            "retrieval_budget": self.retrieval_budget.to_dict(),
            "understanding": self.understanding.to_dict() if self.understanding else None,
            "plan_ms": self.plan_ms,
            "decision_chain": [d.to_dict() for d in self.decision_chain],
        }


@dataclass(frozen=True)
class RetrievalCoverageReport:
    documents_found: int
    documents_selected: int
    avg_score: float | None
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "documents_found": self.documents_found,
            "documents_selected": self.documents_selected,
            "avg_score": round(self.avg_score, 4) if self.avg_score is not None else None,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class KnowledgeCoverageReport:
    required_covered: tuple[str, ...]
    required_missing: tuple[str, ...]
    coverage_pct: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_covered": list(self.required_covered),
            "required_missing": list(self.required_missing),
            "coverage_pct": round(self.coverage_pct, 4),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class EvidenceCoverageReport:
    level: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level, "reasons": list(self.reasons)}


@dataclass(frozen=True)
class AnswerCoverageReport:
    slot_status: dict[str, str]
    coverage_pct: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_status": self.slot_status,
            "coverage_pct": round(self.coverage_pct, 4),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class CoverageSnapshot:
    knowledge: KnowledgeCoverageReport
    evidence: EvidenceCoverageReport
    retrieval: RetrievalCoverageReport | None = None
    answer: AnswerCoverageReport | None = None

    def to_dict(self) -> dict[str, Any]:
        out = {
            "knowledge": self.knowledge.to_dict(),
            "evidence": self.evidence.to_dict(),
        }
        if self.retrieval is not None:
            out["retrieval"] = self.retrieval.to_dict()
        if self.answer is not None:
            out["answer"] = self.answer.to_dict()
        return out


@dataclass(frozen=True)
class QualityStatistics:
    retrieval_quality: float
    coverage_quality: float
    planner_quality: float
    answer_quality: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "retrieval_quality": round(self.retrieval_quality, 4),
            "coverage_quality": round(self.coverage_quality, 4),
            "planner_quality": round(self.planner_quality, 4),
            "answer_quality": round(self.answer_quality, 4) if self.answer_quality is not None else None,
        }
