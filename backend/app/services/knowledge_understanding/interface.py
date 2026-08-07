"""KnowledgeUnderstandingLayer — capability interface (no storage APIs)."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.services.knowledge_understanding.models import (
    Concept,
    CoverageGap,
    QueryNeedInput,
    ResolvedNeed,
    UnderstandingMatch,
    UnderstandingSummary,
)


@runtime_checkable
class KnowledgeUnderstandingLayer(Protocol):
    """Site-wide understanding capabilities. Callers never see indexes or graphs."""

    def resolve_query(
        self,
        understanding: QueryNeedInput,
        *,
        query_embedding: list[float] | None = None,
    ) -> ResolvedNeed:
        """What knowledge does this query need?"""

    def find_evidence(
        self,
        need: ResolvedNeed,
        *,
        limit: int = 24,
    ) -> list[UnderstandingMatch]:
        """Which sources contain that knowledge?"""

    def canonical_for(self, concept_key: str) -> int | None:
        """Which source is authoritative for this knowledge?"""

    def related_knowledge(
        self,
        concept_key: str,
        *,
        limit: int = 8,
    ) -> list[Concept]:
        """What adjacent knowledge might help?"""

    def coverage_gaps(self, *, limit: int = 40) -> list[CoverageGap]:
        """What knowledge is missing or weak?"""

    def explain_match(
        self,
        source_id: int,
        need: ResolvedNeed,
    ) -> str:
        """Why does this evidence fit the need? (human language)."""

    def list_concepts(self, *, limit: int = 100) -> list[Concept]:
        """What concepts does this site explain?"""

    def concept_by_key(self, concept_key: str) -> Concept | None:
        """Lookup one concept by stable key."""

    def sources_for_concept(self, concept_key: str) -> list[UnderstandingMatch]:
        """Which sources explain concept X?"""

    def summary(self) -> UnderstandingSummary:
        """Health / coverage snapshot for diagnostics and admin read models."""

    def understanding_trace(
        self,
        understanding: QueryNeedInput,
        *,
        query_embedding: list[float] | None = None,
        selected_limit: int = 3,
    ) -> dict:
        """Human-language understanding diagnostics (not structure dumps)."""
