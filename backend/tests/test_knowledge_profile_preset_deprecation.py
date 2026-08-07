"""RFC-100 Step 017 — Deprecation headers on Knowledge Profile preset load."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.knowledge_profile_deprecation import (
    KNOWLEDGE_PROFILE_PRESET_LOAD_DEPRECATION_LINK,
    apply_knowledge_profile_preset_load_deprecation,
)
from app.api.deps import require_admin
from app.core.database import get_db
from app.main import app
from app.services.knowledge_profile_service import KnowledgeProfileService

PRESET_ID = "documentation_portal"


def _stub_knowledge_profile_deps(monkeypatch, *, allow_presets: bool = True) -> None:
    class FakeRepo:
        def get_or_create(self):
            settings = MagicMock()
            settings.knowledge_profile_json = "{}"
            settings.allow_legacy_kp_presets = allow_presets
            return settings

        def save(self, settings):
            return settings

    monkeypatch.setattr("app.api.knowledge_profile.SettingsRepository", lambda db: FakeRepo())
    monkeypatch.setattr(
        "app.api.knowledge_profile.CacheInvalidationService",
        lambda db, settings: MagicMock(invalidate_for_correctness=lambda reason: 0),
    )
    monkeypatch.setattr(
        "app.api.knowledge_profile.mark_sources_needs_reprocess",
        lambda db, reason: None,
    )


@pytest.fixture()
def kp_client(monkeypatch) -> TestClient:
    _stub_knowledge_profile_deps(monkeypatch)

    def override_admin():
        return MagicMock()

    def override_db():
        yield MagicMock()

    app.dependency_overrides[require_admin] = override_admin
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.unit
def test_apply_preset_load_deprecation_headers_metadata():
    from starlette.responses import Response

    response = Response()
    apply_knowledge_profile_preset_load_deprecation(response)
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Link"] == KNOWLEDGE_PROFILE_PRESET_LOAD_DEPRECATION_LINK
    assert 'rel="deprecation"' in response.headers["Link"]
    assert "RFC-100-PRODUCTION-MIGRATION-STRATEGY" in response.headers["Link"]
    assert "Sunset" not in response.headers


@pytest.mark.unit
def test_preset_load_returns_unchanged_body(kp_client: TestClient):
    expected = KnowledgeProfileService.load_preset(PRESET_ID).model_dump(mode="json")
    res = kp_client.post(
        "/api/knowledge-profile/presets/load",
        json={"preset_id": PRESET_ID},
    )
    assert res.status_code == 200
    assert res.json() == expected


@pytest.mark.unit
def test_preset_load_includes_deprecation_header(kp_client: TestClient):
    res = kp_client.post(
        "/api/knowledge-profile/presets/load",
        json={"preset_id": PRESET_ID},
    )
    assert res.status_code == 200
    assert res.headers.get("Deprecation") == "true"
    assert res.headers.get("Link") == KNOWLEDGE_PROFILE_PRESET_LOAD_DEPRECATION_LINK
    assert res.headers.get("Sunset") is None


@pytest.mark.unit
def test_other_knowledge_profile_endpoints_omit_deprecation_header(kp_client: TestClient, monkeypatch):
    profile = KnowledgeProfileService.load_preset(PRESET_ID)
    monkeypatch.setattr(
        "app.api.knowledge_profile.KnowledgeProfileService.from_settings",
        lambda settings: profile,
    )
    monkeypatch.setattr(
        "app.api.knowledge_profile.KnowledgeProfileService.list_presets",
        lambda: [{"id": PRESET_ID, "label": "Generic corporate website"}],
    )
    monkeypatch.setattr(
        "app.api.knowledge_profile.KnowledgeProfileService.export_profile",
        lambda p: {"profile": p.model_dump(mode="json")},
    )

    app.dependency_overrides[require_admin] = lambda: MagicMock()

    from app.api.deps import require_authenticated

    app.dependency_overrides[require_authenticated] = lambda: MagicMock()

    get_res = kp_client.get("/api/knowledge-profile")
    presets_res = kp_client.get("/api/knowledge-profile/presets")
    export_res = kp_client.get("/api/knowledge-profile/export")

    for res in (get_res, presets_res, export_res):
        assert res.status_code == 200
        assert res.headers.get("Deprecation") is None
        assert res.headers.get("Link") is None

    app.dependency_overrides.pop(require_authenticated, None)
