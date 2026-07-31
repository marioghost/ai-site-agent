"""Maintenance cycle orchestration (RFC-100 Step 059).

Coordinates gate → rank → select. No Gateway I/O, no Memory writes,
no ranking policy changes, no Settings/API/UI.
"""
from __future__ import annotations

import os
import threading

from sqlalchemy.orm import Session

from app.services.epistemic_maintenance import EpistemicMaintenanceService
from app.services.epistemic_memory import EpistemicMemoryService
from app.services.executive.maintenance_types import (
    SKIP_ALREADY_RUNNING,
    SKIP_BUDGET_ZERO,
    SKIP_EMPTY_PLANS,
    SKIP_FLAG_OFF,
    SKIP_RANK_FAILED,
    STATUS_ERROR,
    STATUS_OK,
    MaintenanceCycleResult,
)
from app.services.tension_surfacing import TensionSurfacingService

# Concrete names are implementation detail (Engineering Package).
_ENV_ROLLOUT_FLAG = "MAINTENANCE_EXECUTION_ENABLED"
_ENV_BUDGET = "MAINTENANCE_INVESTIGATIONS_PER_CYCLE"

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"", "0", "false", "no", "off"})

_cycle_lock = threading.Lock()


def rollout_flag_enabled(environ: dict[str, str] | None = None) -> bool:
    """Environment-backed rollout flag. Invalid values fail closed to disabled."""
    env = environ if environ is not None else os.environ
    raw = str(env.get(_ENV_ROLLOUT_FLAG, "")).strip().lower()
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    return False


def operational_budget(environ: dict[str, str] | None = None) -> int:
    """Environment-backed budget. Missing/invalid/negative fail closed to 0."""
    env = environ if environ is not None else os.environ
    raw = str(env.get(_ENV_BUDGET, "")).strip()
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError:
        return 0
    if value < 0:
        return 0
    return value


def orchestrate_maintenance_cycle(
    db: Session,
    *,
    environ: dict[str, str] | None = None,
    rank_service: EpistemicMaintenanceService | None = None,
) -> MaintenanceCycleResult:
    """Public maintenance orchestration entry.

    Chat methods on ExecutiveService are untouched. Not gated by
    KNOWLEDGE_OS_EXECUTIVE_ENABLED.
    """
    if not _cycle_lock.acquire(blocking=False):
        return MaintenanceCycleResult(
            status=STATUS_OK,
            skip_reason=SKIP_ALREADY_RUNNING,
            selected_plans=(),
            plans_considered=0,
        )
    try:
        return _run_cycle(db, environ=environ, rank_service=rank_service)
    finally:
        _cycle_lock.release()


def _run_cycle(
    db: Session,
    *,
    environ: dict[str, str] | None,
    rank_service: EpistemicMaintenanceService | None,
) -> MaintenanceCycleResult:
    if not rollout_flag_enabled(environ):
        return MaintenanceCycleResult(
            status=STATUS_OK,
            skip_reason=SKIP_FLAG_OFF,
            selected_plans=(),
            plans_considered=0,
        )

    budget = operational_budget(environ)
    if budget == 0:
        return MaintenanceCycleResult(
            status=STATUS_OK,
            skip_reason=SKIP_BUDGET_ZERO,
            selected_plans=(),
            plans_considered=0,
        )

    service = rank_service
    if service is None:
        memory = EpistemicMemoryService(db)
        surfacing = TensionSurfacingService(memory)
        service = EpistemicMaintenanceService(surfacing)

    try:
        plans = service.rank()
    except Exception:
        return MaintenanceCycleResult(
            status=STATUS_ERROR,
            skip_reason=SKIP_RANK_FAILED,
            selected_plans=(),
            plans_considered=0,
        )

    if not plans:
        return MaintenanceCycleResult(
            status=STATUS_OK,
            skip_reason=SKIP_EMPTY_PLANS,
            selected_plans=(),
            plans_considered=0,
        )

    selected = tuple(plans[:budget])
    return MaintenanceCycleResult(
        status=STATUS_OK,
        skip_reason=None,
        selected_plans=selected,
        plans_considered=len(plans),
    )
