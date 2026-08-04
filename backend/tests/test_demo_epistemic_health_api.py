"""Pure unit tests for Epistemic Health API (no Postgres / make_engine)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import require_admin
from app.core.database import get_db
from app.main import app
from app.services.epistemic_memory.provenance_scope import (
    ProvenanceScope,
    claim_matches_scope,
    classify_tension_scope,
    is_test_claim,
    parse_provenance_scope,
)
from app.services.epistemic_memory.types import ProvenanceAwareMemorySummary
from app.services.tension_surfacing.tension_surfacing_service import TensionCountSummary

ENDPOINT = "/api/understanding/tensions"
SUMMARY = "/api/understanding/summary"


@pytest.mark.unit
def test_parse_provenance_scope_defaults_and_errors():
    assert parse_provenance_scope(None) is ProvenanceScope.REAL
    assert parse_provenance_scope("ALL") is ProvenanceScope.ALL
    with pytest.raises(ValueError):
        parse_provenance_scope("nope")


@pytest.mark.unit
def test_is_test_claim_rules():
    assert is_test_claim(provenance_kind="test", attributed_to="x")
    assert is_test_claim(provenance_kind="source_intelligence", attributed_to="fixture")
    assert not is_test_claim(
        provenance_kind="source_intelligence", attributed_to="source_intelligence"
    )
    assert claim_matches_scope(
        provenance_kind="test", attributed_to="fixture", scope=ProvenanceScope.TEST
    )
    assert not claim_matches_scope(
        provenance_kind="test", attributed_to="fixture", scope=ProvenanceScope.REAL
    )


@pytest.mark.unit
def test_classify_tension_scope():
    assert classify_tension_scope([True, True]) == "test"
    assert classify_tension_scope([False, False]) == "real"
    assert classify_tension_scope([True, False]) == "mixed"


@pytest.mark.unit
def test_default_scope_excludes_test_fixtures(monkeypatch):
    captured = {}

    class FakeSurfacing:
        def __init__(self, memory):
            pass

        def surface_tensions(self, **kwargs):
            captured["scope"] = kwargs.get("provenance_scope")
            return []

    monkeypatch.setattr(
        "app.api.understanding.EpistemicMemoryService",
        lambda db: MagicMock(),
    )
    monkeypatch.setattr(
        "app.api.understanding.TensionSurfacingService",
        FakeSurfacing,
    )
    app.dependency_overrides[require_admin] = lambda: MagicMock(role="admin")
    app.dependency_overrides[get_db] = lambda: iter([MagicMock()])
    try:
        client = TestClient(app)
        res = client.get(ENDPOINT)
        assert res.status_code == 200
        assert res.json()["provenance_scope"] == "real"
        assert captured["scope"] == ProvenanceScope.REAL
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
def test_invalid_provenance_scope_422(monkeypatch):
    monkeypatch.setattr(
        "app.api.understanding.EpistemicMemoryService",
        lambda db: MagicMock(),
    )
    app.dependency_overrides[require_admin] = lambda: MagicMock(role="admin")
    app.dependency_overrides[get_db] = lambda: iter([MagicMock()])
    try:
        client = TestClient(app)
        res = client.get(ENDPOINT, params={"provenance_scope": "nope"})
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
def test_summary_endpoint_provenance_aware(monkeypatch):
    class FakeMemory:
        def get_provenance_aware_summary(self):
            return ProvenanceAwareMemorySummary(
                real_claims=6,
                test_claims=33,
                real_active_claims=6,
                test_active_claims=27,
                real_superseded_claims=0,
                test_superseded_claims=6,
                real_observations=3,
                test_observations=10,
                real_evidence_links=6,
                test_evidence_links=15,
                source_intelligence_claims=6,
                all_claims=39,
                all_observations=13,
                all_evidence_links=21,
            )

    class FakeSurfacing:
        def __init__(self, memory):
            pass

        def summarize_counts(self, **kwargs):
            scope = kwargs.get("provenance_scope")
            if scope == ProvenanceScope.REAL:
                return TensionCountSummary(
                    open_tensions=0,
                    support_deficit_tensions=0,
                    conflict_tensions=0,
                    claim_scan_limit=500,
                    provenance_scope="real",
                )
            return TensionCountSummary(
                open_tensions=27,
                support_deficit_tensions=17,
                conflict_tensions=10,
                claim_scan_limit=500,
                provenance_scope="test",
            )

    monkeypatch.setattr(
        "app.api.understanding.EpistemicMemoryService",
        lambda db: FakeMemory(),
    )
    monkeypatch.setattr(
        "app.api.understanding.TensionSurfacingService",
        FakeSurfacing,
    )
    monkeypatch.setattr(
        "app.api.understanding.SettingsRepository",
        lambda db: MagicMock(
            get_or_create=lambda: MagicMock(memory_shadow_write_enabled=False)
        ),
    )
    monkeypatch.setattr(
        "app.api.understanding.MemoryVersionService",
        lambda db: MagicMock(get=lambda: 177),
    )
    monkeypatch.setattr(
        "app.api.understanding.memory_shadow_write_enabled",
        lambda settings: False,
    )
    app.dependency_overrides[require_admin] = lambda: MagicMock(role="admin")
    app.dependency_overrides[get_db] = lambda: iter([MagicMock()])
    try:
        client = TestClient(app)
        res = client.get(SUMMARY)
        assert res.status_code == 200
        body = res.json()
        assert body["real_claims"] == 6
        assert body["test_claims"] == 33
        assert body["real_open_tensions"] == 0
        assert body["test_open_tensions"] == 27
        assert body["chat_impact"] == "not_active"
        assert body["diagnostic_only"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
def test_summary_requires_admin():
    client = TestClient(app)
    res = client.get(SUMMARY)
    assert res.status_code == 401


@pytest.mark.unit
def test_build_info_release_and_capabilities():
    from unittest.mock import patch

    from app.core.config import get_config
    from app.services.build_info_service import APP_RELEASE, BuildInfoService

    assert APP_RELEASE == "1.0"
    svc = BuildInfoService.__new__(BuildInfoService)
    svc._db = MagicMock()
    svc._config = get_config()
    monkey_settings = MagicMock(
        enable_semantic_diagnostics_v2=False,
        cache_namespace_v2_enabled=False,
        memory_shadow_write_enabled=False,
        memory_evidence_assist_enabled=False,
        memory_canonical_shadow_enabled=False,
        allow_legacy_kp_presets=False,
        legacy_doc_type_canonical_enabled=False,
    )
    with (
        patch("app.services.build_info_service.SettingsRepository") as SR,
        patch("app.services.build_info_service.MemoryVersionService") as MV,
        patch("app.services.build_info_service.KnowledgeVersionService") as KV,
        patch(
            "app.services.build_info_service.current_db_revision",
            return_value="0015_memory_shadow_write_enabled",
        ),
    ):
        SR.return_value.get_or_create.return_value = monkey_settings
        MV.return_value.get.return_value = 1
        KV.return_value.get.return_value = 1
        data = svc.collect()
    assert data["release_status"]["accepted"] == "1.0"
    assert data["release_status"]["closed_0_8"] is True
    assert data["release_status"]["closed_0_9"] is True
    assert data["release_status"]["closed_1_0"] is True
    assert data["release_status"]["staging_validated"] is False
    assert data["release_status"]["production_ready"] is False
    assert data["deployed_capabilities"]["REASONING_SERVICE_ENABLED"]["supported"] is True
    assert "memory_shadow_write_enabled" in data["deployed_capabilities"]
