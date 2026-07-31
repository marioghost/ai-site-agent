"""Process-local maintenance / investigation counters (RFC-100 Step 061).

Thread-safe. Non-durable. Reset on process restart.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class MaintenanceCounterSnapshot:
    """Immutable snapshot of process-local maintenance counters."""

    maintenance_cycles_total: int
    investigations_planned: int
    investigations_failed_total: int


class MaintenanceInvestigationCounters:
    """Thread-safe process-local aggregation for Step 061."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cycles = 0
        self._planned = 0
        self._failed = 0

    def record_cycle(self) -> None:
        with self._lock:
            self._cycles += 1

    def record_planned(self, count: int) -> None:
        if count <= 0:
            return
        with self._lock:
            self._planned += count

    def record_failed(self, count: int) -> None:
        if count <= 0:
            return
        with self._lock:
            self._failed += count

    def snapshot(self) -> MaintenanceCounterSnapshot:
        with self._lock:
            return MaintenanceCounterSnapshot(
                maintenance_cycles_total=self._cycles,
                investigations_planned=self._planned,
                investigations_failed_total=self._failed,
            )

    def reset(self) -> None:
        """Test / new-instance helper. Not a product API."""
        with self._lock:
            self._cycles = 0
            self._planned = 0
            self._failed = 0


# Process-local singleton — resets when the process restarts.
_COUNTERS = MaintenanceInvestigationCounters()


def get_maintenance_counters() -> MaintenanceInvestigationCounters:
    return _COUNTERS


def reset_maintenance_counters() -> None:
    """Reset process-local counters (tests / fresh service instance)."""
    _COUNTERS.reset()
