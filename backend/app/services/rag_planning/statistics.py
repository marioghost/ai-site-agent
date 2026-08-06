"""Deterministic quality statistics — no ML."""
from __future__ import annotations

from app.services.evidence_planning.types import EvidencePlan
from app.services.rag_planning.contracts import CoverageSnapshot, PlannerDecision, QualityStatistics
from app.services.retrieval_engine.types import RetrievalQualityMetrics


def compute_quality_statistics(
    *,
    planner_decision: PlannerDecision,
    evidence_plan: EvidencePlan | None,
    coverage: CoverageSnapshot | None,
    retrieval_quality: RetrievalQualityMetrics | None = None,
) -> QualityStatistics:
    planner_quality = 0.5
    if evidence_plan and evidence_plan.selected:
        avg_fitness = sum(s.candidate.authority_fitness for s in evidence_plan.selected) / len(
            evidence_plan.selected
        )
        planner_quality = min(1.0, avg_fitness)
    if planner_decision.plan_ms > 0:
        planner_quality = min(1.0, planner_quality + 0.05)

    retrieval_quality_score = 0.5
    if coverage and coverage.retrieval and coverage.retrieval.avg_score:
        retrieval_quality_score = min(1.0, max(0.2, coverage.retrieval.avg_score))
    elif retrieval_quality and retrieval_quality.documents_found:
        if retrieval_quality.avg_final_score:
            retrieval_quality_score = min(1.0, max(0.2, retrieval_quality.avg_final_score))
        elif retrieval_quality.documents_after_reranking:
            retrieval_quality_score = min(
                1.0, retrieval_quality.documents_after_reranking / max(1, retrieval_quality.documents_found)
            )

    coverage_quality = 0.0
    answer_quality = None
    if coverage:
        coverage_quality = coverage.knowledge.coverage_pct
        if coverage.answer is not None:
            answer_quality = coverage.answer.coverage_pct

    return QualityStatistics(
        retrieval_quality=retrieval_quality_score,
        coverage_quality=coverage_quality,
        planner_quality=planner_quality,
        answer_quality=answer_quality,
    )
