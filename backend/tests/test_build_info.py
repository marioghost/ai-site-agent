"""Tests for GET /api/build release metadata."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.settings import Settings

APP_ROOT = Path(__file__).resolve().parents[1]


def _fake_repo(state: Settings):
    class FakeRepo:
        def get_or_create(self) -> Settings:
            return state

        def save(self, settings: Settings) -> Settings:
            return settings

    return FakeRepo


@pytest.fixture()
def build_client(monkeypatch, tmp_path: Path) -> TestClient:
    state = Settings(
        knowledge_version=5,
        memory_version=2,
        enable_semantic_diagnostics_v2=False,
        cache_namespace_v2_enabled=False,
    )
    build_file = tmp_path / ".build-info.json"
    build_file.write_text(
        json.dumps(
            {
                "release": "0.3",
                "git_commit": "abc123",
                "git_commit_short": "abc123",
                "build_time": "2026-07-05T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.services.build_info_service._project_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.build_info_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.build_info_service.current_db_revision",
        lambda: "0016_memory_evidence_assist_enabled (head)",
    )
    monkeypatch.setattr(
        "app.services.build_info_service.get_config",
        lambda: MagicMock(knowledge_os_executive_enabled=False),
    )

    def override_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.unit
def test_build_info_endpoint(build_client: TestClient):
    res = build_client.get("/api/build")
    assert res.status_code == 200
    body = res.json()
    assert body["release"] == "0.3"
    assert body["git_commit"] == "abc123"
    assert body["build_time"] == "2026-07-05T12:00:00Z"
    assert body["alembic_head"] == "0016_memory_evidence_assist_enabled (head)"
    assert body["memory_version"] == 2
    assert body["knowledge_version"] == 5
    assert body["feature_flags"]["KNOWLEDGE_OS_EXECUTIVE_ENABLED"] is False
    assert body["settings_flags"]["cache_namespace_v2_enabled"] is False
    assert body["release_status"]["accepted"] == "0.9"
    assert body["release_status"]["closed_0_6"] is True
    assert body["release_status"]["closed_0_7"] is True
    assert body["release_status"]["closed_0_8"] is True
    assert body["release_status"]["closed_0_9"] is True
    assert body["release_status"]["engineering_ready"] is True
    assert body["release_status"]["staging_validated"] is False
    assert body["release_status"]["production_ready"] is False
    assert body["release_status"]["in_progress"] == "1.0"
    assert body["release_status"]["steps_063"][0]["step"] == "063"
    assert body["release_status"]["steps_063"][1]["step"] == "064"
    caps = body["release_status"]["release_0_7_capabilities"]
    assert caps["memory_region_reads"]["code_present"] is True
    assert caps["memory_evidence_assist"]["code_present"] is True
    assert caps["memory_evidence_assist"]["enabled"] is False
    assert caps["memory_evidence_assist"]["effective"] is False
    assert caps["memory_canonical_shadow"]["code_present"] is True
    assert caps["memory_canonical_shadow"]["enabled"] is False
    assert caps["memory_canonical_shadow"]["effective"] is False
    assert caps["memory_offline_evaluation"]["code_present"] is True
    caps8 = body["release_status"]["release_0_8_capabilities"]
    assert caps8["settings_boost_api_removed"]["code_present"] is True
    assert caps8["dashboard_boost_inputs_removed"]["code_present"] is True
    assert caps8["legacy_kp_presets_disabled"]["code_present"] is True
    assert caps8["legacy_kp_presets_disabled"]["configured"] is True
    assert caps8["legacy_kp_presets_disabled"]["enabled"] is False
    assert caps8["legacy_doc_type_canonical_gated"]["code_present"] is True
    assert caps8["legacy_doc_type_canonical_gated"]["enabled"] is False
    assert caps8["golden_generic_profile_ci"]["code_present"] is True
    steps8 = body["release_status"]["steps_052_057"]
    assert [s["step"] for s in steps8] == ["052", "053", "054", "055", "056", "057"]
    caps9 = body["release_status"]["release_0_9_capabilities"]
    assert caps9["maintenance_agenda_ranking"]["code_present"] is True
    assert caps9["maintenance_cycle_orchestration"]["code_present"] is True
    assert caps9["index_integrate_compose"]["code_present"] is True
    assert caps9["investigation_execution_fetch"]["code_present"] is True
    assert caps9["investigation_metrics"]["code_present"] is True
    assert caps9["release_0_9_engineering_closure"]["code_present"] is True
    steps9 = body["release_status"]["steps_058_062"]
    assert [s["step"] for s in steps9] == ["058", "059", "060", "061", "062"]
    assert "deployed_capabilities" in body
    assert body["deployed_capabilities"]["KNOWLEDGE_OS_EXECUTIVE_ENABLED"]["supported"] is True
