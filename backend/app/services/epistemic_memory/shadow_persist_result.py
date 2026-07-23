"""Shadow write result counters (RFC-100 Step 030)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShadowPersistResult:
    observations_created: int = 0
    claims_created: int = 0
    evidence_links_created: int = 0

    @property
    def any_created(self) -> bool:
        return (
            self.observations_created + self.claims_created + self.evidence_links_created
        ) > 0
