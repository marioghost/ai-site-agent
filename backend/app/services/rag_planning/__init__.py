"""RAG planning v2 — pre-retrieval orchestration and coverage validation."""
from app.services.rag_planning.contracts import (
    AnswerCoverageReport,
    AnswerPlan,
    CoverageSnapshot,
    EvidenceCoverageReport,
    GenerationDecision,
    KnowledgeCoverageReport,
    KnowledgePlan,
    PipelineDecisionRecord,
    PlannerDecision,
    PlanningDecision,
    QualityStatistics,
    RetrievalBudget,
    RetrievalCoverageReport,
    RetrievalDecision,
    RetrievalStrategy,
)
from app.services.rag_planning.coverage_validator import (
    AnswerCoverageValidator,
    build_coverage_snapshot,
    validate_answer_coverage,
    validate_evidence_coverage,
    validate_knowledge_coverage,
)
from app.services.rag_planning.query_planner import QueryPlanner
from app.services.rag_planning.rag_contract import RAG_CONTRACT_VERSION, RAG_PIPELINE_STAGES
from app.services.rag_planning.intent_taxonomy import OVERVIEW_INTENTS, is_overview_intent
from app.services.rag_planning.statistics import compute_quality_statistics

__all__ = (
    "AnswerCoverageReport",
    "AnswerCoverageValidator",
    "AnswerPlan",
    "CoverageSnapshot",
    "EvidenceCoverageReport",
    "GenerationDecision",
    "KnowledgeCoverageReport",
    "KnowledgePlan",
    "PipelineDecisionRecord",
    "PlannerDecision",
    "PlanningDecision",
    "QualityStatistics",
    "QueryPlanner",
    "RetrievalBudget",
    "RetrievalCoverageReport",
    "RetrievalDecision",
    "RetrievalStrategy",
    "RAG_CONTRACT_VERSION",
    "RAG_PIPELINE_STAGES",
    "OVERVIEW_INTENTS",
    "is_overview_intent",
    "build_coverage_snapshot",
    "compute_quality_statistics",
    "validate_answer_coverage",
    "validate_evidence_coverage",
    "validate_knowledge_coverage",
)
