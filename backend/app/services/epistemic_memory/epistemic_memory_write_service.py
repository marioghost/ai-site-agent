"""Epistemic Memory write API (RFC-100 Step 030 — shadow persistence only)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.models.source import Source
from app.services.epistemic_memory.proposal_types import ClaimProposal, EvidenceProposal
from app.services.epistemic_memory.shadow_persist_result import ShadowPersistResult
from app.services.source_intelligence_constants import SOURCE_INTELLIGENCE_VERSION
from app.services.source_intelligence_service import SourceProfile


class EpistemicMemoryWriteService:
    """Idempotent shadow persistence for claim proposals."""

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
        if not proposals:
            return ShadowPersistResult()

        when = observed_at or datetime.now(timezone.utc)
        extraction_version = (
            profile.profile_version if profile else SOURCE_INTELLIGENCE_VERSION
        )
        observations_created = 0
        claims_created = 0
        evidence_links_created = 0
        observation_ids: dict[str, int] = {}

        for proposal in proposals:
            if not proposal.evidence:
                continue
            evidence = proposal.evidence[0]
            obs_key = _observation_key(evidence, proposal)
            obs_id = observation_ids.get(obs_key)
            if obs_id is None:
                observation, created = self._get_or_create_observation(
                    proposal=proposal,
                    evidence=evidence,
                    observation_key=obs_key,
                    observed_at=when,
                    extraction_version=extraction_version,
                )
                observation_ids[obs_key] = observation.id
                if created:
                    observations_created += 1
                obs_id = observation.id

            claim, claim_created = self._get_or_create_claim(proposal)
            if claim_created:
                claims_created += 1

            _, link_created = self._get_or_create_evidence_link(
                claim_id=claim.id,
                observation_ref_id=obs_id,
                proposal=proposal,
                evidence=evidence,
            )
            if link_created:
                evidence_links_created += 1

        return ShadowPersistResult(
            observations_created=observations_created,
            claims_created=claims_created,
            evidence_links_created=evidence_links_created,
        )

    def _get_or_create_observation(
        self,
        *,
        proposal: ClaimProposal,
        evidence: EvidenceProposal,
        observation_key: str,
        observed_at: datetime,
        extraction_version: str,
    ) -> tuple[ObservationRef, bool]:
        existing = self.db.scalars(
            select(ObservationRef).where(ObservationRef.observation_key == observation_key)
        ).first()
        if existing is not None:
            return existing, False

        row = ObservationRef(
            source_id=evidence.source_id or proposal.source_id,
            chunk_id=evidence.chunk_id,
            observation_key=observation_key,
            content_hash=evidence.content_hash or "unknown",
            excerpt=evidence.excerpt,
            observed_at=observed_at,
            provenance_kind=proposal.provenance_kind,
            provenance_ref=proposal.provenance_ref,
            extraction_version=extraction_version,
        )
        self.db.add(row)
        self.db.flush()
        return row, True

    def _get_or_create_claim(self, proposal: ClaimProposal) -> tuple[EpistemicClaim, bool]:
        existing = self.db.scalars(
            select(EpistemicClaim).where(
                EpistemicClaim.proposition == proposal.proposition,
                EpistemicClaim.provenance_ref == proposal.provenance_ref,
                EpistemicClaim.attributed_to == proposal.attributed_to,
            )
        ).first()
        if existing is not None:
            return existing, False

        row = EpistemicClaim(
            proposition=proposal.proposition,
            scope_json=proposal.scope_json,
            epistemic_status=proposal.epistemic_status,
            attributed_to=proposal.attributed_to,
            provenance_kind=proposal.provenance_kind,
            provenance_ref=proposal.provenance_ref,
            confidence=proposal.confidence,
        )
        self.db.add(row)
        self.db.flush()
        return row, True

    def _get_or_create_evidence_link(
        self,
        *,
        claim_id: int,
        observation_ref_id: int,
        proposal: ClaimProposal,
        evidence: EvidenceProposal,
    ) -> tuple[EvidenceLink, bool]:
        role = evidence.role or "support"
        existing = self.db.scalars(
            select(EvidenceLink).where(
                EvidenceLink.claim_id == claim_id,
                EvidenceLink.observation_ref_id == observation_ref_id,
                EvidenceLink.role == role,
            )
        ).first()
        if existing is not None:
            return existing, False

        row = EvidenceLink(
            claim_id=claim_id,
            observation_ref_id=observation_ref_id,
            role=role,
            provenance_kind=proposal.provenance_kind,
            provenance_ref=proposal.provenance_ref,
            link_confidence=proposal.confidence,
        )
        self.db.add(row)
        self.db.flush()
        return row, True


def _observation_key(evidence: EvidenceProposal, proposal: ClaimProposal) -> str:
    return evidence.observation_key_hint or f"obs:source:{proposal.source_id}:si"
