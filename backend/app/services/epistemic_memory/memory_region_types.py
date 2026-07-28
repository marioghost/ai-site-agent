"""Typed DTOs for Memory region read views (RFC-100 Step 046).

Region is a bounded declarative filter — not a persisted entity.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from app.services.epistemic_memory.provenance_scope import ProvenanceScope

MAX_REGION_LIMIT = 500
DEFAULT_REGION_LIMIT = 50
SPARSE_MEMORY_THRESHOLD = 3

# Stable limitation codes (not free-form prose).
LIMIT_COMPLETENESS_UNKNOWN = "completeness_unknown"
LIMIT_SPARSE_MEMORY = "sparse_memory"
LIMIT_LANGUAGE_FILTER_UNAVAILABLE = "language_filter_unavailable"
LIMIT_MALFORMED_SCOPE_ROWS_EXCLUDED = "malformed_scope_rows_excluded"
LIMIT_EVIDENCE_NOT_REQUESTED = "evidence_not_requested"
LIMIT_NO_MATCHING_CLAIMS = "no_matching_claims"


def _coerce_positive_source_id(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer, not bool")
    if not isinstance(value, int):
        raise ValueError(
            f"{field} must be a positive integer, got {type(value).__name__}"
        )
    if value <= 0:
        raise ValueError(f"{field} must be a positive integer, got {value}")
    return value


def readonly_mapping(data: dict[str, Any] | None) -> Mapping[str, Any] | None:
    """Shallow read-only copy of a mapping for DTO safety.

  Nested dict/list values inside ``scope_json`` remain mutable if present;
  only top-level keys are protected via ``MappingProxyType``.
    """
    if data is None:
        return None
    return MappingProxyType(dict(data))


@dataclass(frozen=True)
class MemoryRegionRequest:
    """Bounded filter for reading claims linked to explicit source scope."""

    source_id: int | None = None
    source_ids: tuple[int, ...] | None = None
    information_need: str | None = None
    topic_key: str | None = None
    language: str | None = None
    page_roles: tuple[str, ...] | None = None
    document_types: tuple[str, ...] | None = None
    proposal_kinds: tuple[str, ...] | None = None
    provenance_scope: ProvenanceScope = ProvenanceScope.REAL
    active_only: bool = True
    epistemic_statuses: tuple[str, ...] | None = None
    limit: int = DEFAULT_REGION_LIMIT
    offset: int = 0
    include_evidence: bool = True
    include_superseded: bool = False

    def normalized_source_ids(self) -> tuple[int, ...]:
        ids: list[int] = []
        if self.source_id is not None:
            ids.append(_coerce_positive_source_id(self.source_id, field="source_id"))
        if self.source_ids:
            for index, sid in enumerate(self.source_ids):
                ids.append(
                    _coerce_positive_source_id(sid, field=f"source_ids[{index}]")
                )
        if not ids:
            raise ValueError("MemoryRegionRequest requires source_id or source_ids")
        return tuple(sorted(set(ids)))

    def normalized_limit(self) -> int:
        return max(1, min(int(self.limit), MAX_REGION_LIMIT))

    def normalized_offset(self) -> int:
        return max(0, int(self.offset))

    def normalized_page_roles(self) -> frozenset[str] | None:
        if not self.page_roles:
            return None
        return frozenset(r.strip().lower() for r in self.page_roles if r and r.strip())

    def normalized_document_types(self) -> frozenset[str] | None:
        if not self.document_types:
            return None
        return frozenset(t.strip().lower() for t in self.document_types if t and t.strip())

    def normalized_proposal_kinds(self) -> frozenset[str] | None:
        if not self.proposal_kinds:
            return None
        return frozenset(k.strip().lower() for k in self.proposal_kinds if k and k.strip())

    def normalized_epistemic_statuses(self) -> frozenset[str] | None:
        if not self.epistemic_statuses:
            return None
        return frozenset(s.strip().lower() for s in self.epistemic_statuses if s and s.strip())

    def normalized_topic_key(self) -> str | None:
        if not self.topic_key or not self.topic_key.strip():
            return None
        return self.topic_key.strip().lower()

    def validate_lifecycle(self) -> None:
        """Reject ambiguous active_only / include_superseded combinations."""
        if not self.active_only and not self.include_superseded:
            raise ValueError(
                "ambiguous lifecycle: active_only=False with include_superseded=False; "
                "set include_superseded=True to include superseded claims"
            )

    def include_superseded_claims(self) -> bool:
        """Whether superseded claims are included after lifecycle validation."""
        self.validate_lifecycle()
        if self.include_superseded:
            return True
        return not self.active_only


@dataclass(frozen=True)
class MemoryEvidenceRef:
    evidence_link_id: int
    observation_ref_id: int
    role: str
    provenance_kind: str
    provenance_ref: str | None
    source_id: int | None
    chunk_id: int | None
    excerpt: str | None
    content_hash: str | None
    observed_at: datetime | None


@dataclass(frozen=True)
class MemoryClaimView:
    claim_id: int
    proposition: str
    attribution: str
    epistemic_status: str
    confidence: float | None
    provenance_kind: str
    provenance_ref: str | None
    scope: Mapping[str, Any] | None
    superseded: bool
    superseded_by_id: int | None
    revision_of_id: int | None
    evidence: tuple[MemoryEvidenceRef, ...]
    evidence_loaded: bool
    has_support: bool | None
    has_conflict: bool | None
    support_observation_source_ids: tuple[int, ...]


@dataclass(frozen=True)
class MemoryRegionView:
    request_echo: MemoryRegionRequest
    matched_claims: tuple[MemoryClaimView, ...]
    total_matched: int
    provenance_excluded_count: int
    excluded_superseded_count: int
    excluded_scope_mismatch_count: int
    provenance_summary: Mapping[str, int]
    page_provenance_summary: Mapping[str, int]
    limitations: tuple[str, ...]
    completeness_unknown: bool = True

    @property
    def excluded_test_count(self) -> int:
        """Deprecated alias for :attr:`provenance_excluded_count`."""
        return self.provenance_excluded_count

    def limitation_set(self) -> frozenset[str]:
        return frozenset(self.limitations)
