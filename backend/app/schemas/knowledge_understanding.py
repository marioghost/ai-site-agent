"""API schemas for Knowledge Understanding Layer (Phase 0)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class UnderstandingConceptSummary(BaseModel):
    concept_key: str
    label: str
    evidence_count: int = 0
    confidence: float = 0.0
    canonical_source_id: int | None = None


class UnderstandingCoverageGap(BaseModel):
    concept_key: str
    label: str
    reason: str
    evidence_count: int = 0


class KnowledgeUnderstandingSummaryResponse(BaseModel):
    enabled: bool
    knowledge_version: int | None = None
    snapshot_id: int | None = None
    status: str
    representation: str = "concept_index"
    concept_count: int = 0
    evidence_count: int = 0
    built_at: str | None = None
    build_duration_ms: int = 0
    top_concepts: list[UnderstandingConceptSummary] = Field(default_factory=list)
    coverage_gaps: list[UnderstandingCoverageGap] = Field(default_factory=list)
    error_message: str | None = None
    last_error_message: str | None = None
    last_error_at: str | None = None


class ConceptSourcesResponse(BaseModel):
    concept_key: str
    label: str | None = None
    sources: list[dict] = Field(default_factory=list)
