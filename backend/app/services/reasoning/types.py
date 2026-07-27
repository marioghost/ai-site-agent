"""Reasoning request/result DTOs (RFC-100 Steps 039–043).

Independent of HTTP schemas and ORM models. Unsupported cognitive fields stay
``None`` where not yet decided. Step 043 fills evidence sufficiency as advisory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.rag_service import RagResult
from app.services.reasoning.evidence_sufficiency import EvidenceSufficiencyAssessment

REASONING_PATH_LEGACY = "legacy"
REASONING_PATH_SERVICE = "reasoning_service"


@dataclass(frozen=True)
class ReasoningRequest:
    """Inputs for a single reasoning invocation (stateless)."""

    message: str
    session_id: str | None
    request_id: str
    user_ip: str | None = None
    user_agent: str | None = None
    referrer: str | None = None
    debug: bool = False
    bypass_cache: bool = False


@dataclass
class ReasoningResult:
    """Typed reasoning outcome.

    ``legacy_result`` carries the existing RagResult so callers keep assembling
    ChatResponse unchanged. Sufficiency (Step 043) is advisory — does not alter
    speech act or final language.
    """

    legacy_result: RagResult
    reasoning_path: str = REASONING_PATH_SERVICE
    information_need: str | None = None
    evidence_sufficient: bool | None = None
    speech_act: str | None = None
    refusal_reason: str | None = None
    clarification_needed: bool | None = None
    reasoning_diagnostics: dict[str, Any] = field(default_factory=dict)
    sufficiency: EvidenceSufficiencyAssessment | None = None

    def as_rag_result(self) -> RagResult:
        """Return the passthrough RagResult with path + advisory diagnostics."""
        result = self.legacy_result
        result.reasoning_path = self.reasoning_path
        if self.reasoning_diagnostics:
            result.reasoning_diagnostics = dict(self.reasoning_diagnostics)
        return result
