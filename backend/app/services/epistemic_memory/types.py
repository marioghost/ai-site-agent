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


@dataclass(frozen=True)
class ProvenanceAwareMemorySummary:
    """Real vs test split for Epistemic Health dashboards (UI/ops)."""

    real_claims: int
    test_claims: int
    real_active_claims: int
    test_active_claims: int
    real_superseded_claims: int
    test_superseded_claims: int
    real_observations: int
    test_observations: int
    real_evidence_links: int
    test_evidence_links: int
    source_intelligence_claims: int
    all_claims: int
    all_observations: int
    all_evidence_links: int

    def as_dict(self) -> dict[str, int]:
        return {
            "real_claims": self.real_claims,
            "test_claims": self.test_claims,
            "real_active_claims": self.real_active_claims,
            "test_active_claims": self.test_active_claims,
            "real_superseded_claims": self.real_superseded_claims,
            "test_superseded_claims": self.test_superseded_claims,
            "real_observations": self.real_observations,
            "test_observations": self.test_observations,
            "real_evidence_links": self.real_evidence_links,
            "test_evidence_links": self.test_evidence_links,
            "source_intelligence_claims": self.source_intelligence_claims,
            "all_claims": self.all_claims,
            "all_observations": self.all_observations,
            "all_evidence_links": self.all_evidence_links,
        }
