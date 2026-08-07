"""Logical types for Knowledge Understanding Layer — no storage coupling."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Concept:
    """A topic the site explains. Embeddings stay adapter-internal."""

    concept_key: str
    label: str
    aliases: tuple[str, ...] = ()
    confidence: float = 0.0
    evidence_count: int = 0
    canonical_source_id: int | None = None


@dataclass(frozen=True)
class EvidenceLink:
    concept_key: str
    source_id: int
    relation: str
    weight: float = 0.0
    confidence: float = 0.0


@dataclass(frozen=True)
class UnderstandingMatch:
    source_id: int
    understanding_score: float
    why: str
    concept_keys: tuple[str, ...] = ()
    url: str = ""
    title: str = ""


@dataclass(frozen=True)
class ResolvedNeed:
    concepts: tuple[Concept, ...] = ()
    need_type: str = "general"
    query_terms: tuple[str, ...] = ()
    resolution_method: str = "none"


@dataclass(frozen=True)
class CoverageGap:
    concept_key: str
    label: str
    reason: str
    evidence_count: int = 0
    confidence: float = 0.0


@dataclass
class UnderstandingSummary:
    enabled: bool
    knowledge_version: int | None
    snapshot_id: int | None
    status: str
    representation: str
    concept_count: int
    evidence_count: int
    built_at: str | None
    build_duration_ms: int
    top_concepts: list[dict] = field(default_factory=list)
    coverage_gaps: list[dict] = field(default_factory=list)
    error_message: str | None = None
    # When status is ready but a newer failed rebuild exists, surface it without
    # mixing error rows into the active concept payload.
    last_error_message: str | None = None
    last_error_at: str | None = None


@runtime_checkable
class QueryNeedInput(Protocol):
    """Minimal query-side input for resolve_query.

    Decouples KUL from retrieval_engine.QueryUnderstanding concrete type while
    remaining structurally compatible with it.
    """

    query: str
    topic: str | None
    expected_answer_type: str
    semantic_focus: str
    intent: str
    focus_terms: list[str]
