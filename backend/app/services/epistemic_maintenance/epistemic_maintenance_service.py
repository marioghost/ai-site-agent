"""EpistemicMaintenanceService — agenda ranking only (RFC-100 Step 058).

Ranks TensionView hypotheses into ephemeral InvestigationPlan DTOs.
No persistence, no execution, no chat/retrieval/indexing side effects.
"""
from __future__ import annotations

from app.services.epistemic_maintenance.types import (
    ACTION_SEEK_ADJUDICATION,
    ACTION_SEEK_CORROBORATION,
    InvestigationPlan,
)
from app.services.tension_surfacing import (
    TENSION_CONFLICT,
    TENSION_SUPPORT_DEFICIT,
    TensionSurfacingService,
    TensionView,
)

# Implementation scores only — not part of the Engineering Package contract.
# Must preserve: conflict strictly outranks support_deficit.
_SCORE_CONFLICT = 2.0
_SCORE_SUPPORT_DEFICIT = 1.0
_SCORE_OTHER = 0.0


class EpistemicMaintenanceService:
    """Rank current tensions into ordered investigation plans."""

    def __init__(self, tension_surfacing: TensionSurfacingService) -> None:
        self._surfacing = tension_surfacing

    def rank(
        self,
        tensions: list[TensionView] | None = None,
    ) -> list[InvestigationPlan]:
        """Return investigation plans sorted by Priority Policy v1.

        When ``tensions`` is omitted, loads via ``surface_tensions()``.
        Passing an explicit list enables pure unit tests with zero DB writes.
        """
        if tensions is None:
            tensions = self._surfacing.surface_tensions()
        if not tensions:
            return []

        ordered = sorted(tensions, key=_tension_sort_key)
        return [_to_plan(t) for t in ordered]


def _tension_sort_key(tension: TensionView) -> tuple:
    """Priority Policy v1: conflict > support_deficit; tie → claim_ids[0] asc."""
    type_rank = _type_sort_rank(tension.tension_type)
    if not tension.claim_ids:
        claim_key: tuple[int, int] = (1, 0)
    else:
        claim_key = (0, tension.claim_ids[0])
    return (
        type_rank,
        claim_key[0],
        claim_key[1],
        tension.claim_ids,
        tension.observation_ref_ids,
        tension.evidence_link_ids,
        tension.summary,
    )


def _type_sort_rank(tension_type: str) -> int:
    if tension_type == TENSION_CONFLICT:
        return 0
    if tension_type == TENSION_SUPPORT_DEFICIT:
        return 1
    return 2


def _priority_score(tension_type: str) -> float:
    if tension_type == TENSION_CONFLICT:
        return _SCORE_CONFLICT
    if tension_type == TENSION_SUPPORT_DEFICIT:
        return _SCORE_SUPPORT_DEFICIT
    return _SCORE_OTHER


def _action_for(tension_type: str) -> str:
    if tension_type == TENSION_SUPPORT_DEFICIT:
        return ACTION_SEEK_CORROBORATION
    if tension_type == TENSION_CONFLICT:
        return ACTION_SEEK_ADJUDICATION
    return ACTION_SEEK_CORROBORATION


def _to_plan(tension: TensionView) -> InvestigationPlan:
    priority = _priority_score(tension.tension_type)
    action = _action_for(tension.tension_type)
    plan_id = _plan_id(tension)
    rationale = (
        f"{tension.tension_type} ranked for {action} "
        f"(claims={list(tension.claim_ids)})"
    )
    return InvestigationPlan(
        plan_id=plan_id,
        tension_type=tension.tension_type,
        claim_ids=tension.claim_ids,
        observation_ref_ids=tension.observation_ref_ids,
        evidence_link_ids=tension.evidence_link_ids,
        action=action,
        priority=priority,
        rationale=rationale,
    )


def _plan_id(tension: TensionView) -> str:
    claims = ",".join(str(c) for c in tension.claim_ids) or "-"
    obs = ",".join(str(o) for o in tension.observation_ref_ids) or "-"
    ev = ",".join(str(e) for e in tension.evidence_link_ids) or "-"
    return f"{tension.tension_type}:{claims}:{obs}:{ev}"
