"""Understanding / tension surfacing API schemas (RFC-100 Step 035).

A Tension is an epistemic hypothesis about a possible problem in Epistemic
Memory — not knowledge, not a belief, and not a fact.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.tension_surfacing.tension_types import TensionView


class TensionRead(BaseModel):
    """API DTO for one epistemic hypothesis (Tension).

    Provenance fields explain *why* the hypothesis was surfaced without exposing
    ORM models. Clients must treat each item as a possible problem signal, not
    as confirmed knowledge.
    """

    tension_type: str = Field(
        ...,
        description=(
            "Hypothesis class (e.g. support_deficit, conflict). "
            "Indicates a possible problem — not a confirmed fact."
        ),
    )
    claim_ids: list[int] = Field(
        ...,
        description="Claim IDs involved in this hypothesis (Epistemic Memory).",
    )
    observation_ref_ids: list[int] = Field(
        ...,
        description="Observation ref IDs that support the detection rule.",
    )
    evidence_link_ids: list[int] = Field(
        ...,
        description="Evidence link IDs that support the detection rule.",
    )
    summary: str = Field(
        ...,
        description=(
            "Human-readable explanation of why this epistemic hypothesis "
            "was surfaced (provenance narrative)."
        ),
    )

    @classmethod
    def from_view(cls, view: TensionView) -> TensionRead:
        return cls(
            tension_type=view.tension_type,
            claim_ids=list(view.claim_ids),
            observation_ref_ids=list(view.observation_ref_ids),
            evidence_link_ids=list(view.evidence_link_ids),
            summary=view.summary,
        )


class TensionListResponse(BaseModel):
    """Paginated list of epistemic hypotheses (tensions)."""

    items: list[TensionRead]
    total: int
    page: int
    page_size: int
