"""Tension cognitive acceptance suite — coverage gaps (see docs/TENSION_ACCEPTANCE.md).

Scenarios already covered in test_tension_surfacing_service.py are not duplicated.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.services.epistemic_memory import EpistemicMemoryService
from app.services.tension_surfacing import (
    TENSION_CONFLICT,
    TENSION_SUPPORT_DEFICIT,
    TensionSurfacingService,
)

NOW = datetime.now(timezone.utc)


def _token() -> str:
    return uuid.uuid4().hex[:12]


def _session():
    from tests._dbutil import make_engine

    engine = make_engine(fresh=False)
    session = sessionmaker(bind=engine)()
    return session, EpistemicMemoryService(session), engine


def _add_obs(session, *, token: str, source_id: int) -> ObservationRef:
    from tests._dbutil import ensure_source_ids

    ensure_source_ids(session, source_id)
    obs = ObservationRef(
        observation_key=f"obs:acc:{token}:{source_id}:{_token()}",
        content_hash=f"hash-acc-{token}-{source_id}-{_token()}",
        source_id=source_id,
        observed_at=NOW,
        provenance_kind="test",
    )
    session.add(obs)
    session.flush()
    return obs


@pytest.mark.unit
def test_acc_empty_memory():
    """T-01 — empty Epistemic Memory yields no hypotheses."""

    class EmptyMemory:
        def list_claims(self, **kwargs):
            return [], 0

    assert TensionSurfacingService(EmptyMemory()).surface_tensions() == []


@pytest.mark.unit
def test_acc_multiple_supporting_observations():
    """T-06 — two support links clear support_deficit."""
    session, memory, engine = _session()
    try:
        token = _token()
        claim = EpistemicClaim(
            proposition=f"Multi-support claim {token}",
            attributed_to="fixture",
            provenance_kind="test",
        )
        session.add(claim)
        session.flush()
        obs_a = _add_obs(session, token=token, source_id=910)
        obs_b = _add_obs(session, token=token, source_id=911)
        session.add_all(
            [
                EvidenceLink(
                    claim_id=claim.id,
                    observation_ref_id=obs_a.id,
                    role="support",
                    provenance_kind="test",
                ),
                EvidenceLink(
                    claim_id=claim.id,
                    observation_ref_id=obs_b.id,
                    role="support",
                    provenance_kind="test",
                ),
            ]
        )
        session.commit()

        tensions = TensionSurfacingService(memory).surface_tensions()
        deficits = [
            t
            for t in tensions
            if t.tension_type == TENSION_SUPPORT_DEFICIT and claim.id in t.claim_ids
        ]
        assert deficits == []
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_acc_mixed_support_and_conflict_same_claim():
    """T-07 — support clears deficit; conflict role still surfaces conflict."""
    session, memory, engine = _session()
    try:
        token = _token()
        claim = EpistemicClaim(
            proposition=f"Mixed claim {token}",
            attributed_to="fixture",
            provenance_kind="test",
        )
        session.add(claim)
        session.flush()
        obs_support = _add_obs(session, token=token, source_id=920)
        obs_conflict = _add_obs(session, token=token, source_id=921)
        session.add_all(
            [
                EvidenceLink(
                    claim_id=claim.id,
                    observation_ref_id=obs_support.id,
                    role="support",
                    provenance_kind="test",
                ),
                EvidenceLink(
                    claim_id=claim.id,
                    observation_ref_id=obs_conflict.id,
                    role="conflict",
                    provenance_kind="test",
                ),
            ]
        )
        session.commit()

        tensions = TensionSurfacingService(memory).surface_tensions()
        deficits = [
            t
            for t in tensions
            if t.tension_type == TENSION_SUPPORT_DEFICIT and claim.id in t.claim_ids
        ]
        conflicts = [
            t
            for t in tensions
            if t.tension_type == TENSION_CONFLICT and t.claim_ids == (claim.id,)
        ]
        assert deficits == []
        assert len(conflicts) == 1
        assert obs_conflict.id in conflicts[0].observation_ref_ids
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_acc_duplicated_conflict_evidence_deduped():
    """T-08 — duplicate conflict links for same claim+obs → one hypothesis."""
    session, memory, engine = _session()
    try:
        token = _token()
        claim = EpistemicClaim(
            proposition=f"Dup conflict claim {token}",
            attributed_to="fixture",
            provenance_kind="test",
        )
        session.add(claim)
        session.flush()
        obs = _add_obs(session, token=token, source_id=930)
        session.add_all(
            [
                EvidenceLink(
                    claim_id=claim.id,
                    observation_ref_id=obs.id,
                    role="conflict",
                    provenance_kind="test",
                ),
                EvidenceLink(
                    claim_id=claim.id,
                    observation_ref_id=obs.id,
                    role="conflict",
                    provenance_kind="test",
                ),
            ]
        )
        session.commit()

        tensions = TensionSurfacingService(memory).surface_tensions()
        conflicts = [
            t
            for t in tensions
            if t.tension_type == TENSION_CONFLICT
            and t.claim_ids == (claim.id,)
            and obs.id in t.observation_ref_ids
        ]
        assert len(conflicts) == 1
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_acc_intra_claim_conflict_without_support():
    """T-09 — conflict without support yields both deficit and conflict."""
    session, memory, engine = _session()
    try:
        token = _token()
        claim = EpistemicClaim(
            proposition=f"Conflict-only claim {token}",
            attributed_to="fixture",
            provenance_kind="test",
        )
        session.add(claim)
        session.flush()
        obs = _add_obs(session, token=token, source_id=940)
        session.add(
            EvidenceLink(
                claim_id=claim.id,
                observation_ref_id=obs.id,
                role="conflict",
                provenance_kind="test",
            )
        )
        session.commit()

        tensions = TensionSurfacingService(memory).surface_tensions()
        deficits = [
            t
            for t in tensions
            if t.tension_type == TENSION_SUPPORT_DEFICIT and claim.id in t.claim_ids
        ]
        conflicts = [
            t
            for t in tensions
            if t.tension_type == TENSION_CONFLICT and t.claim_ids == (claim.id,)
        ]
        assert len(deficits) == 1
        assert len(conflicts) == 1
    finally:
        session.rollback()
        session.close()
        engine.dispose()
