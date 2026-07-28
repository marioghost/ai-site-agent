"""Read-only Memory region facade (RFC-100 Step 046)."""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.repositories.settings_repository import SettingsRepository
from app.services.epistemic_memory.memory_corpus_resolver import (
    bounded_diagnostic_source_ids,
    resolve_corpus_source_ids,
    resolve_deployment_boundary,
)
from app.services.epistemic_memory.memory_region_types import (
    LIMIT_COMPLETENESS_UNKNOWN,
    LIMIT_CORPUS_SCOPE_EMPTY,
    LIMIT_CORPUS_SCOPE_INCOMPLETE,
    LIMIT_CORPUS_SCOPE_INVALID,
    LIMIT_CORPUS_SCOPE_UNCONFIGURED,
    LIMIT_EVIDENCE_NOT_REQUESTED,
    LIMIT_LANGUAGE_FILTER_UNAVAILABLE,
    LIMIT_MALFORMED_SCOPE_ROWS_EXCLUDED,
    LIMIT_NO_MATCHING_CLAIMS,
    LIMIT_SPARSE_MEMORY,
    SPARSE_MEMORY_THRESHOLD,
    MemoryClaimView,
    MemoryCorpusScope,
    MemoryEvidenceRef,
    MemoryIsolationScope,
    MemoryRegionRequest,
    MemoryRegionView,
    readonly_mapping,
)
from app.services.epistemic_memory.provenance_scope import (
    ProvenanceScope,
    claim_matches_scope,
)


def _parse_scope_json(raw: str | None) -> tuple[dict[str, Any] | None, bool]:
    if raw is None or not str(raw).strip():
        return None, False
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None, True
    if not isinstance(parsed, dict):
        return None, True
    return parsed, False


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _scope_field_matches(scope: dict[str, Any] | None, key: str, wanted: frozenset[str]) -> bool:
    if scope is None:
        return False
    val = _norm(scope.get(key))
    return val is not None and val in wanted


def _topic_matches(scope: dict[str, Any] | None, topic_key: str) -> bool:
    if scope is None:
        return False
    for key in ("main_topic", "topic_key"):
        val = _norm(scope.get(key))
        if val == topic_key:
            return True
    return False


