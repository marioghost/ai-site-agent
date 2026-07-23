"""Internal read/write API for Epistemic Memory tables (RFC-100 Steps 028–030).

Reads are always available. Writes are idempotent shadow persistence — only called
from Memory Integration when ``memory_shadow_write_enabled`` is True.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.models.source import Source
from app.services.epistemic_memory.epistemic_memory_write_service import (
    EpistemicMemoryWriteService,
)
from app.services.epistemic_memory.proposal_types import ClaimProposal
from app.services.epistemic_memory.shadow_persist_result import ShadowPersistResult
from app.services.epistemic_memory.types import (
    ClaimView,
    EpistemicMemorySummary,
    EvidenceLinkView,
    ObservationRefView,
)
from app.services.source_intelligence_service import SourceProfile

DEFAULT_LIMIT = 50
MAX_LIMIT = 500


class EpistemicMemoryService:
    """Read/write access to observation_ref, claim, and evidence_link."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def persist_claim_proposals(
        self,
        proposals: list[ClaimProposal],
        *,
        source: Source | None = None,
        profile: SourceProfile | None = None,
        observed_at: datetime | None = None,
    ) -> ShadowPersistResult:
        """Idempotent shadow persistence — Memory Integration only."""
        return EpistemicMemoryWriteService(self.db).persist_claim_proposals(
            proposals,
            source=source,
            profile=profile,
            observed_at=observed_at,
        )

    def get_observation_ref(
        self,
        *,
        observation_ref_id: int | None = None,
        observation_key: str | None = None,
    ) -> ObservationRefView | None:
        if observation_ref_id is None and not observation_key:
            return None
        stmt = select(ObservationRef)
        if observation_ref_id is not None:
            stmt = stmt.where(ObservationRef.id == observation_ref_id)
        if observation_key:
            stmt = stmt.where(ObservationRef.observation_key == observation_key)
        row = self.db.scalars(stmt.limit(1)).first()
        return _observation_to_view(row) if row else None

    def list_observation_refs(
        self,
        *,
        source_id: int | None = None,
        chunk_id: int | None = None,
        provenance_kind: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[ObservationRefView], int]:
        stmt = select(ObservationRef)
        if source_id is not None:
            stmt = stmt.where(ObservationRef.source_id == source_id)
        if chunk_id is not None:
            stmt = stmt.where(ObservationRef.chunk_id == chunk_id)
        if provenance_kind:
            stmt = stmt.where(ObservationRef.provenance_kind == provenance_kind)

        total = self._count(stmt)
        rows = self.db.scalars(
            stmt.order_by(ObservationRef.id.asc())
            .offset(max(0, offset))
            .limit(_clamp_limit(limit))
        ).all()
        return [_observation_to_view(row) for row in rows], total

    def get_claim(self, claim_id: int) -> ClaimView | None:
        row = self.db.get(EpistemicClaim, claim_id)
        return _claim_to_view(row) if row else None

    def list_claims(
        self,
        *,
        epistemic_status: str | None = None,
        attributed_to: str | None = None,
        active_only: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[ClaimView], int]:
        stmt = select(EpistemicClaim)
        if epistemic_status:
            stmt = stmt.where(EpistemicClaim.epistemic_status == epistemic_status)
        if attributed_to:
            stmt = stmt.where(EpistemicClaim.attributed_to == attributed_to)
        if active_only:
            stmt = stmt.where(EpistemicClaim.superseded_by_id.is_(None))

        total = self._count(stmt)
        rows = self.db.scalars(
            stmt.order_by(EpistemicClaim.id.asc())
            .offset(max(0, offset))
            .limit(_clamp_limit(limit))
        ).all()
        return [_claim_to_view(row) for row in rows], total

    def list_claims_by_source_id(
        self,
        source_id: int,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[ClaimView], int]:
        """Claims linked to observations from the given source (via evidence_link)."""
        stmt = (
            select(EpistemicClaim)
            .join(EvidenceLink, EvidenceLink.claim_id == EpistemicClaim.id)
            .join(ObservationRef, ObservationRef.id == EvidenceLink.observation_ref_id)
            .where(ObservationRef.source_id == source_id)
            .distinct()
        )
        total = self._count(stmt)
        rows = self.db.scalars(
            stmt.order_by(EpistemicClaim.id.asc())
            .offset(max(0, offset))
            .limit(_clamp_limit(limit))
        ).all()
        return [_claim_to_view(row) for row in rows], total

    def list_evidence_links_for_claim(
        self,
        claim_id: int,
        *,
        role: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[EvidenceLinkView], int]:
        stmt = select(EvidenceLink).where(EvidenceLink.claim_id == claim_id)
        if role:
            stmt = stmt.where(EvidenceLink.role == role)

        total = self._count(stmt)
        rows = self.db.scalars(
            stmt.order_by(EvidenceLink.id.asc())
            .offset(max(0, offset))
            .limit(_clamp_limit(limit))
        ).all()
        return [_evidence_to_view(row) for row in rows], total

    def get_summary(self) -> EpistemicMemorySummary:
        observation_ref_count = int(
            self.db.scalar(select(func.count()).select_from(ObservationRef)) or 0
        )
        claim_count = int(
            self.db.scalar(select(func.count()).select_from(EpistemicClaim)) or 0
        )
        active_claim_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(EpistemicClaim)
                .where(EpistemicClaim.superseded_by_id.is_(None))
            )
            or 0
        )
        evidence_link_count = int(
            self.db.scalar(select(func.count()).select_from(EvidenceLink)) or 0
        )
        return EpistemicMemorySummary(
            observation_ref_count=observation_ref_count,
            claim_count=claim_count,
            active_claim_count=active_claim_count,
            evidence_link_count=evidence_link_count,
        )

    def _count(self, stmt) -> int:
        return int(
            self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        )


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(limit, MAX_LIMIT))


def _observation_to_view(row: ObservationRef) -> ObservationRefView:
    return ObservationRefView(
        id=row.id,
        source_id=row.source_id,
        chunk_id=row.chunk_id,
        observation_key=row.observation_key,
        content_hash=row.content_hash,
        excerpt=row.excerpt,
        observed_at=row.observed_at,
        provenance_kind=row.provenance_kind,
        provenance_ref=row.provenance_ref,
        extraction_version=row.extraction_version,
        created_at=row.created_at,
    )


def _claim_to_view(row: EpistemicClaim) -> ClaimView:
    return ClaimView(
        id=row.id,
        proposition=row.proposition,
        scope_json=row.scope_json,
        epistemic_status=row.epistemic_status,
        attributed_to=row.attributed_to,
        provenance_kind=row.provenance_kind,
        provenance_ref=row.provenance_ref,
        confidence=row.confidence,
        superseded_by_id=row.superseded_by_id,
        revision_of_id=row.revision_of_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _evidence_to_view(row: EvidenceLink) -> EvidenceLinkView:
    return EvidenceLinkView(
        id=row.id,
        claim_id=row.claim_id,
        observation_ref_id=row.observation_ref_id,
        role=row.role,
        provenance_kind=row.provenance_kind,
        provenance_ref=row.provenance_ref,
        link_confidence=row.link_confidence,
        created_at=row.created_at,
    )
