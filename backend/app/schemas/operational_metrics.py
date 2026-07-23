"""Operational gauge schemas (RFC-100 Step 025)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class OperationalGaugeRead(BaseModel):
    """A single read-only operational gauge."""

    name: str
    value: float
    help: str
    type: str = "gauge"


class OperationalMetricsResponse(BaseModel):
    """JSON snapshot of operational gauges for operators and tests."""

    memory_version: int = Field(description="Epistemic memory revision (MemoryVersionService)")
    knowledge_version: int = Field(
        description="Indexed knowledge revision (KnowledgeVersionService)"
    )
