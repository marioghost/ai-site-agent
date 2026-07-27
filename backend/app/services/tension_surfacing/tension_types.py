"""In-memory tension DTOs (RFC-100 Step 034 — not persisted).

Semantic rule (do not blur this):

- A Tension is **not** knowledge.
- A Tension is **not** a belief.
- A Tension is **not** a fact.

A Tension is an **epistemic hypothesis**: a conservative, read-only signal that a
*possible* problem may exist inside Epistemic Memory (for example a possible
support deficit, conflict, incompleteness, or authority gap). Surfacing a
tension never asserts that the problem is confirmed or that the underlying
claims are false.
"""
from __future__ import annotations

from dataclasses import dataclass


TENSION_SUPPORT_DEFICIT = "support_deficit"
TENSION_CONFLICT = "conflict"


@dataclass(frozen=True)
class TensionView:
    """Epistemic hypothesis about a possible problem in Epistemic Memory.

    Read-only, in-memory only. Not knowledge, not a belief, and not a fact.
    """

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
