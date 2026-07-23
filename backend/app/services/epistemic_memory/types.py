"""Read DTOs for EpistemicMemoryService (RFC-100 Step 028)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ObservationRefView:
    id: int
    source_id: int | None
    chunk_id: int | None
    observation_key: str
    content_hash: str
    excerpt: str | None
    observed_at: datetime
    provenance_kind: str
    provenance_ref: str | None
    extraction_version: str | None
    created_at: datetime


@dataclass(frozen=True)
class ClaimView:
    id: int
    proposition: str
    scope_json: str | None
    epistemic_status: str
    attributed_to: str
    provenance_kind: str
    provenance_ref: str | None
    confidence: float | None
    superseded_by_id: int | None
    revision_of_id: int | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class EvidenceLinkView:
    id: int
    claim_id: int
    observation_ref_id: int
    role: str
    provenance_kind: str
    provenance_ref: str | None
    link_confidence: float | None
    created_at: datetime


@dataclass(frozen=True)
class EpistemicMemorySummary:
    observation_ref_count: int
    claim_count: int
    active_claim_count: int
    evidence_link_count: int

    def as_dict(self) -> dict[str, int]:
        return {
            "observation_ref_count": self.observation_ref_count,
            "claim_count": self.claim_count,
            "active_claim_count": self.active_claim_count,
            "evidence_link_count": self.evidence_link_count,
        }
