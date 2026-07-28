"""Typed DTOs for Memory region read views (RFC-100 Step 046).

Region is a bounded declarative filter — not a persisted entity.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
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
LIMIT_CORPUS_SCOPE_UNCONFIGURED = "corpus_scope_unconfigured"
LIMIT_CORPUS_SCOPE_INVALID = "corpus_scope_invalid"
LIMIT_CORPUS_SCOPE_EMPTY = "corpus_scope_empty"
LIMIT_CORPUS_SCOPE_INCOMPLETE = "corpus_scope_incomplete"


class MemoryCorpusScope(str, Enum):
    DEPLOYMENT = "deployment"


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
    """Shallow read-only copy of a mapping for DTO safety."""
    if data is None:
        return None
    return MappingProxyType(dict(data))


@dataclass(frozen=True)
class MemoryIsolationScope:
    """Isolation boundary — exactly one of corpus_scope or source_ids."""

    corpus_scope: MemoryCorpusScope | None = None
    source_ids: tuple[int, ...] | None = None

    def validate(self) -> None:
        has_corpus = self.corpus_scope is not None
        has_sources = bool(self.source_ids)
        if has_corpus and has_sources:
            raise ValueError(
                "MemoryIsolationScope requires exactly one of corpus_scope or source_ids"
            )
        if not has_corpus and not has_sources:
            raise ValueError(
                "MemoryIsolationScope requires exactly one of corpus_scope or source_ids"
            )
        if self.corpus_scope is not None and self.corpus_scope is not MemoryCorpusScope.DEPLOYMENT:
            raise ValueError(
                f"unsupported corpus_scope={self.corpus_scope!r}; expected deployment"
            )
        if self.source_ids:
            for index, sid in enumerate(self.source_ids):
                _coerce_positive_source_id(sid, field=f"source_ids[{index}]")

    def normalized_source_ids(self) -> tuple[int, ...]:
        self.validate()
        if self.source_ids:
            return tuple(sorted(set(self.source_ids)))
        return ()


@dataclass(frozen=True)
class MemoryRegionRequest:
    """Bounded filter for reading claims within an isolation scope."""

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
    isolation: MemoryIsolationScope | None = None
    # Legacy compatibility — use isolation=MemoryIsolationScope(source_ids=...) instead.
    source_id: int | None = None
    source_ids: tuple[int, ...] | None = None

    def normalized_isolation(self) -> MemoryIsolationScope:
        if self.isolation is not None:
            if self.source_id is not None or self.source_ids:
                raise ValueError(
                    "MemoryRegionRequest cannot combine isolation with source_id/source_ids"
                )
            self.isolation.validate()
            return self.isolation

        ids: list[int] = []
        if self.source_id is not None:
            ids.append(_coerce_positive_source_id(self.source_id, field="source_id"))
        if self.source_ids:
            for index, sid in enumerate(self.source_ids):
                ids.append(
                    _coerce_positive_source_id(sid, field=f"source_ids[{index}]")
                )
        if not ids:
            raise ValueError(
                "MemoryRegionRequest requires isolation or source_id/source_ids"
            )
        scope = MemoryIsolationScope(source_ids=tuple(sorted(set(ids))))
        scope.validate()
        return scope

    def normalized_source_ids(self) -> tuple[int, ...]:
        """Legacy helper — explicit source isolation only."""
        isolation = self.normalized_isolation()
        if isolation.corpus_scope is not None:
            raise ValueError(
                "normalized_source_ids() requires explicit source_ids isolation"
            )
        return isolation.normalized_source_ids()

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
        if not self.active_only and not self.include_superseded:
            raise ValueError(
                "ambiguous lifecycle: active_only=False with include_superseded=False; "
                "set include_superseded=True to include superseded claims"
            )

    def include_superseded_claims(self) -> bool:
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
    isolation_scope_echo: MemoryIsolationScope
    corpus_scope: MemoryCorpusScope | None
    corpus_hosts: tuple[str, ...]
    corpus_anchor_source_ids: tuple[int, ...]
    corpus_anchor_source_count: int
    corpus_scope_configured: bool
    corpus_scope_complete: bool
    corpus_limitations: tuple[str, ...]
    completeness_unknown: bool = True

    @property
    def excluded_test_count(self) -> int:
        return self.provenance_excluded_count

    def limitation_set(self) -> frozenset[str]:
        return frozenset(self.limitations)

    def corpus_boundary_fingerprint(self) -> str | None:
        if self.corpus_scope is None or not self.corpus_scope_configured:
            return None
        from app.services.epistemic_memory.memory_corpus_resolver import (
            CORPUS_BOUNDARY_VERSION,
            MemoryCorpusBoundary,
        )

        boundary = MemoryCorpusBoundary(
            corpus_scope=self.corpus_scope,
            hosts=self.corpus_hosts,
            configured=self.corpus_scope_configured,
            invalid_entries=(),
            settings_row_id=None,
            complete=self.corpus_scope_complete,
        )
        return boundary.fingerprint()
