"""In-memory tension DTOs (RFC-100 Step 034 — not persisted)."""
from __future__ import annotations

from dataclasses import dataclass


TENSION_SUPPORT_DEFICIT = "support_deficit"
TENSION_CONFLICT = "conflict"


@dataclass(frozen=True)
class TensionView:
    """Detected epistemic tension — read-only, surfaced in memory only."""

    tension_type: str
    claim_ids: tuple[int, ...]
    observation_ref_ids: tuple[int, ...]
    evidence_link_ids: tuple[int, ...]
    summary: str

    def as_dict(self) -> dict:
        return {
            "tension_type": self.tension_type,
            "claim_ids": list(self.claim_ids),
            "observation_ref_ids": list(self.observation_ref_ids),
            "evidence_link_ids": list(self.evidence_link_ids),
            "summary": self.summary,
        }
