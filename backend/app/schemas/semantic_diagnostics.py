"""Semantic diagnostics v2 schema stubs (RFC-100 Step 013).

Defines additive debug/diagnostics fields for future reasoning phases.
Stubs are empty and null-safe until Step 014+ populates them behind flags.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UnderstandingTraceStepRead(BaseModel):
    """Single phase in a human-readable understanding trace (stub)."""

    phase: str = ""
    status: Literal["pending", "skipped", "completed", "failed"] = "pending"
    summary: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class UnderstandingTraceRead(BaseModel):
    """Stub container for semantic reasoning trace (RFC-100 Step 013).

    Default empty — populated in Release 0.2+ when reasoning is wired.
    """

    version: Literal["stub"] = "stub"
    populated: bool = False
    summary: str | None = None
    steps: list[UnderstandingTraceStepRead] = Field(default_factory=list)


class ChatDiagnosticsEnvelope(BaseModel):
    """Documented extension to persisted chat diagnostics JSON.

    Extra keys from legacy persistence are allowed for backward compatibility.
    """

    model_config = ConfigDict(extra="allow")

    understanding_trace: UnderstandingTraceRead | None = None


def empty_understanding_trace() -> UnderstandingTraceRead:
    """Return the canonical empty understanding trace stub."""
    return UnderstandingTraceRead()


def semantic_debug_fields(*, debug: bool) -> dict[str, Any]:
    """Additive debug-only fields for diagnostics payloads (Step 013).

    Returns an empty dict when ``debug`` is False so production responses
    omit semantic stubs unless debug/diagnostics is enabled.
    """
    if not debug:
        return {}
    return {"understanding_trace": empty_understanding_trace().model_dump()}


def merge_semantic_debug_fields(
    payload: dict[str, Any] | None,
    *,
    debug: bool,
) -> dict[str, Any]:
    """Merge semantic debug stubs into an existing diagnostics dict."""
    merged = dict(payload or {})
    merged.update(semantic_debug_fields(debug=debug))
    return merged
