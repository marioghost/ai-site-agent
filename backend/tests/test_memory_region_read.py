"""RFC-100 Step 046 — Memory region read view tests (no live app DB required)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from types import MappingProxyType
from unittest.mock import MagicMock

import pytest

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.models.settings import Settings
from app.services.epistemic_memory.memory_region_reader import (
    MemoryRegionReader,
    _parse_scope_json,
    _topic_matches,
)
from app.services.epistemic_memory.memory_region_types import (
    LIMIT_COMPLETENESS_UNKNOWN,
    LIMIT_EVIDENCE_NOT_REQUESTED,
    LIMIT_LANGUAGE_FILTER_UNAVAILABLE,
    LIMIT_MALFORMED_SCOPE_ROWS_EXCLUDED,
    LIMIT_NO_MATCHING_CLAIMS,
    LIMIT_SPARSE_MEMORY,
    MemoryClaimView,
    MemoryRegionRequest,
    MemoryRegionView,
    readonly_mapping,
)
from app.services.epistemic_memory.provenance_scope import ProvenanceScope


def _claim(
    cid: int,
    *,
    proposition: str = "p",
    provenance_kind: str = "source_intelligence",
    attributed_to: str = "source_intelligence",
    epistemic_status: str = "proposal",
    scope_json: str | None = None,
    superseded_by_id: int | None = None,
) -> EpistemicClaim:
    return EpistemicClaim(
        id=cid,
        proposition=proposition,
        scope_json=scope_json,
        epistemic_status=epistemic_status,
        attributed_to=attributed_to,
        provenance_kind=provenance_kind,
        superseded_by_id=superseded_by_id,
    )


def _obs(oid: int, source_id: int) -> ObservationRef:
    return ObservationRef(
        id=oid,
        observation_key=f"obs:{oid}",
        content_hash=f"h{oid}",
        source_id=source_id,
        observed_at=datetime.now(timezone.utc),
        provenance_kind="source_intelligence",
        excerpt="ex",
    )


def _link(lid: int, claim_id: int, obs_id: int, role: str = "support") -> EvidenceLink:
    return EvidenceLink(
        id=lid,
        claim_id=claim_id,
        observation_ref_id=obs_id,
        role=role,
        provenance_kind="source_intelligence",
    )


def _reader_with_candidates(
    claims: list[EpistemicClaim],
    evidence_rows: list[tuple[EvidenceLink, ObservationRef]] | None = None,
) -> tuple[MemoryRegionReader, MagicMock]:
    session = MagicMock()
    session.scalars.return_value.all.return_value = claims
    if evidence_rows is None:
        evidence_rows = []
    session.execute.return_value.all.return_value = evidence_rows
    return MemoryRegionReader(session), session


# --- Request validation ---


@pytest.mark.unit
def test_request_requires_source_scope():
    with pytest.raises(ValueError, match="source_id"):
        MemoryRegionRequest().normalized_source_ids()


@pytest.mark.unit
@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"source_id": 0}, "source_id must be a positive integer"),
        ({"source_id": -1}, "source_id must be a positive integer"),
        ({"source_ids": (0,)}, "source_ids\\[0\\] must be a positive integer"),
        ({"source_ids": (-1, 5)}, "source_ids\\[0\\] must be a positive integer"),
        ({"source_id": True}, "source_id must be a positive integer, not bool"),
        ({"source_ids": (False, 5)}, "source_ids\\[0\\] must be a positive integer, not bool"),
    ],
)
def test_request_rejects_invalid_source_ids(kwargs, match):
    with pytest.raises(ValueError, match=match):
        MemoryRegionRequest(**kwargs).normalized_source_ids()


@pytest.mark.unit
def test_request_rejects_empty_source_ids_tuple():
    with pytest.raises(ValueError, match="source_id"):
        MemoryRegionRequest(source_ids=()).normalized_source_ids()


@pytest.mark.unit
def test_request_rejects_empty_source_ids_list():
    with pytest.raises(ValueError, match="source_id"):
        MemoryRegionRequest(source_ids=[]).normalized_source_ids()  # type: ignore[arg-type]


@pytest.mark.unit
def test_request_normalizes_sources_and_limit():
    req = MemoryRegionRequest(source_id=5, source_ids=(3, 5, 3), limit=0, offset=-1)
    assert req.normalized_source_ids() == (3, 5)
    assert req.normalized_limit() == 1
    assert req.normalized_offset() == 0


@pytest.mark.unit
def test_invalid_source_id_does_not_query_db():
    reader, session = _reader_with_candidates([_claim(1)])
    with pytest.raises(ValueError, match="source_id"):
        reader.read_region(MemoryRegionRequest(source_id=0))
    session.scalars.assert_not_called()


# --- Lifecycle ---


@pytest.mark.unit
@pytest.mark.parametrize(
    "active_only,include_superseded,expect_superseded",
    [
        (True, False, False),
        (True, True, True),
        (False, True, True),
    ],
)
def test_lifecycle_valid_combinations(active_only, include_superseded, expect_superseded):
    req = MemoryRegionRequest(
        source_id=1, active_only=active_only, include_superseded=include_superseded
    )
    assert req.include_superseded_claims() is expect_superseded


@pytest.mark.unit
def test_lifecycle_rejects_ambiguous_combination():
    req = MemoryRegionRequest(source_id=1, active_only=False, include_superseded=False)
    with pytest.raises(ValueError, match="ambiguous lifecycle"):
        req.validate_lifecycle()


@pytest.mark.unit
def test_ambiguous_lifecycle_does_not_query_db():
    reader, session = _reader_with_candidates([_claim(1)])
    with pytest.raises(ValueError, match="ambiguous lifecycle"):
        reader.read_region(
            MemoryRegionRequest(source_id=1, active_only=False, include_superseded=False)
        )
    session.scalars.assert_not_called()


# --- Region reads ---


@pytest.mark.unit
def test_empty_region():
    view = _reader_with_candidates([])[0].read_region(MemoryRegionRequest(source_id=1))
    assert view.total_matched == 0
    assert LIMIT_NO_MATCHING_CLAIMS in view.limitations
    assert LIMIT_COMPLETENESS_UNKNOWN in view.limitations


@pytest.mark.unit
def test_active_si_claim_with_evidence():
    scope = json.dumps({"page_role": "organization_overview", "document_type": "about_page"})
    claim = _claim(1, proposition="Org", scope_json=scope, epistemic_status="proposal")
    obs = _obs(10, 100)
    link = _link(20, 1, 10)
    view = _reader_with_candidates([claim], [(link, obs)])[0].read_region(
        MemoryRegionRequest(source_id=100)
    )
    assert view.total_matched == 1
    row = view.matched_claims[0]
    assert row.epistemic_status == "proposal"
    assert row.evidence_loaded is True
    assert row.has_support is True
    assert row.has_conflict is False
    assert row.support_observation_source_ids == (100,)


@pytest.mark.unit
def test_test_provenance_excluded_by_default():
    claim = _claim(2, provenance_kind="test", attributed_to="fixture")
    view = _reader_with_candidates([claim])[0].read_region(MemoryRegionRequest(source_id=1))
    assert view.total_matched == 0
    assert view.provenance_excluded_count == 1
    assert view.excluded_test_count == 1


@pytest.mark.unit
def test_test_scope_only():
    claim = _claim(3, provenance_kind="test", attributed_to="fixture")
    view = _reader_with_candidates([claim])[0].read_region(
        MemoryRegionRequest(source_id=1, provenance_scope=ProvenanceScope.TEST)
    )
    assert view.total_matched == 1


@pytest.mark.unit
def test_real_claim_excluded_under_test_scope_counts_provenance_excluded():
    claim = _claim(31, provenance_kind="source_intelligence")
    view = _reader_with_candidates([claim])[0].read_region(
        MemoryRegionRequest(source_id=1, provenance_scope=ProvenanceScope.TEST)
    )
    assert view.total_matched == 0
    assert view.provenance_excluded_count == 1


@pytest.mark.unit
def test_all_scope_includes_test():
    real = _claim(4)
    test = _claim(5, provenance_kind="test", attributed_to="fixture")
    view = _reader_with_candidates([real, test])[0].read_region(
        MemoryRegionRequest(source_id=1, provenance_scope=ProvenanceScope.ALL)
    )
    assert view.total_matched == 2


@pytest.mark.unit
def test_superseded_excluded_by_default():
    active = _claim(6)
    old = _claim(7, superseded_by_id=6)
    view = _reader_with_candidates([active, old])[0].read_region(MemoryRegionRequest(source_id=1))
    assert view.total_matched == 1
    assert view.excluded_superseded_count == 1


@pytest.mark.unit
def test_superseded_included_when_requested():
    active = _claim(8)
    old = _claim(9, superseded_by_id=8)
    view = _reader_with_candidates([active, old])[0].read_region(
        MemoryRegionRequest(source_id=1, include_superseded=True)
    )
    assert view.total_matched == 2


@pytest.mark.unit
def test_page_role_filter():
    ok = _claim(10, scope_json=json.dumps({"page_role": "product_catalog"}))
    no = _claim(11, scope_json=json.dumps({"page_role": "organization_overview"}))
    view = _reader_with_candidates([ok, no])[0].read_region(
        MemoryRegionRequest(source_id=1, page_roles=("product_catalog",))
    )
    assert view.total_matched == 1
    assert view.matched_claims[0].claim_id == 10
    assert view.excluded_scope_mismatch_count == 1


@pytest.mark.unit
def test_epistemic_statuses_filter():
    ok = _claim(32, epistemic_status="accepted")
    no = _claim(33, epistemic_status="proposal")
    view = _reader_with_candidates([ok, no])[0].read_region(
        MemoryRegionRequest(source_id=1, epistemic_statuses=("accepted",))
    )
    assert view.total_matched == 1
    assert view.matched_claims[0].claim_id == 32


@pytest.mark.unit
def test_topic_key_filter():
    ok = _claim(12, scope_json=json.dumps({"main_topic": "credits"}))
    no = _claim(13, scope_json=json.dumps({"main_topic": "deposits"}))
    view = _reader_with_candidates([ok, no])[0].read_region(
        MemoryRegionRequest(source_id=1, topic_key="credits")
    )
    assert view.total_matched == 1


@pytest.mark.unit
def test_malformed_scope_json_safe():
    parsed, malformed = _parse_scope_json("{bad")
    assert parsed is None and malformed is True
    c_bad = _claim(14, scope_json="{bad")
    c_ok = _claim(15, scope_json=json.dumps({"page_role": "generic"}))
    view_all = _reader_with_candidates([c_bad, c_ok])[0].read_region(
        MemoryRegionRequest(source_id=1)
    )
    assert view_all.total_matched == 2
    view_f = _reader_with_candidates([c_bad, c_ok])[0].read_region(
        MemoryRegionRequest(source_id=1, page_roles=("generic",))
    )
    assert view_f.total_matched == 1
    assert LIMIT_MALFORMED_SCOPE_ROWS_EXCLUDED in view_f.limitations
    assert view_f.excluded_scope_mismatch_count == 1


@pytest.mark.unit
def test_topic_matches_exact_not_substring():
    scope = {"main_topic": "Credits"}
    assert _topic_matches(scope, "credits") is True
    assert _topic_matches(scope, "deposits") is False
    assert _topic_matches(scope, "cred") is False
    assert _topic_matches({"main_topic": "microcredits"}, "credits") is False


@pytest.mark.unit
def test_deterministic_ordering_and_pagination():
    claims = [_claim(i) for i in (3, 1, 2)]
    view = _reader_with_candidates(claims)[0].read_region(
        MemoryRegionRequest(source_id=1, limit=2, offset=1)
    )
    assert view.total_matched == 3
    assert [c.claim_id for c in view.matched_claims] == [2, 3]


@pytest.mark.unit
def test_provenance_summary_full_set_before_pagination():
    claims = [
        _claim(40, provenance_kind="source_intelligence"),
        _claim(41, provenance_kind="manual"),
        _claim(42, provenance_kind="manual"),
    ]
    view = _reader_with_candidates(claims)[0].read_region(
        MemoryRegionRequest(source_id=1, limit=1, offset=0)
    )
    assert view.total_matched == 3
    assert view.provenance_summary["manual"] == 2
    assert view.provenance_summary["source_intelligence"] == 1
    assert view.page_provenance_summary["source_intelligence"] == 1
    assert "manual" not in view.page_provenance_summary


@pytest.mark.unit
def test_limit_clamping():
    assert MemoryRegionRequest(source_id=1, limit=9999).normalized_limit() == 500


@pytest.mark.unit
def test_conflict_only_claim_honest():
    claim = _claim(20)
    obs = _obs(30, 5)
    link = _link(40, 20, 30, role="conflict")
    row = _reader_with_candidates([claim], [(link, obs)])[0].read_region(
        MemoryRegionRequest(source_id=5)
    ).matched_claims[0]
    assert row.evidence_loaded is True
    assert row.has_support is False
    assert row.has_conflict is True


@pytest.mark.unit
def test_include_evidence_false_semantics():
    claim = _claim(21)
    view = _reader_with_candidates([claim])[0].read_region(
        MemoryRegionRequest(source_id=1, include_evidence=False)
    )
    row = view.matched_claims[0]
    assert row.evidence == ()
    assert row.evidence_loaded is False
    assert row.has_support is None
    assert row.has_conflict is None
    assert LIMIT_EVIDENCE_NOT_REQUESTED in view.limitations


@pytest.mark.unit
def test_language_limitation():
    view = _reader_with_candidates([_claim(22)])[0].read_region(
        MemoryRegionRequest(source_id=1, language="uk")
    )
    assert LIMIT_LANGUAGE_FILTER_UNAVAILABLE in view.limitations


@pytest.mark.unit
def test_sparse_memory_limitation():
    view = _reader_with_candidates([_claim(23)])[0].read_region(MemoryRegionRequest(source_id=1))
    assert LIMIT_SPARSE_MEMORY in view.limitations


@pytest.mark.unit
def test_information_need_echoed_only():
    view = _reader_with_candidates([])[0].read_region(
        MemoryRegionRequest(source_id=1, information_need="enumeration")
    )
    assert view.request_echo.information_need == "enumeration"


@pytest.mark.unit
def test_limitations_deterministic_and_deduped():
    view = _reader_with_candidates([])[0].read_region(
        MemoryRegionRequest(source_id=1, include_evidence=False, language="uk")
    )
    assert view.limitations == tuple(dict.fromkeys(view.limitations))
    assert view.limitations[0] == LIMIT_COMPLETENESS_UNKNOWN


@pytest.mark.unit
def test_completeness_unknown_always_true():
    view = _reader_with_candidates([_claim(26)])[0].read_region(MemoryRegionRequest(source_id=1))
    assert view.completeness_unknown is True


@pytest.mark.unit
def test_dto_scope_and_provenance_summary_are_readonly():
    scope = json.dumps({"page_role": "generic"})
    claim = _claim(50, scope_json=scope)
    view = _reader_with_candidates([claim])[0].read_region(MemoryRegionRequest(source_id=1))
    row = view.matched_claims[0]
    assert isinstance(row.scope, MappingProxyType)
    with pytest.raises(TypeError):
        row.scope["page_role"] = "mutated"  # type: ignore[index]
    with pytest.raises(TypeError):
        view.provenance_summary["manual"] = 99  # type: ignore[index]


@pytest.mark.unit
def test_readonly_mapping_helper():
    ro = readonly_mapping({"a": 1})
    assert isinstance(ro, MappingProxyType)
    with pytest.raises(TypeError):
        ro["a"] = 2  # type: ignore[index]


@pytest.mark.unit
def test_no_orm_leakage_in_claim_view():
    claim = _claim(51)
    view = _reader_with_candidates([claim])[0].read_region(MemoryRegionRequest(source_id=1))
    row = view.matched_claims[0]
    assert isinstance(row, MemoryClaimView)
    assert not isinstance(row, EpistemicClaim)


@pytest.mark.unit
def test_read_region_delegates_from_service():
    from app.services.epistemic_memory import EpistemicMemoryService

    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    svc = EpistemicMemoryService(session)
    view = svc.read_region(MemoryRegionRequest(source_id=99))
    assert view.total_matched == 0
    session.scalars.assert_called()


@pytest.mark.unit
def test_read_region_no_session_mutations():
    reader, session = _reader_with_candidates([_claim(60)])
    reader.read_region(MemoryRegionRequest(source_id=1))
    session.add.assert_not_called()
    session.add_all.assert_not_called()
    session.delete.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.unit
def test_read_region_does_not_bump_versions(monkeypatch):
    from app.services.epistemic_memory import EpistemicMemoryService

    state = Settings(knowledge_version=11, memory_version=4)
    session = MagicMock()
    session.scalars.return_value.all.return_value = []

    class _BumpGuard:
        def bump(self, *_args, **_kwargs):
            raise AssertionError("version bump during read_region")

    monkeypatch.setattr(
        "app.services.memory_version_service.MemoryVersionService",
        lambda _db: _BumpGuard(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_version_service.KnowledgeVersionService",
        lambda _db: _BumpGuard(),
    )

    svc = EpistemicMemoryService(session)
    svc.read_region(MemoryRegionRequest(source_id=1))
    assert state.knowledge_version == 11
    assert state.memory_version == 4


# --- Query count instrumentation ---


@pytest.mark.unit
@pytest.mark.parametrize("claim_count", [0, 1, 50])
@pytest.mark.parametrize("include_evidence", [True, False])
def test_query_counts(claim_count, include_evidence):
    claims = [_claim(i) for i in range(1, claim_count + 1)]
    reader, session = _reader_with_candidates(claims)
    reader.read_region(
        MemoryRegionRequest(source_id=1, include_evidence=include_evidence)
    )
    assert session.scalars.call_count == 1
    expected_execute = 1 if include_evidence and claim_count > 0 else 0
    assert session.execute.call_count == expected_execute
