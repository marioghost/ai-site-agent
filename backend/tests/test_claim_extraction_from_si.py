"""RFC-100 Step 029 — ClaimExtractionFromSI mapper tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.models.settings import Settings
from app.models.source import Source
from app.services.epistemic_memory import ClaimExtractionFromSI
from app.services.memory_version_service import MemoryVersionService
from app.services.source_intelligence_service import SourceIntelligenceService, SourceProfile

MAPPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "services"
    / "epistemic_memory"
    / "claim_extraction_from_si.py"
)

FORBIDDEN_DOMAIN_TERMS = (
    "bank",
    "customer",
    "credit_card",
    "mortgage",
    "about_bank",
    "product_page",
    "should_answer_product",
)


def _generic_source(**overrides) -> Source:
    base = dict(
        id=42,
        url="https://example.com/about/",
        source_type="page",
        status="indexed",
        title="About the organization",
        document_type="about_page",
        main_content_text="We provide services across multiple regions since 2010.",
        main_content_chars=1200,
        boilerplate_ratio=0.1,
        content_hash="abc123hash",
    )
    base.update(overrides)
    return Source(**base)


def _apply_profile(source: Source) -> SourceProfile:
    profile = SourceIntelligenceService.build_profile(source)
    SourceIntelligenceService.apply_to_source(source, profile)
    return profile


@pytest.mark.unit
def test_maps_valid_si_to_claim_proposals():
    source = _generic_source()
    _apply_profile(source)
    proposals = ClaimExtractionFromSI().extract_from_source(source)
    assert len(proposals) >= 1
    first = proposals[0]
    assert first.proposition
    assert first.source_id == 42
    assert first.epistemic_status == "proposal"
    assert first.attributed_to == "source_intelligence"
    assert first.provenance_kind == "source_intelligence"
    assert first.provenance_ref.startswith("source:42:si:")
    assert first.confidence is not None
    assert first.confidence >= 0.35
    assert len(first.evidence) == 1
    assert first.evidence[0].source_id == 42
    assert first.evidence[0].content_hash == "abc123hash"
    assert first.evidence[0].observation_key_hint == "obs:source:42:si"


@pytest.mark.unit
def test_ignores_empty_or_invalid_si_safely():
    mapper = ClaimExtractionFromSI()
    bare = _generic_source(profile_version=None, llm_summary="", intelligence_json="{}")
    assert mapper.extract_from_source(bare) == []

    low_conf = SourceProfile(
        source_id=1,
        url="https://example.com/x",
        confidence=0.1,
        llm_summary="Too short",
        semantic={"main_topic": "x"},
    )
    assert mapper.extract_from_profile(_generic_source(id=1), low_conf) == []

    invalid = _generic_source(
        profile_version="v1",
        profile_confidence=0.9,
        llm_summary="Valid length summary here.",
        intelligence_json="{not-json",
    )
    invalid.topics_json = "[]"
    invalid.keywords_json = "[]"
    invalid.entity_types_json = "[]"
    # profile_from_source returns None when profile_version missing on second case;
    # for malformed semantic, extraction should still not crash.
    proposals = mapper.extract_from_source(invalid)
    assert isinstance(proposals, list)


@pytest.mark.unit
def test_includes_provenance_on_every_proposal():
    source = _generic_source()
    profile = _apply_profile(source)
    proposals = ClaimExtractionFromSI().extract_from_profile(source, profile)
    assert proposals
    for proposal in proposals:
        assert proposal.provenance_kind == "source_intelligence"
        assert proposal.provenance_ref
        assert proposal.scope_json
        assert "proposal_kind" in proposal.scope_json
        assert proposal.evidence
        assert proposal.evidence[0].excerpt


@pytest.mark.unit
def test_deduplicates_near_duplicate_propositions():
    source = _generic_source()
    profile = SourceProfile(
        source_id=source.id,
        url=source.url,
        confidence=0.8,
        llm_summary="Organization overview and services.",
        semantic={
            "main_topic": "Organization overview and services",
            "main_topic_confidence": 0.9,
            "document_purpose": "about company",
            "document_purpose_confidence": 0.85,
            "confidence": 0.85,
        },
    )
    proposals = ClaimExtractionFromSI().extract_from_profile(source, profile)
    normalized = [p.proposition.lower().strip() for p in proposals]
    assert len(normalized) == len(set(normalized))


@pytest.mark.unit
def test_mapper_does_not_bump_memory_version(monkeypatch):
    state = Settings(knowledge_version=2, memory_version=5)
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
    source = _generic_source()
    _apply_profile(source)
    before = MemoryVersionService(db=None).get()
    ClaimExtractionFromSI().extract_from_source(source)
    after = MemoryVersionService(db=None).get()
    assert before == after == 5
    assert save_calls == []


@pytest.mark.unit
def test_no_hardcoded_bank_or_customer_rules_in_mapper():
    source = MAPPER_PATH.read_text(encoding="utf-8").lower()
    for term in FORBIDDEN_DOMAIN_TERMS:
        assert term not in source, f"unexpected hardcoded domain term: {term}"


@pytest.mark.unit
def test_no_db_writes_in_mapper_module():
    source = MAPPER_PATH.read_text(encoding="utf-8")
    forbidden = (
        "session.add",
        "session.commit",
        "EpistemicClaim(",
        "ObservationRef(",
        "EvidenceLink(",
        "EpistemicMemoryService(",
    )
    for token in forbidden:
        assert token not in source
