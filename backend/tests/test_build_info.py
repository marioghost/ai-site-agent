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
        lambda: "0013_cache_namespace_v2_enabled (head)",
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
    assert body["alembic_head"] == "0013_cache_namespace_v2_enabled (head)"
    assert body["memory_version"] == 2
    assert body["knowledge_version"] == 5
    assert body["feature_flags"]["KNOWLEDGE_OS_EXECUTIVE_ENABLED"] is False
    assert body["settings_flags"]["cache_namespace_v2_enabled"] is False
    assert body["release_status"]["accepted"] == "0.5"
    assert body["release_status"]["closed_0_6"] is False
    assert "deployed_capabilities" in body
    assert body["deployed_capabilities"]["KNOWLEDGE_OS_EXECUTIVE_ENABLED"]["supported"] is True
