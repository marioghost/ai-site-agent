"""Implementation-specific periodic invocation for Step 059 maintenance cycles.

Not a Scheduler framework. Reuses the existing in-process background-worker
pattern. Harmless when rollout flag is disabled and budget is 0.

After Step 059 selection, invokes Step 060 investigation execution when plans
were selected. Does not change Step 059 gates or selection semantics.
"""
from __future__ import annotations

import threading

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.repositories.settings_repository import SettingsRepository
from app.services.executive.investigation_execution import (
    execute_selected_investigations,
)
from app.services.executive.maintenance_orchestration import (
    orchestrate_maintenance_cycle,
)
from app.services.maintenance_metrics import observe_maintenance_metrics

logger = get_logger(__name__)

# Internal constant — not product Settings / not Engineering Package contract.
_INTERVAL_SECONDS = 300


class MaintenanceCycleInvoker:
    """Daemon loop that periodically invokes the maintenance orchestration entry."""

    def __init__(self, interval_seconds: int = _INTERVAL_SECONDS) -> None:
        self._interval_seconds = max(5, interval_seconds)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="maintenance-cycle",
            daemon=True,
        )
        self._thread.start()
        logger.info("Maintenance cycle invoker started")

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Maintenance cycle invocation failed: %s", exc)
            self._stop.wait(self._interval_seconds)

    def run_once(self) -> None:
        db = SessionLocal()
        try:
            cycle = orchestrate_maintenance_cycle(db)
            investigation = None
            if cycle.selected_plans:
                settings = SettingsRepository(db).get_or_create()
                investigation = execute_selected_investigations(
                    db, cycle.selected_plans, settings
                )
            # Step 061: observe DTOs on this invocation path (fail-open).
            observe_maintenance_metrics(cycle, investigation)
        finally:
            db.close()


maintenance_cycle_invoker = MaintenanceCycleInvoker()
