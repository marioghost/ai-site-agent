"""Understanding / Epistemic Health API schemas (RFC-100 Step 035 + demo-ready).

A Tension is an epistemic hypothesis about a possible problem in Epistemic
Memory — not knowledge, not a belief, and not a fact.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.services.tension_surfacing.tension_types import TensionView

ProvenanceScopeLiteral = Literal["real", "test", "all"]


class TensionRead(BaseModel):
    """API DTO for one epistemic hypothesis (Tension)."""

    tension_type: str = Field(
        ...,
        description=(
            "Hypothesis class (e.g. support_deficit, conflict). "
            "Indicates a possible problem — not a confirmed fact."
        ),
    )
    claim_ids: list[int]
    observation_ref_ids: list[int]
    evidence_link_ids: list[int]
    summary: str
    provenance_scope: str = Field(
        ...,
        description="real | test | mixed — derived from involved claims.",
    )
    claim_provenance_kinds: list[str] = Field(default_factory=list)
    is_test_data: bool = False

    @classmethod
    def from_view(cls, view: TensionView) -> TensionRead:
        return cls(
            tension_type=view.tension_type,
            claim_ids=list(view.claim_ids),
            observation_ref_ids=list(view.observation_ref_ids),
            evidence_link_ids=list(view.evidence_link_ids),
            summary=view.summary,
            provenance_scope=view.provenance_scope,
            claim_provenance_kinds=list(view.claim_provenance_kinds),
            is_test_data=view.is_test_data,
        )


class TensionListResponse(BaseModel):
    """Paginated list of epistemic hypotheses (tensions)."""

    items: list[TensionRead]
    total: int
    page: int
    page_size: int
    provenance_scope: ProvenanceScopeLiteral


class EpistemicHealthSummaryResponse(BaseModel):
    """Live Epistemic Health summary — provenance-aware, read-only."""

    real_claims: int
    test_claims: int
    real_active_claims: int
    test_active_claims: int
    real_superseded_claims: int
    test_superseded_claims: int
    real_observations: int
    test_observations: int
    real_evidence_links: int
    test_evidence_links: int
    source_intelligence_claims: int
    real_support_deficit_tensions: int
    real_conflict_tensions: int
    real_open_tensions: int
    test_open_tensions: int
    memory_version: int
    memory_shadow_write_enabled: bool
    chat_impact: Literal["not_active"] = "not_active"
    diagnostic_only: bool = True
    experimental: bool = True
