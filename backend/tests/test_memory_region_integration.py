"""RFC-100 Step 046 — Memory region SQL source-isolation integration tests.

Uses disposable POSTGRES_TEST_URL only. Rolls back all writes; never touches ai_site_agent.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.models.source import Source
from app.services.epistemic_memory.memory_region_reader import MemoryRegionReader
from app.services.epistemic_memory.memory_region_types import MemoryRegionRequest
from app.services.epistemic_memory.provenance_scope import ProvenanceScope
from tests._dbutil import make_engine, new_test_run_id


@pytest.fixture(scope="module", autouse=True)
def _alembic_at_head():
    from tests._dbutil import ensure_alembic_head

    ensure_alembic_head()


@pytest.fixture()
def region_session():
    engine = make_engine(fresh=False)
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
    engine.dispose()


def _fixture_source(session, *, run_id: str, token: str) -> Source:
    source = Source(
        url=f"https://fixture.example/run-{run_id}/region-{token}/",
        source_type="page",
        title=f"Region fixture {token} [test_run={run_id}]",
    )
    session.add(source)
    session.flush()
    return source


def _observation(
    session,
    *,
    source_id: int,
    key_suffix: str,
    run_id: str,
) -> ObservationRef:
    obs = ObservationRef(
        source_id=source_id,
        observation_key=f"obs:region:{run_id}:{key_suffix}",
        content_hash=f"hash-{run_id}-{key_suffix}",
        excerpt=f"excerpt {key_suffix}",
        observed_at=datetime.now(timezone.utc),
        provenance_kind="source_intelligence",
    )
    session.add(obs)
    session.flush()
    return obs


def _claim_with_link(
    session,
    *,
    proposition: str,
    source: Source,
    obs: ObservationRef,
    role: str = "support",
    scope_json: str | None = None,
    provenance_kind: str = "source_intelligence",
    attributed_to: str = "source_intelligence",
) -> EpistemicClaim:
    claim = EpistemicClaim(
        proposition=proposition,
        scope_json=scope_json,
        epistemic_status="proposal",
        attributed_to=attributed_to,
        provenance_kind=provenance_kind,
    )
    session.add(claim)
    session.flush()
    session.add(
        EvidenceLink(
            claim_id=claim.id,
            observation_ref_id=obs.id,
            role=role,
            provenance_kind=provenance_kind,
        )
    )
    session.flush()
    return claim


@pytest.mark.unit
def test_source_a_claim_returned_for_source_a(region_session):
    run_id = new_test_run_id()
    src_a = _fixture_source(region_session, run_id=run_id, token="a")
    obs = _observation(region_session, source_id=src_a.id, key_suffix="a1", run_id=run_id)
    claim = _claim_with_link(
        region_session, proposition="Claim A", source=src_a, obs=obs
    )

    view = MemoryRegionReader(region_session).read_region(
        MemoryRegionRequest(source_id=src_a.id)
    )
    assert view.total_matched == 1
    assert view.matched_claims[0].claim_id == claim.id


@pytest.mark.unit
def test_source_b_claim_excluded_from_source_a(region_session):
    run_id = new_test_run_id()
    src_a = _fixture_source(region_session, run_id=run_id, token="a")
    src_b = _fixture_source(region_session, run_id=run_id, token="b")
    obs_b = _observation(region_session, source_id=src_b.id, key_suffix="b1", run_id=run_id)
    _claim_with_link(region_session, proposition="Claim B", source=src_b, obs=obs_b)

    view = MemoryRegionReader(region_session).read_region(
        MemoryRegionRequest(source_id=src_a.id)
    )
    assert view.total_matched == 0


@pytest.mark.unit
def test_multiple_source_ids_return_union(region_session):
    run_id = new_test_run_id()
    src_a = _fixture_source(region_session, run_id=run_id, token="a")
    src_b = _fixture_source(region_session, run_id=run_id, token="b")
    obs_a = _observation(region_session, source_id=src_a.id, key_suffix="a2", run_id=run_id)
    obs_b = _observation(region_session, source_id=src_b.id, key_suffix="b2", run_id=run_id)
    claim_a = _claim_with_link(
        region_session, proposition="A", source=src_a, obs=obs_a
    )
    claim_b = _claim_with_link(
        region_session, proposition="B", source=src_b, obs=obs_b
    )

    view = MemoryRegionReader(region_session).read_region(
        MemoryRegionRequest(source_ids=(src_a.id, src_b.id))
    )
    ids = {row.claim_id for row in view.matched_claims}
    assert ids == {claim_a.id, claim_b.id}


@pytest.mark.unit
def test_misleading_scope_json_source_id_does_not_bypass_isolation(region_session):
    run_id = new_test_run_id()
    src_a = _fixture_source(region_session, run_id=run_id, token="a")
    src_b = _fixture_source(region_session, run_id=run_id, token="b")
    obs_b = _observation(region_session, source_id=src_b.id, key_suffix="b3", run_id=run_id)
    scope = json.dumps({"source_id": src_a.id, "page_role": "about"})
    _claim_with_link(
        region_session,
        proposition="Misleading scope",
        source=src_b,
        obs=obs_b,
        scope_json=scope,
    )

    view = MemoryRegionReader(region_session).read_region(
        MemoryRegionRequest(source_id=src_a.id)
    )
    assert view.total_matched == 0


@pytest.mark.unit
def test_claim_without_evidence_link_not_returned(region_session):
    run_id = new_test_run_id()
    src_a = _fixture_source(region_session, run_id=run_id, token="a")
    orphan = EpistemicClaim(
        proposition="Orphan claim",
        epistemic_status="proposal",
        attributed_to="source_intelligence",
        provenance_kind="source_intelligence",
    )
    region_session.add(orphan)
    region_session.flush()

    obs = _observation(region_session, source_id=src_a.id, key_suffix="a3", run_id=run_id)
    linked = _claim_with_link(
        region_session, proposition="Linked", source=src_a, obs=obs
    )

    view = MemoryRegionReader(region_session).read_region(
        MemoryRegionRequest(source_id=src_a.id)
    )
    assert view.total_matched == 1
    assert view.matched_claims[0].claim_id == linked.id
    assert orphan.id not in {row.claim_id for row in view.matched_claims}


@pytest.mark.unit
def test_conflict_only_evidence_honest(region_session):
    run_id = new_test_run_id()
    src = _fixture_source(region_session, run_id=run_id, token="c")
    obs = _observation(region_session, source_id=src.id, key_suffix="c1", run_id=run_id)
    _claim_with_link(
        region_session,
        proposition="Conflict only",
        source=src,
        obs=obs,
        role="conflict",
    )

    row = MemoryRegionReader(region_session).read_region(
        MemoryRegionRequest(source_id=src.id)
    ).matched_claims[0]
    assert row.has_support is False
    assert row.has_conflict is True
    assert row.evidence_loaded is True


@pytest.mark.unit
def test_evidence_filtered_to_allowed_source_ids(region_session):
    run_id = new_test_run_id()
    src_a = _fixture_source(region_session, run_id=run_id, token="a")
    src_b = _fixture_source(region_session, run_id=run_id, token="b")
    obs_a = _observation(region_session, source_id=src_a.id, key_suffix="ea", run_id=run_id)
    obs_b = _observation(region_session, source_id=src_b.id, key_suffix="eb", run_id=run_id)

    claim = EpistemicClaim(
        proposition="Dual-linked",
        epistemic_status="proposal",
        attributed_to="source_intelligence",
        provenance_kind="source_intelligence",
    )
    region_session.add(claim)
    region_session.flush()
    region_session.add(
        EvidenceLink(
            claim_id=claim.id,
            observation_ref_id=obs_a.id,
            role="support",
            provenance_kind="source_intelligence",
        )
    )
    region_session.add(
        EvidenceLink(
            claim_id=claim.id,
            observation_ref_id=obs_b.id,
            role="support",
            provenance_kind="source_intelligence",
        )
    )
    region_session.flush()

    row = MemoryRegionReader(region_session).read_region(
        MemoryRegionRequest(source_id=src_a.id)
    ).matched_claims[0]
    source_ids = {ref.source_id for ref in row.evidence}
    assert source_ids == {src_a.id}


@pytest.mark.unit
def test_test_provenance_excluded_by_default_integration(region_session):
    run_id = new_test_run_id()
    src = _fixture_source(region_session, run_id=run_id, token="t")
    obs = _observation(region_session, source_id=src.id, key_suffix="t1", run_id=run_id)
    _claim_with_link(
        region_session,
        proposition="Fixture claim",
        source=src,
        obs=obs,
        provenance_kind="test",
        attributed_to="fixture",
    )

    view = MemoryRegionReader(region_session).read_region(
        MemoryRegionRequest(source_id=src.id, provenance_scope=ProvenanceScope.REAL)
    )
    assert view.total_matched == 0
    assert view.provenance_excluded_count == 1