def _provenance_counter(rows: list[EpistemicClaim]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for claim in rows:
        counter[claim.provenance_kind or "unknown"] += 1
    return dict(sorted(counter.items()))


class MemoryRegionReader:
    """Deterministic bounded claim reads for explicit isolation scope."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def read_region(self, request: MemoryRegionRequest) -> MemoryRegionView:
        request.validate_lifecycle()
        isolation = request.normalized_isolation()
        limit = request.normalized_limit()
        offset = request.normalized_offset()
        page_roles = request.normalized_page_roles()
        document_types = request.normalized_document_types()
        proposal_kinds = request.normalized_proposal_kinds()
        epistemic_statuses = request.normalized_epistemic_statuses()
        topic_key = request.normalized_topic_key()
        include_superseded = request.include_superseded_claims()

        limitations: list[str] = [LIMIT_COMPLETENESS_UNKNOWN]
        corpus_limitations: list[str] = []
        if not request.include_evidence:
            limitations.append(LIMIT_EVIDENCE_NOT_REQUESTED)
        if request.language and request.language.strip():
            limitations.append(LIMIT_LANGUAGE_FILTER_UNAVAILABLE)

        corpus_scope: MemoryCorpusScope | None = None
        corpus_hosts: tuple[str, ...] = ()
        corpus_anchor_source_ids: tuple[int, ...] = ()
        corpus_anchor_source_count = 0
        corpus_scope_configured = False
        corpus_scope_complete = True

        if isolation.corpus_scope == MemoryCorpusScope.DEPLOYMENT:
            corpus_scope = MemoryCorpusScope.DEPLOYMENT
            settings = SettingsRepository(self._db).get()
            boundary = resolve_deployment_boundary(settings)
            corpus_hosts = boundary.hosts
            if boundary.invalid_entries:
                corpus_limitations.append(LIMIT_CORPUS_SCOPE_INVALID)
            if not boundary.configured:
                corpus_limitations.append(LIMIT_CORPUS_SCOPE_UNCONFIGURED)
                return self._empty_corpus_view(
                    request=request,
                    isolation=isolation,
                    corpus_scope=corpus_scope,
                    corpus_hosts=corpus_hosts,
                    corpus_limitations=tuple(dict.fromkeys(corpus_limitations)),
                    limitations=limitations,
                )
            corpus_scope_configured = True
            corpus_anchor_source_ids = resolve_corpus_source_ids(self._db, boundary)
            corpus_anchor_source_count = len(corpus_anchor_source_ids)
            if not corpus_anchor_source_ids:
                corpus_limitations.append(LIMIT_CORPUS_SCOPE_EMPTY)
                limitations.append(LIMIT_NO_MATCHING_CLAIMS)
                return self._empty_corpus_view(
                    request=request,
                    isolation=isolation,
                    corpus_scope=corpus_scope,
                    corpus_hosts=corpus_hosts,
                    corpus_anchor_source_ids=(),
                    corpus_anchor_source_count=0,
                    corpus_scope_configured=True,
                    corpus_scope_complete=boundary.complete,
                    corpus_limitations=tuple(dict.fromkeys(corpus_limitations)),
                    limitations=limitations,
                )
            if not boundary.complete:
                corpus_limitations.append(LIMIT_CORPUS_SCOPE_INCOMPLETE)
                corpus_scope_complete = False
            source_ids = corpus_anchor_source_ids
        else:
            source_ids = isolation.normalized_source_ids()
            corpus_scope_complete = True

        malformed_scope_seen = False

        stmt = (
            select(EpistemicClaim)
            .join(EvidenceLink, EvidenceLink.claim_id == EpistemicClaim.id)
            .join(ObservationRef, ObservationRef.id == EvidenceLink.observation_ref_id)
            .where(ObservationRef.source_id.in_(source_ids))
            .distinct()
            .order_by(EpistemicClaim.id.asc())
        )
        candidates = list(self._db.scalars(stmt).all())

        provenance_excluded = 0
        excluded_superseded = 0
        excluded_scope = 0
        matched_rows: list[EpistemicClaim] = []

        scope_filters_requested = any(
            [page_roles, document_types, proposal_kinds, topic_key]
        )

        for claim in candidates:
            if not claim_matches_scope(
                provenance_kind=claim.provenance_kind,
                attributed_to=claim.attributed_to,
                scope=request.provenance_scope,
            ):
                provenance_excluded += 1
                continue

            is_superseded = claim.superseded_by_id is not None
            if is_superseded and not include_superseded:
                excluded_superseded += 1
                continue

            if epistemic_statuses is not None:
                status = _norm(claim.epistemic_status) or ""
                if status not in epistemic_statuses:
                    excluded_scope += 1
                    continue

            scope, malformed = _parse_scope_json(claim.scope_json)
            if malformed:
                malformed_scope_seen = True
                if scope_filters_requested:
                    excluded_scope += 1
                    continue

            if page_roles is not None and not _scope_field_matches(
                scope, "page_role", page_roles
            ):
                excluded_scope += 1
                continue
            if document_types is not None and not _scope_field_matches(
                scope, "document_type", document_types
            ):
                excluded_scope += 1
                continue
            if proposal_kinds is not None and not _scope_field_matches(
                scope, "proposal_kind", proposal_kinds
            ):
                excluded_scope += 1
                continue
            if topic_key is not None and not _topic_matches(scope, topic_key):
                excluded_scope += 1
                continue

            matched_rows.append(claim)

        matched_rows.sort(key=lambda c: c.id)

        if malformed_scope_seen:
            limitations.append(LIMIT_MALFORMED_SCOPE_ROWS_EXCLUDED)

        total_matched = len(matched_rows)
        if total_matched == 0:
            limitations.append(LIMIT_NO_MATCHING_CLAIMS)
        elif total_matched < SPARSE_MEMORY_THRESHOLD:
            limitations.append(LIMIT_SPARSE_MEMORY)

        provenance_summary = readonly_mapping(_provenance_counter(matched_rows)) or readonly_mapping({})

        page_rows = matched_rows[offset : offset + limit]
        page_provenance_summary = readonly_mapping(_provenance_counter(page_rows)) or readonly_mapping({})

        evidence_by_claim: dict[int, list[MemoryEvidenceRef]] = {}
        if request.include_evidence and page_rows:
            evidence_by_claim = self._load_evidence_for_claims(
                [c.id for c in page_rows],
                allowed_source_ids=set(source_ids),
            )

        claim_views: list[MemoryClaimView] = []
        evidence_loaded = request.include_evidence

        for claim in page_rows:
            evidence = tuple(evidence_by_claim.get(claim.id, []))
            if evidence_loaded:
                has_support: bool | None = any(e.role == "support" for e in evidence)
                has_conflict: bool | None = any(e.role == "conflict" for e in evidence)
                support_source_ids = tuple(
                    sorted(
                        {
                            e.source_id
                            for e in evidence
                            if e.role == "support" and e.source_id is not None
                        }
                    )
                )
            else:
                has_support = None
                has_conflict = None
                support_source_ids = ()

            scope, _ = _parse_scope_json(claim.scope_json)
            claim_views.append(
                MemoryClaimView(
                    claim_id=claim.id,
                    proposition=claim.proposition,
                    attribution=claim.attributed_to,
                    epistemic_status=claim.epistemic_status,
                    confidence=claim.confidence,
                    provenance_kind=claim.provenance_kind,
                    provenance_ref=claim.provenance_ref,
                    scope=readonly_mapping(scope),
                    superseded=claim.superseded_by_id is not None,
                    superseded_by_id=claim.superseded_by_id,
                    revision_of_id=claim.revision_of_id,
                    evidence=evidence,
                    evidence_loaded=evidence_loaded,
                    has_support=has_support,
                    has_conflict=has_conflict,
                    support_observation_source_ids=support_source_ids,
                )
            )

        diagnostic_ids = bounded_diagnostic_source_ids(corpus_anchor_source_ids)

        return MemoryRegionView(
            request_echo=request,
            matched_claims=tuple(claim_views),
            total_matched=total_matched,
            provenance_excluded_count=provenance_excluded,
            excluded_superseded_count=excluded_superseded,
            excluded_scope_mismatch_count=excluded_scope,
            provenance_summary=provenance_summary,
            page_provenance_summary=page_provenance_summary,
            limitations=tuple(dict.fromkeys(limitations)),
            isolation_scope_echo=isolation,
            corpus_scope=corpus_scope,
            corpus_hosts=corpus_hosts,
            corpus_anchor_source_ids=diagnostic_ids,
            corpus_anchor_source_count=corpus_anchor_source_count,
            corpus_scope_configured=corpus_scope_configured,
            corpus_scope_complete=corpus_scope_complete,
            corpus_limitations=tuple(dict.fromkeys(corpus_limitations)),
            completeness_unknown=True,
        )

    def _empty_corpus_view(
        self,
        *,
        request: MemoryRegionRequest,
        isolation: MemoryIsolationScope,
        corpus_scope: MemoryCorpusScope | None,
        corpus_hosts: tuple[str, ...],
        corpus_limitations: tuple[str, ...],
        limitations: list[str],
        corpus_anchor_source_ids: tuple[int, ...] = (),
        corpus_anchor_source_count: int = 0,
        corpus_scope_configured: bool = False,
        corpus_scope_complete: bool = False,
    ) -> MemoryRegionView:
        return MemoryRegionView(
            request_echo=request,
            matched_claims=(),
            total_matched=0,
            provenance_excluded_count=0,
            excluded_superseded_count=0,
            excluded_scope_mismatch_count=0,
            provenance_summary=readonly_mapping({}),
            page_provenance_summary=readonly_mapping({}),
            limitations=tuple(dict.fromkeys(limitations)),
            isolation_scope_echo=isolation,
            corpus_scope=corpus_scope,
            corpus_hosts=corpus_hosts,
            corpus_anchor_source_ids=bounded_diagnostic_source_ids(corpus_anchor_source_ids),
            corpus_anchor_source_count=corpus_anchor_source_count,
            corpus_scope_configured=corpus_scope_configured,
            corpus_scope_complete=corpus_scope_complete,
            corpus_limitations=corpus_limitations,
            completeness_unknown=True,
        )

    def _load_evidence_for_claims(
        self,
        claim_ids: list[int],
        *,
        allowed_source_ids: set[int],
    ) -> dict[int, list[MemoryEvidenceRef]]:
        if not claim_ids:
            return {}

        stmt = (
            select(EvidenceLink, ObservationRef)
            .join(ObservationRef, ObservationRef.id == EvidenceLink.observation_ref_id)
            .where(EvidenceLink.claim_id.in_(claim_ids))
            .where(ObservationRef.source_id.in_(allowed_source_ids))
            .order_by(EvidenceLink.id.asc())
        )
        rows = self._db.execute(stmt).all()

        by_claim: dict[int, dict[int, MemoryEvidenceRef]] = {}
        for link, obs in rows:
            ref = MemoryEvidenceRef(
                evidence_link_id=link.id,
                observation_ref_id=link.observation_ref_id,
                role=link.role,
                provenance_kind=link.provenance_kind,
                provenance_ref=link.provenance_ref,
                source_id=obs.source_id,
                chunk_id=obs.chunk_id,
                excerpt=obs.excerpt,
                content_hash=obs.content_hash,
                observed_at=obs.observed_at,
            )
            bucket = by_claim.setdefault(link.claim_id, {})
            bucket[link.id] = ref

        return {
            cid: [bucket[k] for k in sorted(bucket)]
            for cid, bucket in by_claim.items()
        }
