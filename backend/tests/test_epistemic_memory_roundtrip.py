"""RFC-100 Step 032 — claim roundtrip and provenance tests.

Validates shadow persist → read API roundtrip and provenance chain integrity.
Encodes ADR-0001 observation identity semantics (stable key per source).
No production code changes — tests and documentation only.
"""
from __future__ import annotations

import json
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
from app.services.source_intelligence_constants import SOURCE_INTELLIGENCE_VERSION
from app.services.source_intelligence_service import SourceIntelligenceService


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


def _sample_source(session, *, suffix: str | None = None) -> Source:
    token = suffix or uuid.uuid4().hex[:8]
    source = Source(
        url=f"https://example.com/roundtrip-{token}/",
        source_type="page",
        status="indexed",
        title="About the organization",
        document_type="about_page",
        main_content_text="We provide services across multiple regions since 2010.",
        main_content_chars=1200,
        boilerplate_ratio=0.1,
        content_hash=f"roundtrip-hash-{token}",
    )
    session.add(source)
    session.flush()
    return source


def _profile_for(source: Source):
    profile = SourceIntelligenceService.build_profile(source)
    SourceIntelligenceService.apply_to_source(source, profile)
    return profile


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


def _observation_key(source_id: int) -> str:
    return f"obs:source:{source_id}:si"


def _provenance_ref(source_id: int) -> str:
    return f"source:{source_id}:si:{SOURCE_INTELLIGENCE_VERSION}"


@pytest.mark.unit
def test_shadow_write_roundtrip_via_read_api():
    """Persist through integration, read back only via EpistemicMemoryService."""
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session)
        profile = _profile_for(source)

        EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
            source, profile
        )
        session.commit()

        svc = EpistemicMemoryService(session)
        obs = svc.get_observation_ref(observation_key=_observation_key(source.id))
        assert obs is not None
        assert obs.source_id == source.id
        assert obs.content_hash == source.content_hash

        claims, total = svc.list_claims_by_source_id(source.id)
        assert total >= 1
        assert len(claims) == total

        for claim in claims:
            assert claim.attributed_to == "source_intelligence"
            assert claim.provenance_kind == "source_intelligence"
            assert claim.provenance_ref == _provenance_ref(source.id)
            assert claim.epistemic_status == "proposal"

            links, link_total = svc.list_evidence_links_for_claim(claim.id)
            assert link_total >= 1
            assert links[0].observation_ref_id == obs.id
            assert links[0].role == "support"

        summary = svc.get_summary()
        assert summary.observation_ref_count >= 1
        assert summary.claim_count >= 1
        assert summary.evidence_link_count >= 1

        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_provenance_chain_complete_on_all_layers():
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session)
        profile = _profile_for(source)
        expected_ref = _provenance_ref(source.id)

        EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
            source, profile
        )
        session.commit()

        svc = EpistemicMemoryService(session)
        obs = svc.get_observation_ref(observation_key=_observation_key(source.id))
        assert obs is not None
        assert obs.provenance_kind == "source_intelligence"
        assert obs.provenance_ref == expected_ref
        assert obs.extraction_version == SOURCE_INTELLIGENCE_VERSION

        claims, _ = svc.list_claims_by_source_id(source.id)
        assert claims
        for claim in claims:
            assert claim.provenance_kind == "source_intelligence"
            assert claim.provenance_ref == expected_ref
            links, _ = svc.list_evidence_links_for_claim(claim.id)
            for link in links:
                assert link.provenance_kind == "source_intelligence"
                assert link.provenance_ref == expected_ref

        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_scope_json_carries_proposal_kind_and_source_context():
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session)
        profile = _profile_for(source)

        EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
            source, profile
        )
        session.commit()

        claims, _ = EpistemicMemoryService(session).list_claims_by_source_id(source.id)
        assert claims
        kinds = set()
        for claim in claims:
            assert claim.scope_json
            scope = json.loads(claim.scope_json)
            assert scope["source_id"] == source.id
            assert scope["url"] == source.url
            assert scope["document_type"] == profile.document_type
            assert scope["proposal_kind"] in {
                "llm_summary",
                "main_topic",
                "document_purpose",
                "subtopics",
            }
            kinds.add(scope["proposal_kind"])
        assert kinds  # at least one proposal kind present

        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_re_si_reuses_observation_preserves_first_content_hash():
    """ADR-0001: stable obs key reuses row; content_hash from first persist kept."""
    session, engine = _session()
    try:
        settings = _settings(shadow=True)
        source = _sample_source(session, suffix="adr0001")
        profile = _profile_for(source)
        integration = EpistemicMemoryIntegrationService(session, settings)
        obs_key = _observation_key(source.id)

        integration.shadow_write_after_si(source, profile)
        session.commit()

        svc = EpistemicMemoryService(session)
        obs_first = svc.get_observation_ref(observation_key=obs_key)
        assert obs_first is not None
        first_hash = obs_first.content_hash
        first_obs_id = obs_first.id

        source.content_hash = "roundtrip-hash-changed-after-reindex"
        source.main_content_text = "Updated content after re-index."
        session.flush()
        profile2 = _profile_for(source)

        integration.shadow_write_after_si(source, profile2)
        session.commit()

        obs_second = svc.get_observation_ref(observation_key=obs_key)
        assert obs_second is not None
        assert obs_second.id == first_obs_id
        assert obs_second.content_hash == first_hash
        assert obs_second.content_hash != source.content_hash

        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_flag_off_no_roundtrip_rows():
    session, engine = _session()
    try:
        settings = _settings(shadow=False)
        source = _sample_source(session)
        profile = _profile_for(source)

        result = EpistemicMemoryIntegrationService(session, settings).shadow_write_after_si(
            source, profile
        )
        assert result is None
        session.commit()

        svc = EpistemicMemoryService(session)
        assert svc.get_observation_ref(observation_key=_observation_key(source.id)) is None
        claims, total = svc.list_claims_by_source_id(source.id)
        assert total == 0
        assert claims == []

        _cleanup_shadow_for_source(session, source)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_roundtrip_documented_in_adr_index():
    adr_path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "docs"
        / "adr"
        / "0001-shadow-observation-key-per-source.md"
    )
    text = adr_path.read_text(encoding="utf-8")
    assert "obs:source:{source_id}:si" in text
    assert "NOT a blocker for RFC-100 Step 032" in text
