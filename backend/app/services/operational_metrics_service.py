"""Operational metrics — gauges + maintenance counters (RFC-100 Steps 025 / 037 / 061).

Uses version services and TensionSurfacingService as authorities for gauges.
Step 061 process-local counters are observed separately and appended at exposition.

Does not mutate settings, bump versions, persist tensions, or query epistemic ORM
tables directly.

Tension gauges count **epistemic hypotheses** (possible memory issues), not
confirmed knowledge errors. Only ``support_deficit`` and explicit ``conflict``
are measured. No active maintenance is implied by non-zero values.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.epistemic_memory import EpistemicMemoryService
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.maintenance_metrics import get_maintenance_counters
from app.services.memory_version_service import MemoryVersionService
from app.services.tension_surfacing import TensionSurfacingService
from app.services.tension_surfacing.tension_surfacing_service import (
    METRICS_CLAIM_SCAN_LIMIT,
    TensionCountSummary,
)


@dataclass(frozen=True)
class OperationalGauges:
    memory_version: int
    knowledge_version: int
    open_tensions: int
    support_deficit_tensions: int
    conflict_tensions: int
    tension_claim_scan_limit: int = METRICS_CLAIM_SCAN_LIMIT


class OperationalMetricsService:
    """Collect read-only operational gauges."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def collect_gauges(self) -> OperationalGauges:
        tension_counts = self._tension_counts()
        return OperationalGauges(
            memory_version=MemoryVersionService(self.db).get(),
            knowledge_version=KnowledgeVersionService(self.db).get(),
            open_tensions=tension_counts.open_tensions,
            support_deficit_tensions=tension_counts.support_deficit_tensions,
            conflict_tensions=tension_counts.conflict_tensions,
            tension_claim_scan_limit=tension_counts.claim_scan_limit,
        )

    def _tension_counts(self) -> TensionCountSummary:
        memory = EpistemicMemoryService(self.db)
        return TensionSurfacingService(memory).summarize_counts(
            claim_limit=METRICS_CLAIM_SCAN_LIMIT
        )

    def render_prometheus(self) -> str:
        """Prometheus text exposition format (RFC-100 ``kos_*`` names)."""
        gauges = self.collect_gauges()
        counters = get_maintenance_counters().snapshot()
        lines = [
            "# HELP kos_memory_version Epistemic memory revision counter (MemoryVersionService).",
            "# TYPE kos_memory_version gauge",
            f"kos_memory_version {gauges.memory_version}",
            "# HELP kos_knowledge_version Indexed knowledge revision counter (KnowledgeVersionService).",
            "# TYPE kos_knowledge_version gauge",
            f"kos_knowledge_version {gauges.knowledge_version}",
            (
                "# HELP kos_open_tensions Surfaced epistemic hypotheses "
                "(possible memory issues; not confirmed knowledge errors). "
                f"Bounded to {gauges.tension_claim_scan_limit} active claims."
            ),
            "# TYPE kos_open_tensions gauge",
            f"kos_open_tensions {gauges.open_tensions}",
            (
                "# HELP kos_support_deficit_tensions Possible support-deficit hypotheses "
                "(active claims lacking support evidence)."
            ),
            "# TYPE kos_support_deficit_tensions gauge",
            f"kos_support_deficit_tensions {gauges.support_deficit_tensions}",
            (
                "# HELP kos_conflict_tensions Possible conflict hypotheses "
                "(explicit conflict evidence roles only)."
            ),
            "# TYPE kos_conflict_tensions gauge",
            f"kos_conflict_tensions {gauges.conflict_tensions}",
            (
                "# HELP kos_maintenance_cycles_total Completed maintenance cycle "
                "results observed (process-local; includes no-op skip outcomes)."
            ),
            "# TYPE kos_maintenance_cycles_total counter",
            f"kos_maintenance_cycles_total {counters.maintenance_cycles_total}",
            (
                "# HELP kos_investigations_planned Selected investigation plans "
                "observed from MaintenanceCycleResult.selected_plans (process-local)."
            ),
            "# TYPE kos_investigations_planned counter",
            f"kos_investigations_planned {counters.investigations_planned}",
            (
                "# HELP kos_investigations_failed_total Investigation plans with "
                "status=failed observed from InvestigationCycleResult (process-local)."
            ),
            "# TYPE kos_investigations_failed_total counter",
            f"kos_investigations_failed_total {counters.investigations_failed_total}",
        ]
        # Step 066 remediation — minimal Ask pool / cancel signals (no Dashboard).
        from app.core.ask_db import (
            cancel_cleanup_count,
            park_count,
            pool_timeout_count,
            unpark_count,
        )
        from app.core.database import pool_diagnostics

        pool = pool_diagnostics()
        lines.extend(
            [
                "# HELP kos_db_pool_checked_out Current SQLAlchemy pool checked-out connections.",
                "# TYPE kos_db_pool_checked_out gauge",
                f"kos_db_pool_checked_out {int(pool.get('checked_out') or 0)}",
                "# HELP kos_db_pool_timeout_total Ask-path QueuePool acquire timeouts (process-local).",
                "# TYPE kos_db_pool_timeout_total counter",
                f"kos_db_pool_timeout_total {pool_timeout_count()}",
                "# HELP kos_ask_db_park_total Ask sessions parked before LLM wait (process-local).",
                "# TYPE kos_ask_db_park_total counter",
                f"kos_ask_db_park_total {park_count()}",
                "# HELP kos_ask_db_unpark_total Ask sessions reopened after LLM wait (process-local).",
                "# TYPE kos_ask_db_unpark_total counter",
                f"kos_ask_db_unpark_total {unpark_count()}",
                "# HELP kos_ask_cancel_cleanup_total Stream cancel cleanups observed (process-local).",
                "# TYPE kos_ask_cancel_cleanup_total counter",
                f"kos_ask_cancel_cleanup_total {cancel_cleanup_count()}",
            ]
        )
        return "\n".join(lines) + "\n"
