"""RFC-100 Step 065 — build-info derives from canonical flag definitions."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.settings import Settings
from app.services.feature_flags import (
    knowledge_os_executive_enabled,
    maintenance_observation,
    reasoning_service_enabled,
)

pytestmark = pytest.mark.unit


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
        enable_semantic_diagnostics_v2=True,
        cache_namespace_v2_enabled=True,
        memory_shadow_write_enabled=True,
        memory_evidence_assist_enabled=True,
        memory_canonical_shadow_enabled=True,
        allow_legacy_kp_presets=False,
        legacy_doc_type_canonical_enabled=False,
    )
    build_file = tmp_path / ".build-info.json"
    build_file.write_text(
        json.dumps(
            {
                "release": "0.9",
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
        lambda: "0020_step_063_kos_flags_default_on (head)",
    )
    cfg = MagicMock(
        knowledge_os_executive_enabled=True,
        reasoning_service_enabled=True,
        evidence_assembly_enabled=True,
        reasoning_speech_acts_enabled=True,
    )
    monkeypatch.setattr("app.services.build_info_service.get_config", lambda: cfg)
    monkeypatch.setattr("app.services.feature_flags.get_config", lambda: cfg)
    monkeypatch.delenv("MAINTENANCE_EXECUTION_ENABLED", raising=False)
    monkeypatch.delenv("MAINTENANCE_INVESTIGATIONS_PER_CYCLE", raising=False)

    def override_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_build_info_compatible_shape_and_bool_maps(build_client: TestClient):
    body = build_client.get("/api/build").json()
    for key in (
        "feature_flags",
        "env_flags",
        "settings_flags",
        "deployed_capabilities",
        "release_status",
        "maintenance_observation",
    ):
        assert key in body

    assert isinstance(body["env_flags"], dict)
    assert all(isinstance(v, bool) for v in body["env_flags"].values())
    assert all(isinstance(v, bool) for v in body["settings_flags"].values())
    assert "MAINTENANCE_INVESTIGATIONS_PER_CYCLE" not in body["env_flags"]

    maint = body["maintenance_observation"]
    assert isinstance(maint["execution_enabled"], bool)
    assert isinstance(maint["investigations_per_cycle"], int)
    assert maint["investigations_per_cycle"] == 0
    assert maint["execution_enabled"] is True
    obs = maintenance_observation(environ={})
    assert maint["execution_enabled"] is obs["execution_enabled"]
    assert maint["investigations_per_cycle"] == obs["investigations_per_cycle"]


def test_build_info_helper_parity_and_executive_description(build_client: TestClient):
    body = build_client.get("/api/build").json()
    assert body["env_flags"]["KNOWLEDGE_OS_EXECUTIVE_ENABLED"] is knowledge_os_executive_enabled()
    assert body["env_flags"]["REASONING_SERVICE_ENABLED"] is reasoning_service_enabled()

    exec_cap = body["deployed_capabilities"]["KNOWLEDGE_OS_EXECUTIVE_ENABLED"]
    assert "controlled unavailable" in exec_cap["effect"].lower()
    assert "direct Rag" not in exec_cap["effect"]
    assert exec_cap["classification"] == "permanent_kill_switch"

    legacy = body["deployed_capabilities"]["allow_legacy_kp_presets"]
    assert legacy["classification"] == "legacy_compatibility"
    assert body["settings_flags"]["allow_legacy_kp_presets"] is False
    assert body["settings_flags"]["legacy_doc_type_canonical_enabled"] is False

    assist = body["deployed_capabilities"]["memory_evidence_assist_enabled"]
    assert "effective" in assist
    shadow = body["deployed_capabilities"]["memory_canonical_shadow_enabled"]
    assert "effective" in shadow

    rs = body["release_status"]
    assert rs["accepted"] == "0.9"
    assert rs["in_progress"] == "1.0"
    assert rs["staging_validated"] is False
    assert rs["production_ready"] is False
