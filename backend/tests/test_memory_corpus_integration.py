"""PostgreSQL integration tests for Memory deployment corpus scope."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.models.settings import Settings
from app.models.source import Source
from app.services.epistemic_memory.memory_region_reader import MemoryRegionReader
from app.services.epistemic_memory.memory_region_types import (
    LIMIT_CORPUS_SCOPE_UNCONFIGURED,
    MemoryCorpusScope,
    MemoryIsolationScope,
    MemoryRegionRequest,
)
from app.services.epistemic_memory.provenance_scope import ProvenanceScope
from tests._dbutil import make_engine, new_test_run_id


@pytest.fixture(scope="module", autouse=True)
def _alembic_at_head():
    from tests._dbutil import ensure_alembic_head

    ensure_alembic_head()


@pytest.fixture()
def corpus_session():
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


def _source(session, *, run_id: str, host: str, token: str) -> Source:
    source = Source(
        url=f"https://{host}/corpus-{token}/",
        source_type="page",
        title=f"Corpus {token} [test_run={run_id}]",
    )
    session.add(source)
    session.flush()
    return source


def _obs(session, *, source_id: int, key: str, run_id: str) -> ObservationRef:
    obs = ObservationRef(
        source_id=source_id,
        observation_key=f"obs:corpus:{run_id}:{key}",
        content_hash=f"hash-{run_id}-{key}",
        excerpt="ex",
        observed_at=datetime.now(timezone.utc),
        provenance_kind="source_intelligence",
    )
    session.add(obs)
    session.flush()
    return obs


def _claim_link(
    session,
    *,
    obs: ObservationRef,
    proposition: str,
    scope_json: str | None = None,
) -> EpistemicClaim:
    claim = EpistemicClaim(
        proposition=proposition,
        scope_json=scope_json,
        epistemic_status="proposal",
        attributed_to="source_intelligence",
        provenance_kind="source_intelligence",
    )
    session.add(claim)
    session.flush()
    session.add(
        EvidenceLink(
            claim_id=claim.id,
            observation_ref_id=obs.id,
            role="support",
            provenance_kind="source_intelligence",
        )
    )
    session.flush()
    return claim


def _configure_settings(session, *, allowed_domains: list[str]) -> Settings:
    settings = session.query(Settings).order_by(Settings.id).first()
    if settings is None:
        settings = Settings()
        session.add(settings)
    settings.allowed_domains_json = json.dumps(allowed_domains)
    settings.site_url = None
    session.flush()
    return settings


@pytest.mark.unit
def test_deployment_corpus_returns_only_allowed_host(corpus_session):
    run_id = new_test_run_id()
    _configure_settings(corpus_session, allowed_domains=["allowed.example"])
    host_a = _source(corpus_session, run_id=run_id, host="allowed.example", token="a")
    host_b = _source(corpus_session, run_id=run_id, host="foreign.example", token="b")
    obs_a = _obs(corpus_session, source_id=host_a.id, key="a", run_id=run_id)
    obs_b = _obs(corpus_session, source_id=host_b.id, key="b", run_id=run_id)
    claim_a = _claim_link(corpus_session, obs=obs_a, proposition="Allowed claim")
    _claim_link(
        corpus_session,
        obs=obs_b,
        proposition="Foreign claim",
        scope_json=json.dumps({"source_id": host_a.id}),
    )

    view = MemoryRegionReader(corpus_session).read_region(
        MemoryRegionRequest(
            isolation=MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT),
        )
    )
    assert view.total_matched == 1
    assert view.matched_claims[0].claim_id == claim_a.id
    assert host_b.id not in view.corpus_anchor_source_ids or host_a.id in view.corpus_anchor_source_ids


@pytest.mark.unit
def test_explicit_source_scope_can_read_foreign_host(corpus_session):
    run_id = new_test_run_id()
    _configure_settings(corpus_session, allowed_domains=["allowed.example"])
    foreign = _source(corpus_session, run_id=run_id, host="foreign.example", token="f")
    obs = _obs(corpus_session, source_id=foreign.id, key="f", run_id=run_id)
    claim = _claim_link(corpus_session, obs=obs, proposition="Engineering scope")

    view = MemoryRegionReader(corpus_session).read_region(
        MemoryRegionRequest(source_id=foreign.id)
    )
    assert view.total_matched == 1
    assert view.matched_claims[0].claim_id == claim.id


@pytest.mark.unit
def test_unconfigured_corpus_returns_empty_not_global(corpus_session):
    run_id = new_test_run_id()
    settings = corpus_session.query(Settings).order_by(Settings.id).first()
    if settings is None:
        settings = Settings()
        corpus_session.add(settings)
    settings.allowed_domains_json = "[]"
    settings.site_url = None
    corpus_session.flush()

    foreign = _source(corpus_session, run_id=run_id, host="foreign.example", token="z")
    obs = _obs(corpus_session, source_id=foreign.id, key="z", run_id=run_id)
    _claim_link(corpus_session, obs=obs, proposition="Should not appear")

    view = MemoryRegionReader(corpus_session).read_region(
        MemoryRegionRequest(
            isolation=MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT),
        )
    )
    assert view.total_matched == 0
    assert LIMIT_CORPUS_SCOPE_UNCONFIGURED in view.corpus_limitations


@pytest.mark.unit
def test_test_provenance_excluded_under_deployment_corpus(corpus_session):
    run_id = new_test_run_id()
    _configure_settings(corpus_session, allowed_domains=["allowed.example"])
    src = _source(corpus_session, run_id=run_id, host="allowed.example", token="t")
    obs = _obs(corpus_session, source_id=src.id, key="t", run_id=run_id)
    claim = EpistemicClaim(
        proposition="Fixture",
        epistemic_status="proposal",
        attributed_to="fixture",
        provenance_kind="test",
    )
    corpus_session.add(claim)
    corpus_session.flush()
    corpus_session.add(
        EvidenceLink(
            claim_id=claim.id,
            observation_ref_id=obs.id,
            role="support",
            provenance_kind="test",
        )
    )
    corpus_session.flush()

    view = MemoryRegionReader(corpus_session).read_region(
        MemoryRegionRequest(
            isolation=MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT),
            provenance_scope=ProvenanceScope.REAL,
        )
    )
    assert view.total_matched == 0
    assert view.provenance_excluded_count == 1
