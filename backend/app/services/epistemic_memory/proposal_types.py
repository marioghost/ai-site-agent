"""In-memory claim proposal DTOs (RFC-100 Step 029 — not persisted)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceProposal:
    """Suggested evidence anchor for a future observation_ref row."""

    excerpt: str | None
    content_hash: str | None
    source_id: int | None
    chunk_id: int | None
    observation_key_hint: str | None
    role: str = "support"


@dataclass(frozen=True)
class ClaimProposal:
    """Candidate claim derived from Source Intelligence — proposal only."""

    proposition: str
    scope_json: str | None
    epistemic_status: str
    attributed_to: str
    provenance_kind: str
    provenance_ref: str
    confidence: float | None
    source_id: int
    source_url: str | None
    proposal_kind: str
    evidence: tuple[EvidenceProposal, ...]
