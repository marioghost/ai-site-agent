"""RFC-100 Step 030 — shadow write tests."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.models.settings import Settings
from app.models.source import Source
from app.services.epistemic_memory import (
    EpistemicMemoryIntegrationService,
    EpistemicMemoryService,
)
from app.services.memory_version_service import MemoryVersionService
from app.services.source_intelligence_service import SourceIntelligenceService

INTEGRATION_PATH = (
    __import__("pathlib").Path(__file__).resolve().parents[1]
    / "app"
    / "services"
    / "epistemic_memory"
    / "memory_integration_service.py"
)


@pytest.fixture(scope="module", autouse=True)
def _alembic_at_head():
    from tests._dbutil import ensure_alembic_head

    ensure_alembic_head()


def _session():
    from tests._dbutil import make_engine

    engine = make_engine(fresh=False)
    return sessionmaker(bind=engine)(), engine


def _counts(session):
    return (
        session.scalar(select(func.count()).select_from(ObservationRef)) or 0,
        session.scalar(select(func.count()).select_from(EpistemicClaim)) or 0,
        session.scalar(select(func.count()).select_from(EvidenceLink)) or 0,
    )


def _settings(*, shadow: bool) -> Settings:
    """In-memory settings — avoids requiring migration 0015 on shared dev DB."""
    return Settings(memory_shadow_write_enabled=shadow)


def _sample_source(session) -> Source:
    suffix = uuid.uuid4().hex[:8]
    source = Source(
        url=f"https://example.com/shadow-{suffix}/",
        source_type="page",
        status="indexed",
        title="About the organization",
        document_type="about_page",
        main_content_text="We provide services across multiple regions since 2010.",
        main_content_chars=1200,
        boilerplate_ratio=0.1,
        content_hash=f"shadow-test-hash-{suffix}",
    )
    session.add(source)
    session.flush()
    return source


def _profile_for(source: Source):
    profile = SourceIntelligenceService.build_profile(source)
    SourceIntelligenceService.apply_to_source(source, profile)
    return profile


def _cleanup_shadow_for_source(session, source: Source) -> None:
    """Remove epistemic rows created for a test source (shared DB safe)."""
    obs_ids = list(
        session.scalars(
            select(ObservationRef.id).where(ObservationRef.source_id == source.id)
        ).all()
    )
    if obs_ids:
        claim_ids = list(
            session.scalars(
                select(EvidenceLink.claim_id)
                .where(EvidenceLink.observation_ref_id.in_(obs_ids))
                .distinct()
            ).all()
        )
        session.execute(
            delete(EvidenceLink).where(EvidenceLink.observation_ref_id.in_(obs_ids))
        )
        session.execute(delete(ObservationRef).where(ObservationRef.id.in_(obs_ids)))
        for claim_id in claim_ids:
            remaining = session.scalar(
                select(func.count())
                .select_from(EvidenceLink)
                .where(EvidenceLink.claim_id == claim_id)
            )
            if not remaining:
                session.execute(delete(EpistemicClaim).where(EpistemicClaim.id == claim_id))
    session.delete(source)
    session.commit()


@pytest.mark.unit
def test_flag_off_zero_writes():
    session, engine = _session()
    try:
        settings = _settings(shadow=False)
        obs0, claim0, link0 = _counts(session)
        source = _sample_source(session)
        profile = _profile_for(source)
        result = EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
            source, profile
        )
        assert result is None
        obs1, claim1, link1 = _counts(session)
        assert (obs1, claim1, link1) == (obs0, claim0, link0)
        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_flag_on_writes_and_idempotent():
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session)
        profile = _profile_for(source)
        integration = EpistemicMemoryIntegrationService(session, settings)

        first = integration.shadow_write_after_si(source, profile)
        assert first is not None
        assert first.any_created is True
        session.commit()

        obs_after_first, claims_after_first, links_after_first = _counts(session)
        assert obs_after_first >= 1
        assert claims_after_first >= 1
        assert links_after_first >= 1

        memory_after_first = MemoryVersionService(session).get()

        second = integration.shadow_write_after_si(source, profile)
        assert second is not None
        assert second.observations_created == 0
        assert second.claims_created == 0
        assert second.evidence_links_created == 0
        assert second.any_created is False
        session.commit()

        obs_after_second, claims_after_second, links_after_second = _counts(session)
        assert (obs_after_second, claims_after_second, links_after_second) == (
            obs_after_first,
            claims_after_first,
            links_after_first,
        )
        assert MemoryVersionService(session).get() == memory_after_first

        obs_keys = session.scalars(select(ObservationRef.observation_key)).all()
        assert len(obs_keys) == len(set(obs_keys))
        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_bump_only_on_real_changes(monkeypatch):
    session, engine = _session()
    bump_calls: list[int] = []

    class _TrackingMemoryVersionService:
        def __init__(self, db) -> None:
            pass

        def bump(self, *, commit: bool = True) -> int:
            bump_calls.append(1)
            assert commit is False
            return 99

    monkeypatch.setattr(
        "app.services.epistemic_memory.memory_integration_service.MemoryVersionService",
        _TrackingMemoryVersionService,
    )
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session)
        profile = _profile_for(source)
        integration = EpistemicMemoryIntegrationService(session, settings)

        integration.shadow_write_after_si(source, profile)
        assert len(bump_calls) == 1

        bump_calls.clear()
        integration.shadow_write_after_si(source, profile)
        assert bump_calls == []
        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_observation_uniqueness_stable_key():
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session)
        profile = _profile_for(source)
        EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
            source, profile
        )
        session.commit()
        obs_key = f"obs:source:{source.id}:si"
        keys = session.scalars(select(ObservationRef.observation_key)).all()
        assert obs_key in keys
        assert session.scalar(
            select(func.count())
            .select_from(ObservationRef)
            .where(ObservationRef.observation_key == obs_key)
        ) == 1
        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_memory_integration_does_not_write_orm_directly():
    source = INTEGRATION_PATH.read_text(encoding="utf-8")
    assert "ObservationRef(" not in source
    assert "EpistemicClaim(" not in source
    assert "EvidenceLink(" not in source
    assert "session.add" not in source


@pytest.mark.unit
def test_claim_extraction_still_has_no_db_writes():
    mapper_path = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "epistemic_memory"
        / "claim_extraction_from_si.py"
    )
    source = mapper_path.read_text(encoding="utf-8")
    for token in ("session.add", "ObservationRef(", "EpistemicClaim(", "EvidenceLink("):
        assert token not in source
