"""RFC-100 Step 031 — shadow claim integrate memory_version bump contract."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.models.settings import Settings
from app.models.source import Source
from app.repositories.settings_repository import SettingsRepository
from app.services.epistemic_memory import EpistemicMemoryIntegrationService
from app.services.epistemic_memory.epistemic_memory_service import EpistemicMemoryService
from app.services.epistemic_memory.epistemic_memory_write_service import (
    EpistemicMemoryWriteService,
)
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.memory_version_service import MemoryVersionService
from app.services.source_intelligence_service import SourceIntelligenceService, SourceProfile

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
MEMORY_BUMP_CALL_ALLOWLIST = frozenset(
    {
        "services/memory_version_service.py",
        "api/settings.py",
        "services/epistemic_memory/memory_integration_service.py",
    }
)


@pytest.fixture(scope="module", autouse=True)
def _alembic_at_head():
    from tests._dbutil import ensure_alembic_head

    ensure_alembic_head()


def _session():
    from tests._dbutil import make_engine

    engine = make_engine(fresh=False)
    return sessionmaker(bind=engine)(), engine


def _settings(*, shadow: bool) -> Settings:
    return Settings(memory_shadow_write_enabled=shadow)


def _sample_source(session) -> Source:
    suffix = uuid.uuid4().hex[:8]
    source = Source(
        url=f"https://example.com/bump-{suffix}/",
        source_type="page",
        status="indexed",
        title="About the organization",
        document_type="about_page",
        main_content_text="We provide services across multiple regions since 2010.",
        main_content_chars=1200,
        boilerplate_ratio=0.1,
        content_hash=f"bump-test-hash-{suffix}",
    )
    session.add(source)
    session.flush()
    return source


def _rich_profile(source: Source) -> SourceProfile:
    profile = SourceIntelligenceService.build_profile(source)
    SourceIntelligenceService.apply_to_source(source, profile)
    return profile


def _empty_profile(source: Source) -> SourceProfile:
    return SourceProfile(
        source_id=source.id,
        url=source.url,
        confidence=0.1,
        llm_summary="",
        semantic=None,
    )


def _pinned_memory_version(session) -> tuple[int, int]:
    """Return (settings_id, memory_version) for the canonical settings row."""
    row = SettingsRepository(session).get_or_create()
    return row.id, MemoryVersionService(session).get()


def _counts(session):
    return (
        session.scalar(select(func.count()).select_from(ObservationRef)) or 0,
        session.scalar(select(func.count()).select_from(EpistemicClaim)) or 0,
        session.scalar(select(func.count()).select_from(EvidenceLink)) or 0,
    )


def _cleanup_shadow_for_source(session, source: Source) -> None:
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
def test_successful_shadow_write_bumps_memory_version_once():
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session)
        profile = _rich_profile(source)
        settings_id, memory_before = _pinned_memory_version(session)

        EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
            source, profile
        )
        session.commit()

        pinned = session.get(Settings, settings_id)
        assert pinned is not None
        assert pinned.memory_version == memory_before + 1

        EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
            source, profile
        )
        session.commit()
        session.refresh(pinned)
        assert pinned.memory_version == memory_before + 1

        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_flag_off_does_not_bump():
    session, engine = _session()
    try:
        settings = _settings(shadow=False)
        source = _sample_source(session)
        profile = _rich_profile(source)
        settings_id, memory_before = _pinned_memory_version(session)

        result = EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
            source, profile
        )
        assert result is None
        session.commit()
        pinned = session.get(Settings, settings_id)
        assert pinned is not None
        assert pinned.memory_version == memory_before

        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_empty_proposals_do_not_bump():
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session)
        profile = _empty_profile(source)
        settings_id, memory_before = _pinned_memory_version(session)

        result = EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
            source, profile
        )
        assert result is not None
        assert result.any_created is False
        session.commit()
        pinned = session.get(Settings, settings_id)
        assert pinned is not None
        assert pinned.memory_version == memory_before

        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_failed_persist_does_not_bump(monkeypatch):
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session)
        profile = _rich_profile(source)
        settings_id, memory_before = _pinned_memory_version(session)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("persist failed")

        monkeypatch.setattr(
            EpistemicMemoryService,
            "persist_claim_proposals",
            _boom,
        )

        with pytest.raises(RuntimeError, match="persist failed"):
            EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
                source, profile
            )
        session.rollback()
        pinned = session.get(Settings, settings_id)
        assert pinned is not None
        assert pinned.memory_version == memory_before
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_partial_persist_failure_does_not_bump(monkeypatch):
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session)
        profile = _rich_profile(source)
        settings_id, memory_before = _pinned_memory_version(session)
        original = EpistemicMemoryWriteService._get_or_create_claim
        calls = {"n": 0}

        def _flaky(self, proposal):
            calls["n"] += 1
            if calls["n"] > 1:
                raise RuntimeError("mid-persist")
            return original(self, proposal)

        monkeypatch.setattr(
            EpistemicMemoryWriteService,
            "_get_or_create_claim",
            _flaky,
        )

        with pytest.raises(RuntimeError, match="mid-persist"):
            EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
                source, profile
            )
        session.rollback()
        pinned = session.get(Settings, settings_id)
        assert pinned is not None
        assert pinned.memory_version == memory_before
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_rollback_discards_bump_and_epistemic_rows():
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session)
        profile = _rich_profile(source)
        settings_id, memory_before = _pinned_memory_version(session)
        obs0, claim0, link0 = _counts(session)

        EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
            source, profile
        )
        session.rollback()

        pinned = session.get(Settings, settings_id)
        assert pinned is not None
        assert pinned.memory_version == memory_before
        obs1, claim1, link1 = _counts(session)
        assert (obs1, claim1, link1) == (obs0, claim0, link0)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_sequential_sources_bump_monotonically():
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        settings_id, memory_before = _pinned_memory_version(session)
        sources = [_sample_source(session) for _ in range(2)]

        for source in sources:
            profile = _rich_profile(source)
            EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
                source, profile
            )
        session.commit()

        pinned = session.get(Settings, settings_id)
        assert pinned is not None
        assert pinned.memory_version >= memory_before + 2

        for source in sources:
            _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_shadow_write_does_not_change_knowledge_version():
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session)
        profile = _rich_profile(source)
        knowledge_before = KnowledgeVersionService(session).get()

        EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
            source, profile
        )
        session.commit()

        assert KnowledgeVersionService(session).get() == knowledge_before

        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_bump_commit_false_participates_in_caller_transaction():
    from tests._dbutil import make_engine

    engine = make_engine(fresh=False)
    session = sessionmaker(bind=engine)()
    try:
        svc = MemoryVersionService(session)
        row = SettingsRepository(session).get_or_create()
        settings_id = row.id
        memory_before = row.memory_version or 1

        assert svc.bump(commit=False) == memory_before + 1
        session.rollback()
        pinned = session.get(Settings, settings_id)
        assert pinned is not None
        assert pinned.memory_version == memory_before

        assert svc.bump(commit=True) == memory_before + 1
        session.commit()
        session.refresh(pinned)
        assert pinned.memory_version == memory_before + 1

        pinned.memory_version = memory_before
        session.commit()
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_only_allowlisted_modules_call_memory_version_bump():
    violations: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        rel = path.relative_to(APP_ROOT).as_posix()
        if rel.startswith("migrations/"):
            continue
        if rel in MEMORY_BUMP_CALL_ALLOWLIST:
            continue
        source = path.read_text(encoding="utf-8")
        if "MemoryVersionService" in source and ".bump(" in source:
            violations.append(rel)
    assert violations == [], f"unexpected MemoryVersionService.bump() callers: {violations}"


@pytest.mark.unit
def test_integration_uses_deferred_commit_bump():
    source = (
        APP_ROOT / "services" / "epistemic_memory" / "memory_integration_service.py"
    ).read_text(encoding="utf-8")
    assert "bump(commit=False)" in source
    assert "MemoryVersionService(self.db).bump(commit=False)" in source
