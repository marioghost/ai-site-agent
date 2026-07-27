"""RFC-100 Step 034 — TensionSurfacingService tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.services.epistemic_memory import EpistemicMemoryService
from app.services.tension_surfacing import (
    TENSION_CONFLICT,
    TENSION_SUPPORT_DEFICIT,
    TensionSurfacingService,
)

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
NOW = datetime.now(timezone.utc)


def _token() -> str:
    return uuid.uuid4().hex[:12]


def _session():
    from tests._dbutil import make_engine

    engine = make_engine(fresh=False)
    session = sessionmaker(bind=engine)()
    return session, EpistemicMemoryService(session), engine


def _seed_support_deficit(session):
    token = _token()
    claim = EpistemicClaim(
        proposition=f"Unsubstantiated claim without evidence {token}",
        attributed_to="fixture",
        provenance_kind="test",
        epistemic_status="proposal",
    )
    session.add(claim)
    session.commit()
    session.refresh(claim)
    return claim


def _seed_supported_claim(session):
    from tests._dbutil import ensure_source_ids

    token = _token()
    ensure_source_ids(session, 901)
    obs = ObservationRef(
        observation_key=f"obs:tension:supported:{token}",
        content_hash=f"hash-supported-{token}",
        source_id=901,
        observed_at=NOW,
        provenance_kind="test",
        excerpt="Supporting excerpt",
    )
    claim = EpistemicClaim(
        proposition=f"Claim with support {token}",
        attributed_to="fixture",
        provenance_kind="test",
    )
    session.add_all([obs, claim])
    session.flush()
    link = EvidenceLink(
        claim_id=claim.id,
        observation_ref_id=obs.id,
        role="support",
        provenance_kind="test",
    )
    session.add(link)
    session.commit()
    for row in (obs, claim, link):
        session.refresh(row)
    return claim, obs, link


def _seed_cross_claim_conflict(session):
    from tests._dbutil import ensure_source_ids

    token = _token()
    ensure_source_ids(session, 902)
    obs = ObservationRef(
        observation_key=f"obs:tension:cross:{token}",
        content_hash=f"hash-cross-{token}",
        source_id=902,
        observed_at=NOW,
        provenance_kind="test",
    )
    claim_a = EpistemicClaim(
        proposition=f"Supported proposition A {token}",
        attributed_to="fixture",
        provenance_kind="test",
    )
    claim_b = EpistemicClaim(
        proposition=f"Conflicting proposition B {token}",
        attributed_to="fixture",
        provenance_kind="test",
    )
    session.add_all([obs, claim_a, claim_b])
    session.flush()
    support = EvidenceLink(
        claim_id=claim_a.id,
        observation_ref_id=obs.id,
        role="support",
        provenance_kind="test",
    )
    conflict = EvidenceLink(
        claim_id=claim_b.id,
        observation_ref_id=obs.id,
        role="conflict",
        provenance_kind="test",
    )
    session.add_all([support, conflict])
    session.commit()
    return claim_a, claim_b, obs, support, conflict


def _seed_superseded_claim(session):
    token = _token()
    active = EpistemicClaim(
        proposition=f"Active successor {token}",
        attributed_to="fixture",
        provenance_kind="test",
    )
    session.add(active)
    session.flush()
    old = EpistemicClaim(
        proposition=f"Superseded claim without evidence {token}",
        attributed_to="fixture",
        provenance_kind="test",
        superseded_by_id=active.id,
    )
    session.add(old)
    session.commit()
    session.refresh(old)
    return old


@pytest.mark.unit
def test_support_deficit_detected_for_claim_without_support():
    session, memory, engine = _session()
    try:
        claim = _seed_support_deficit(session)
        tensions = TensionSurfacingService(memory).surface_tensions()
        deficits = [t for t in tensions if t.tension_type == TENSION_SUPPORT_DEFICIT]
        assert any(claim.id in t.claim_ids for t in deficits)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_no_support_deficit_when_support_link_exists():
    session, memory, engine = _session()
    try:
        claim, _, _ = _seed_supported_claim(session)
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
def test_cross_claim_conflict_explicit_via_evidence_roles():
    session, memory, engine = _session()
    try:
        claim_a, claim_b, obs, _, _ = _seed_cross_claim_conflict(session)
        tensions = TensionSurfacingService(memory).surface_tensions()
        conflicts = [t for t in tensions if t.tension_type == TENSION_CONFLICT]
        cross = [
            t
            for t in conflicts
            if set(t.claim_ids) == {claim_a.id, claim_b.id}
            and obs.id in t.observation_ref_ids
        ]
        assert len(cross) == 1
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_superseded_claims_ignored():
    session, memory, engine = _session()
    try:
        old = _seed_superseded_claim(session)
        tensions = TensionSurfacingService(memory).surface_tensions()
        assert all(old.id not in t.claim_ids for t in tensions)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_service_reads_via_epistemic_memory_only(monkeypatch):
    calls: list[str] = []

    class _TrackingMemory:
        def list_claims(self, **kwargs):
            calls.append("list_claims")
            return [], 0

    TensionSurfacingService(_TrackingMemory()).surface_tensions()
    assert calls == ["list_claims"]


@pytest.mark.unit
def test_tension_surfacing_has_no_db_writes():
    service_path = APP_ROOT / "services" / "tension_surfacing" / "tension_surfacing_service.py"
    source = service_path.read_text(encoding="utf-8")
    for token in ("session.add", "session.commit", "EpistemicClaim(", "ObservationRef("):
        assert token not in source
