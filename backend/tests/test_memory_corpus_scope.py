"""Unit tests for Memory deployment corpus scope (Step 046 extension)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from types import MappingProxyType
from unittest.mock import MagicMock, patch

import pytest

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.models.settings import Settings
from app.services.epistemic_memory.memory_corpus_resolver import (
    MemoryCorpusBoundary,
    bounded_diagnostic_source_ids,
    normalize_allowed_host_entry,
    resolve_deployment_boundary,
    source_url_allowed,
)
from app.services.epistemic_memory.memory_region_reader import MemoryRegionReader
from app.services.epistemic_memory.memory_region_types import (
    LIMIT_CORPUS_SCOPE_EMPTY,
    LIMIT_CORPUS_SCOPE_INVALID,
    LIMIT_CORPUS_SCOPE_UNCONFIGURED,
    LIMIT_NO_MATCHING_CLAIMS,
    MemoryCorpusScope,
    MemoryIsolationScope,
    MemoryRegionRequest,
)
from app.services.epistemic_memory.provenance_scope import ProvenanceScope


def _claim(cid: int, **kwargs) -> EpistemicClaim:
    return EpistemicClaim(
        id=cid,
        proposition="p",
        epistemic_status=kwargs.get("epistemic_status", "proposal"),
        attributed_to=kwargs.get("attributed_to", "source_intelligence"),
        provenance_kind=kwargs.get("provenance_kind", "source_intelligence"),
        scope_json=kwargs.get("scope_json"),
        superseded_by_id=kwargs.get("superseded_by_id"),
    )


def _reader_with_candidates(
    claims: list[EpistemicClaim],
    evidence_rows: list[tuple[EvidenceLink, ObservationRef]] | None = None,
) -> tuple[MemoryRegionReader, MagicMock]:
    session = MagicMock()
    session.scalars.return_value.all.return_value = claims
    session.execute.return_value.all.return_value = evidence_rows or []
    return MemoryRegionReader(session), session


# --- Isolation contract ---


@pytest.mark.unit
def test_exactly_one_isolation_mode_required():
    with pytest.raises(ValueError, match="requires isolation or source_id"):
        MemoryRegionRequest().normalized_isolation()
    with pytest.raises(ValueError, match="exactly one"):
        MemoryIsolationScope().validate()


@pytest.mark.unit
def test_corpus_and_source_ids_together_rejected_on_scope():
    with pytest.raises(ValueError, match="exactly one"):
        MemoryIsolationScope(
            corpus_scope=MemoryCorpusScope.DEPLOYMENT,
            source_ids=(1,),
        ).validate()


@pytest.mark.unit
def test_request_cannot_combine_isolation_with_legacy_source_fields():
    with pytest.raises(ValueError, match="cannot combine"):
        MemoryRegionRequest(
            isolation=MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT),
            source_id=1,
        ).normalized_isolation()


@pytest.mark.unit
def test_legacy_source_id_still_works():
    scope = MemoryRegionRequest(source_id=5).normalized_isolation()
    assert scope.source_ids == (5,)


# --- Domain normalization ---


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("ukrsibbank.com", "ukrsibbank.com"),
        ("www.ukrsibbank.com", "www.ukrsibbank.com"),
        ("https://ukrsibbank.com/path", "ukrsibbank.com"),
        ("https://ukrsibbank.com:443/x", "ukrsibbank.com"),
        ("subdomain.ukrsibbank.com", "subdomain.ukrsibbank.com"),
        ("", None),
        ("not a host", None),
    ],
)
def test_normalize_allowed_host_entry(raw, expected):
    assert normalize_allowed_host_entry(raw) == expected


@pytest.mark.unit
def test_subdomain_semantics_match_crawler():
    hosts = ("ukrsibbank.com",)
    assert source_url_allowed("https://online.ukrsibbank.com/page", hosts)
    assert not source_url_allowed("https://example.com/page", hosts)


# --- Boundary resolution ---


@pytest.mark.unit
def test_deployment_resolves_allowed_domains_json():
    settings = Settings(
        allowed_domains_json=json.dumps(["ukrsibbank.com", "https://www.ukrsibbank.com"]),
    )
    boundary = resolve_deployment_boundary(settings)
    assert boundary.configured is True
    assert boundary.hosts == ("ukrsibbank.com", "www.ukrsibbank.com")


@pytest.mark.unit
def test_site_url_fallback_when_allowed_domains_empty():
    settings = Settings(
        allowed_domains_json="[]",
        site_url="https://ukrsibbank.com/about",
    )
    boundary = resolve_deployment_boundary(settings)
    assert boundary.configured is True
    assert boundary.hosts == ("ukrsibbank.com",)


@pytest.mark.unit
def test_unconfigured_boundary_fails_closed():
    boundary = resolve_deployment_boundary(None)
    assert boundary.configured is False
    assert boundary.hosts == ()


@pytest.mark.unit
def test_malformed_allowed_domains_reports_invalid():
    settings = Settings(allowed_domains_json="{bad", site_url=None)
    boundary = resolve_deployment_boundary(settings)
    assert boundary.configured is False
    assert "allowed_domains_json" in boundary.invalid_entries


@pytest.mark.unit
def test_mixed_valid_invalid_domain_entries():
    settings = Settings(
        allowed_domains_json=json.dumps(["ukrsibbank.com", "not a host"]),
    )
    boundary = resolve_deployment_boundary(settings)
    assert boundary.hosts == ("ukrsibbank.com",)
    assert "not a host" in boundary.invalid_entries


@pytest.mark.unit
def test_boundary_fingerprint_deterministic():
    boundary = MemoryCorpusBoundary(
        corpus_scope=MemoryCorpusScope.DEPLOYMENT,
        hosts=("ukrsibbank.com",),
        configured=True,
        invalid_entries=(),
        settings_row_id=1,
    )
    assert boundary.fingerprint() == boundary.fingerprint()


# --- Corpus-scoped read_region ---


@pytest.mark.unit
def test_deployment_unconfigured_returns_empty_without_sql_claim_query():
    session = MagicMock()
    reader = MemoryRegionReader(session)
    request = MemoryRegionRequest(
        isolation=MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT),
    )
    with patch(
        "app.services.epistemic_memory.memory_region_reader.SettingsRepository"
    ) as repo_cls:
        repo_cls.return_value.get.return_value = Settings(allowed_domains_json="[]")
        view = reader.read_region(request)
    session.scalars.assert_not_called()
    assert view.total_matched == 0
    assert LIMIT_CORPUS_SCOPE_UNCONFIGURED in view.corpus_limitations
    assert LIMIT_NO_MATCHING_CLAIMS not in view.limitations


@pytest.mark.unit
def test_deployment_empty_corpus_sources_returns_empty_region():
    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    reader = MemoryRegionReader(session)
    settings = Settings(allowed_domains_json=json.dumps(["ukrsibbank.com"]))
    request = MemoryRegionRequest(
        isolation=MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT),
    )
    with patch(
        "app.services.epistemic_memory.memory_region_reader.SettingsRepository"
    ) as repo_cls:
        repo_cls.return_value.get.return_value = settings
        view = reader.read_region(request)
    assert view.total_matched == 0
    assert LIMIT_CORPUS_SCOPE_EMPTY in view.corpus_limitations
    assert view.corpus_scope_configured is True
    assert session.scalars.call_count == 1


@pytest.mark.unit
def test_deployment_reads_claims_after_resolving_source_ids():
    claim = _claim(1)
    session = MagicMock()
    session.scalars.side_effect = [
        MagicMock(all=MagicMock(return_value=[10, 20])),
        MagicMock(all=MagicMock(return_value=[claim])),
    ]
    session.execute.return_value.all.return_value = []
    reader = MemoryRegionReader(session)
    settings = Settings(allowed_domains_json=json.dumps(["ukrsibbank.com"]))
    request = MemoryRegionRequest(
        isolation=MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT),
    )
    with patch(
        "app.services.epistemic_memory.memory_region_reader.SettingsRepository"
    ) as repo_cls:
        repo_cls.return_value.get.return_value = settings
        view = reader.read_region(request)
    assert view.total_matched == 1
    assert view.corpus_anchor_source_count == 2
    assert view.corpus_scope_complete is True


@pytest.mark.unit
def test_explicit_source_scope_unchanged():
    claim = _claim(3)
    reader, session = _reader_with_candidates([claim])
    view = reader.read_region(MemoryRegionRequest(source_id=99))
    assert view.total_matched == 1
    assert view.corpus_scope is None
    assert view.corpus_scope_configured is False
    session.scalars.assert_called_once()


@pytest.mark.unit
def test_test_provenance_still_excluded_under_corpus_scope():
    claim = _claim(4, provenance_kind="test", attributed_to="fixture")
    session = MagicMock()
    session.scalars.side_effect = [
        MagicMock(all=MagicMock(return_value=[1])),
        MagicMock(all=MagicMock(return_value=[claim])),
    ]
    reader = MemoryRegionReader(session)
    settings = Settings(allowed_domains_json=json.dumps(["ukrsibbank.com"]))
    with patch(
        "app.services.epistemic_memory.memory_region_reader.SettingsRepository"
    ) as repo_cls:
        repo_cls.return_value.get.return_value = settings
        view = reader.read_region(
            MemoryRegionRequest(
                isolation=MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT),
            )
        )
    assert view.total_matched == 0
    assert view.provenance_excluded_count == 1


@pytest.mark.unit
def test_no_arbitrary_fifty_source_truncation_in_resolver():
    ids = tuple(range(1, 120))
    bounded = bounded_diagnostic_source_ids(ids)
    assert len(bounded) == 200 or len(bounded) == len(ids)
    assert len(ids) == 119


@pytest.mark.unit
def test_corpus_scope_complete_distinct_from_epistemic_completeness():
    reader, _ = _reader_with_candidates([])
    view = reader.read_region(MemoryRegionRequest(source_id=1))
    assert view.completeness_unknown is True
    assert view.corpus_scope_complete is True


@pytest.mark.unit
def test_view_exposes_isolation_scope_echo():
    isolation = MemoryIsolationScope(source_ids=(7,))
    view = _reader_with_candidates([])[0].read_region(
        MemoryRegionRequest(isolation=isolation)
    )
    assert view.isolation_scope_echo == isolation


@pytest.mark.unit
def test_corpus_hosts_readonly_mapping_not_required_but_hosts_are_tuple():
    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    reader = MemoryRegionReader(session)
    settings = Settings(allowed_domains_json=json.dumps(["ukrsibbank.com"]))
    with patch(
        "app.services.epistemic_memory.memory_region_reader.SettingsRepository"
    ) as repo_cls:
        repo_cls.return_value.get.return_value = settings
        view = reader.read_region(
            MemoryRegionRequest(
                isolation=MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT),
            )
        )
    assert isinstance(view.corpus_hosts, tuple)


@pytest.mark.unit
def test_read_region_no_session_mutations_corpus_path():
    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    reader = MemoryRegionReader(session)
    with patch(
        "app.services.epistemic_memory.memory_region_reader.SettingsRepository"
    ) as repo_cls:
        repo_cls.return_value.get.return_value = Settings(allowed_domains_json="[]")
        reader.read_region(
            MemoryRegionRequest(
                isolation=MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT),
            )
        )
    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize("claim_count", [0, 1, 50])
@pytest.mark.parametrize("include_evidence", [True, False])
@pytest.mark.parametrize("use_corpus", [False, True])
def test_query_counts_explicit_and_corpus(claim_count, include_evidence, use_corpus):
    claims = [_claim(i) for i in range(1, claim_count + 1)]
    session = MagicMock()
    if use_corpus:
        session.scalars.side_effect = [
            MagicMock(all=MagicMock(return_value=[1])),
            MagicMock(all=MagicMock(return_value=claims)),
        ]
    else:
        session.scalars.return_value.all.return_value = claims
    session.execute.return_value.all.return_value = []
    reader = MemoryRegionReader(session)
    if use_corpus:
        with patch(
            "app.services.epistemic_memory.memory_region_reader.SettingsRepository"
        ) as repo_cls:
            repo_cls.return_value.get.return_value = Settings(
                allowed_domains_json=json.dumps(["ukrsibbank.com"])
            )
            reader.read_region(
                MemoryRegionRequest(
                    isolation=MemoryIsolationScope(
                        corpus_scope=MemoryCorpusScope.DEPLOYMENT
                    ),
                    include_evidence=include_evidence,
                )
            )
        expected_scalars = 2
    else:
        reader.read_region(
            MemoryRegionRequest(source_id=1, include_evidence=include_evidence)
        )
        expected_scalars = 1
    assert session.scalars.call_count == expected_scalars
    expected_execute = 1 if include_evidence and claim_count > 0 else 0
    assert session.execute.call_count == expected_execute
