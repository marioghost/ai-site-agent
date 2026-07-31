"""Ephemeral maintenance cycle result (RFC-100 Step 059)."""
from __future__ import annotations

from dataclasses import dataclass

from app.services.epistemic_maintenance import InvestigationPlan

SKIP_FLAG_OFF = "flag_off"
SKIP_BUDGET_ZERO = "budget_zero"
SKIP_EMPTY_PLANS = "empty_plans"
SKIP_ALREADY_RUNNING = "already_running"
SKIP_RANK_FAILED = "rank_failed"

STATUS_OK = "ok"
STATUS_ERROR = "error"


@dataclass(frozen=True)
class MaintenanceCycleResult:
    """In-memory cycle outcome. Not persisted. Not ORM."""

    status: str
    skip_reason: str | None
    selected_plans: tuple[InvestigationPlan, ...]
    plans_considered: int
