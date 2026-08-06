"""RAG pipeline contract — stage ownership reference."""
from __future__ import annotations

RAG_PIPELINE_STAGES: tuple[tuple[str, str], ...] = (
    ("query", "User"),
    ("query_planning", "QueryPlanner"),
    ("retrieval", "DocumentFirstRetrievalPipeline"),
    ("candidate_enrichment", "RetrievalPipelineService"),
    ("evidence_planning", "EvidencePlanner"),
    ("context_serialization", "RetrievalContextBuilder"),
    ("prompt_assembly", "CompactPromptBuilder"),
    ("generation", "LlmGenerationService"),
    ("coverage_validation", "AnswerCoverageValidator"),
    ("evidence_sufficiency", "assess_evidence_sufficiency"),
    ("diagnostics", "RetrievalDiagnostics"),
)

RAG_CONTRACT_VERSION = "rag-v2.1"
