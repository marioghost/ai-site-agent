"""Observe Step 059/060 ephemeral results into process-local counters (Step 061).

Observation only. Fail-open. Does not mutate DTOs or re-execute work.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.services.executive.investigation_types import (
    STATUS_FAILED,
    InvestigationCycleResult,
)
from app.services.executive.maintenance_types import MaintenanceCycleResult
from app.services.maintenance_metrics.counters import get_maintenance_counters

logger = get_logger(__name__)


def observe_maintenance_metrics(
    cycle: MaintenanceCycleResult,
    investigation: InvestigationCycleResult | None = None,
) -> None:
    """Observe one maintenance invocation's DTOs on that execution path.

    Each completed MaintenanceCycleResult and InvestigationCycleResult produced
    by a single maintenance invocation shall be observed exactly once by that
    invocation. Does not detect duplicate observations from repeated external
    calls. Fail-open: never raises into the maintenance path.
    """
    try:
        counters = get_maintenance_counters()
        counters.record_cycle()
        counters.record_planned(len(cycle.selected_plans))
        if investigation is not None:
            failed = sum(
                1 for plan in investigation.plan_results if plan.status == STATUS_FAILED
            )
            counters.record_failed(failed)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Maintenance metrics observation failed: %s", type(exc).__name__)
