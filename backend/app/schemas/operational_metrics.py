"""Operational gauge schemas (RFC-100 Steps 025 / 037)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class OperationalGaugeRead(BaseModel):
    """A single read-only operational gauge."""

    name: str
    value: float
    help: str
    type: str = "gauge"


class OperationalMetricsResponse(BaseModel):
    """JSON snapshot of operational gauges for operators and tests.

    Tension fields count epistemic hypotheses (possible memory issues), not
    confirmed knowledge errors. Additive vs Step 025 — existing version fields
    are unchanged.
    """

    memory_version: int = Field(description="Epistemic memory revision (MemoryVersionService)")
    knowledge_version: int = Field(
        description="Indexed knowledge revision (KnowledgeVersionService)"
    )
    open_tensions: int = Field(
        description=(
            "Surfaced epistemic hypotheses (possible memory issues). "
            "Bounded active-claim scan — not confirmed knowledge errors."
        )
    )
    support_deficit_tensions: int = Field(
        description="Possible support-deficit hypotheses"
    )
    conflict_tensions: int = Field(
        description="Possible conflict hypotheses (explicit evidence roles only)"
    )
    tension_claim_scan_limit: int = Field(
        description="Max active claims scanned when counting tensions"
    )
