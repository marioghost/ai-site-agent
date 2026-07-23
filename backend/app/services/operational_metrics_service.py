"""Operational metrics — read-only gauges for operators (RFC-100 Step 025).

Uses version services as the sole authority; does not mutate settings or bump versions.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.memory_version_service import MemoryVersionService


@dataclass(frozen=True)
class OperationalGauges:
    memory_version: int
    knowledge_version: int


class OperationalMetricsService:
    """Collect read-only operational gauges."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def collect_gauges(self) -> OperationalGauges:
        return OperationalGauges(
            memory_version=MemoryVersionService(self.db).get(),
            knowledge_version=KnowledgeVersionService(self.db).get(),
        )

    def render_prometheus(self) -> str:
        """Prometheus text exposition format (RFC-100 ``kos_*`` gauge names)."""
        gauges = self.collect_gauges()
        lines = [
            "# HELP kos_memory_version Epistemic memory revision counter (MemoryVersionService).",
            "# TYPE kos_memory_version gauge",
            f"kos_memory_version {gauges.memory_version}",
            "# HELP kos_knowledge_version Indexed knowledge revision counter (KnowledgeVersionService).",
            "# TYPE kos_knowledge_version gauge",
            f"kos_knowledge_version {gauges.knowledge_version}",
        ]
        return "\n".join(lines) + "\n"
