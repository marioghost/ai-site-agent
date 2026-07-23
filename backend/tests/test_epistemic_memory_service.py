"""RFC-100 Step 028 — EpistemicMemoryService read API tests."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.models.settings import Settings
from app.services.epistemic_memory import EpistemicMemoryService
from app.services.memory_version_service import MemoryVersionService

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
EPISTEMIC_MODEL_ALLOWLIST = frozenset(
    {
        "models/epistemic_memory.py",
        "models/__init__.py",
    }
)
EPISTEMIC_SERVICE_PREFIX = "services/epistemic_memory/"
EPISTEMIC_WRITE_ALLOWLIST = frozenset(
    {
        "services/epistemic_memory/epistemic_memory_service.py",
        "services/epistemic_memory/epistemic_memory_write_service.py",
    }
)
EPISTEMIC_WRITE_TOKENS = (
    "ObservationRef(",
    "EpistemicClaim(",
    "EvidenceLink(",
    "from app.models.epistemic_memory",
)


def _session_and_service():
    from tests._dbutil import make_engine

    engine = make_engine(fresh=False)
    session = sessionmaker(bind=engine)()
    return session, EpistemicMemoryService(session), engine


def _seed_sample(session) -> "SampleData":
    obs_a = ObservationRef(
        observation_key="obs:svc:a",
        content_hash="hash-a",
        source_id=101,
        observed_at=datetime.now(timezone.utc),
        provenance_kind="si_extraction",
        provenance_ref="si:101",
        excerpt="Excerpt A",
    )
    obs_b = ObservationRef(
        observation_key="obs:svc:b",
        content_hash="hash-b",
        source_id=102,
        observed_at=datetime.now(timezone.utc),
        provenance_kind="si_extraction",
        provenance_ref="si:102",
    )
    claim_a = EpistemicClaim(
        proposition="Claim A for source 101",
        attributed_to="claim_extraction",
        provenance_kind="si_extraction",
        provenance_ref="si:101",
        confidence=0.9,
    )
    claim_b = EpistemicClaim(
        proposition="Claim B for source 102",
        attributed_to="claim_extraction",
        provenance_kind="si_extraction",
        provenance_ref="si:102",
        epistemic_status="confirmed",
    )
    superseded = EpistemicClaim(
        proposition="Superseded claim",
        attributed_to="claim_extraction",
        provenance_kind="si_extraction",
    )
    session.add_all([obs_a, obs_b, claim_a, claim_b, superseded])
    session.flush()
    superseded.superseded_by_id = claim_a.id
    link_a = EvidenceLink(
        claim_id=claim_a.id,
        observation_ref_id=obs_a.id,
        role="support",
        provenance_kind="si_extraction",
        provenance_ref="si:101",
    )
    link_b = EvidenceLink(
        claim_id=claim_b.id,
        observation_ref_id=obs_b.id,
        role="support",
        provenance_kind="si_extraction",
    )
    session.add_all([link_a, link_b])
    session.commit()
    for row in (obs_a, obs_b, claim_a, claim_b, superseded, link_a, link_b):
        session.refresh(row)
    return SampleData(
        obs_a=obs_a,
        obs_b=obs_b,
        claim_a=claim_a,
        claim_b=claim_b,
        superseded=superseded,
        link_a=link_a,
        link_b=link_b,
    )


@dataclass
class SampleData:
    obs_a: ObservationRef
    obs_b: ObservationRef
    claim_a: EpistemicClaim
    claim_b: EpistemicClaim
    superseded: EpistemicClaim
    link_a: EvidenceLink
    link_b: EvidenceLink

    def cleanup(self, session) -> None:
        for row in (
            self.link_a,
            self.link_b,
            self.claim_a,
            self.claim_b,
            self.superseded,
            self.obs_a,
            self.obs_b,
        ):
            session.delete(row)
        session.commit()


@pytest.mark.unit
def test_read_empty_memory_returns_empty_results():
    session, svc, engine = _session_and_service()
    try:
        summary = svc.get_summary()
        assert summary.observation_ref_count >= 0
        obs, total = svc.list_observation_refs(source_id=999_999)
        assert obs == []
        assert total == 0
        claims, claim_total = svc.list_claims(attributed_to="__no_such_attribution__")
        assert claims == []
        assert claim_total == 0
        assert svc.get_claim(999_999) is None
        assert svc.get_observation_ref(observation_ref_id=999_999) is None
        links, link_total = svc.list_evidence_links_for_claim(999_999)
        assert links == []
        assert link_total == 0
        by_source, by_source_total = svc.list_claims_by_source_id(999_999)
        assert by_source == []
        assert by_source_total == 0
    finally:
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_read_inserted_observation_refs():
    session, svc, engine = _session_and_service()
    obs = ObservationRef(
        observation_key="obs:svc:read-one",
        content_hash="read-one",
        observed_at=datetime.now(timezone.utc),
        provenance_kind="index_extraction",
        source_id=55,
    )
    session.add(obs)
    session.commit()
    session.refresh(obs)
    try:
        by_id = svc.get_observation_ref(observation_ref_id=obs.id)
        assert by_id is not None
        assert by_id.observation_key == "obs:svc:read-one"
        by_key = svc.get_observation_ref(observation_key="obs:svc:read-one")
        assert by_key is not None
        assert by_key.id == obs.id
        listed, total = svc.list_observation_refs(source_id=55)
        assert total >= 1
        assert any(item.id == obs.id for item in listed)
    finally:
        session.delete(obs)
        session.commit()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_read_inserted_claims_and_evidence_links():
    session, svc, engine = _session_and_service()
    sample = _seed_sample(session)
    try:
        claim = svc.get_claim(sample.claim_a.id)
        assert claim is not None
        assert claim.proposition == "Claim A for source 101"
        active, active_total = svc.list_claims(active_only=True)
        assert active_total >= 2
        assert all(item.superseded_by_id is None for item in active)
        assert not any(item.id == sample.superseded.id for item in active)
        by_source, by_source_total = svc.list_claims_by_source_id(101)
        assert by_source_total >= 1
        assert any(item.id == sample.claim_a.id for item in by_source)
        links, link_total = svc.list_evidence_links_for_claim(
            sample.claim_a.id, role="support"
        )
        assert link_total >= 1
        assert links[0].observation_ref_id == sample.obs_a.id
        summary = svc.get_summary()
        assert summary.observation_ref_count >= 2
        assert summary.claim_count >= 3
        assert summary.evidence_link_count >= 2
    finally:
        sample.cleanup(session)
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_pagination_limit_works():
    session, svc, engine = _session_and_service()
    rows: list[ObservationRef] = []
    for i in range(5):
        obs = ObservationRef(
            observation_key=f"obs:svc:page:{i}",
            content_hash=f"page-{i}",
            observed_at=datetime.now(timezone.utc),
            provenance_kind="test",
            source_id=777,
        )
        session.add(obs)
        rows.append(obs)
    session.commit()
    try:
        page1, total = svc.list_observation_refs(source_id=777, limit=2, offset=0)
        page2, _ = svc.list_observation_refs(source_id=777, limit=2, offset=2)
        assert total >= 5
        assert len(page1) == 2
        assert len(page2) == 2
        ids_page1 = {item.id for item in page1}
        ids_page2 = {item.id for item in page2}
        assert ids_page1.isdisjoint(ids_page2)
        clamped, _ = svc.list_observation_refs(source_id=777, limit=10_000)
        assert len(clamped) <= 500
    finally:
        for obs in rows:
            session.delete(obs)
        session.commit()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_service_does_not_mutate_memory_version(monkeypatch):
    state = Settings(knowledge_version=3, memory_version=7)
    save_calls: list[Settings] = []

    class _FakeRepo:
        def get_or_create(self) -> Settings:
            return state

        def save(self, settings: Settings) -> Settings:
            save_calls.append(settings)
            return settings

    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: _FakeRepo(),
    )
    session, svc, engine = _session_and_service()
    try:
        before = MemoryVersionService(session).get()
        svc.get_summary()
        svc.list_claims(limit=1)
        after = MemoryVersionService(session).get()
        assert before == 7
        assert after == 7
        assert save_calls == []
    finally:
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_negative_no_production_writes_to_epistemic_tables():
    violations: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        rel = path.relative_to(APP_ROOT).as_posix()
        if rel.startswith("migrations/"):
            continue
        if rel in EPISTEMIC_MODEL_ALLOWLIST:
            continue
        if rel.startswith(EPISTEMIC_SERVICE_PREFIX):
            if rel in EPISTEMIC_WRITE_ALLOWLIST:
                continue
            continue
        source = path.read_text(encoding="utf-8")
        for token in EPISTEMIC_WRITE_TOKENS:
            if token in source:
                violations.append(f"{rel}: {token}")
    assert violations == []
