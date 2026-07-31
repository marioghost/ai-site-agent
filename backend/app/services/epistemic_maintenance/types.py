"""Investigation plan DTOs (RFC-100 Step 058 — ephemeral, not persisted)."""
from __future__ import annotations

from dataclasses import dataclass

ACTION_SEEK_CORROBORATION = "seek_corroboration"
ACTION_SEEK_ADJUDICATION = "seek_adjudication"


@dataclass(frozen=True)
class InvestigationPlan:
    """Ranked investigation plan produced by EpistemicMaintenanceService.

    In-memory only. Not persisted. Not executed in Step 058.
    """

    plan_id: str
    tension_type: str
    claim_ids: tuple[int, ...]
    observation_ref_ids: tuple[int, ...]
    evidence_link_ids: tuple[int, ...]
    action: str
    priority: float
    rationale: str
