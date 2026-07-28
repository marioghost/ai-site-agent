"""RFC-100 Step 054 — allow_legacy_kp_presets default false + Preset 410."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import require_admin, require_authenticated
from app.api.knowledge_profile_deprecation import (
    KNOWLEDGE_PROFILE_PRESET_LOAD_DEPRECATION_LINK,
)
from app.api.knowledge_profile_preset_errors import (
    LEGACY_KP_PRESETS_DISABLED_CODE,
    LEGACY_KP_PRESETS_DISABLED_DETAIL,
    LEGACY_KP_PRESETS_DISABLED_MESSAGE,
)
from app.core.database import get_db
from app.main import app
from app.models.settings import Settings
from app.schemas.settings import SettingsBase, SettingsRead, SettingsUpdate
from app.services.feature_flags import allow_legacy_kp_presets
from app.services.knowledge_profile_service import KnowledgeProfileService, PRESETS

PRESET_ID = "documentation_portal"
MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def _load_migration(name: str):
    path = MIGRATIONS / name
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _stub_kp_repo(monkeypatch, *, allow_presets: bool) -> MagicMock:
    settings = MagicMock()
    settings.knowledge_profile_json = "{}"
    settings.allow_legacy_kp_presets = allow_presets

    class FakeRepo:
        def get_or_create(self):
            return settings

        def save(self, s):
            return s

    monkeypatch.setattr("app.api.knowledge_profile.SettingsRepository", lambda db: FakeRepo())
    monkeypatch.setattr(
        "app.api.knowledge_profile.CacheInvalidationService",
        lambda db, s: MagicMock(invalidate_retrieval_cache=lambda reason: None),
    )
    monkeypatch.setattr(
        "app.api.knowledge_profile.mark_sources_needs_reprocess",
        lambda db, reason: None,
    )
    return settings


@pytest.fixture()
def kp_client_factory(monkeypatch):
    def _make(*, allow_presets: bool) -> TestClient:
        _stub_kp_repo(monkeypatch, allow_presets=allow_presets)
        app.dependency_overrides[require_admin] = lambda: MagicMock()
        app.dependency_overrides[require_authenticated] = lambda: MagicMock()

        def override_db():
            yield MagicMock()

        app.dependency_overrides[get_db] = override_db
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


@pytest.mark.unit
def test_migration_0018_chain_and_additive():
    m18 = _load_migration("0018_allow_legacy_kp_presets.py")
    assert m18.revision == "0018_allow_legacy_kp_presets"
    assert m18.down_revision == "0017_memory_canonical_shadow_enabled"
    assert len(m18.revision) <= 64

    text = (MIGRATIONS / "0018_allow_legacy_kp_presets.py").read_text(encoding="utf-8")
    assert "allow_legacy_kp_presets" in text
    assert "server_default=sa.false()" in text
    assert "nullable=False" in text
    assert "op.add_column" in text
    assert 'op.drop_column("settings", "allow_legacy_kp_presets")' in text
    assert "knowledge_profile_json" not in text
    assert "DROP TABLE" not in text.upper()

    # Exactly one head: 0018's down is 0017; no other migration claims 0018 parent.
    downs = []
    for path in MIGRATIONS.glob("*.py"):
        if path.name.startswith("__"):
            continue
        mod = _load_migration(path.name)
        downs.append((mod.revision, mod.down_revision))
    children = [r for r, d in downs if d == "0017_memory_canonical_shadow_enabled"]
    assert children == ["0018_allow_legacy_kp_presets"]
    # 0018 may gain later children (e.g. 0019); require it remains on the linear chain.
    assert any(r == "0018_allow_legacy_kp_presets" for r, _ in downs)
    assert any(d == "0018_allow_legacy_kp_presets" or r == "0018_allow_legacy_kp_presets" for r, d in downs)


@pytest.mark.unit
def test_orm_and_schema_default_false():
    # SQLAlchemy column defaults apply on INSERT; helper must treat unset as false.
    assert allow_legacy_kp_presets(Settings()) is False
    assert Settings(allow_legacy_kp_presets=False).allow_legacy_kp_presets is False
    assert SettingsBase().allow_legacy_kp_presets is False
    assert SettingsUpdate().allow_legacy_kp_presets is False
    col_default = Settings.__table__.c.allow_legacy_kp_presets.default
    assert col_default is not None
    assert col_default.arg is False


@pytest.mark.unit
def test_helper_defaults_false_when_absent():
    assert allow_legacy_kp_presets(SimpleNamespace()) is False
    assert allow_legacy_kp_presets(SimpleNamespace(allow_legacy_kp_presets=False)) is False
    assert allow_legacy_kp_presets(SimpleNamespace(allow_legacy_kp_presets=True)) is True
    assert allow_legacy_kp_presets(Settings()) is False


@pytest.mark.unit
def test_settings_read_includes_flag():
    assert "allow_legacy_kp_presets" in SettingsRead.model_fields
    assert SettingsRead.model_fields["allow_legacy_kp_presets"].default is False
    assert allow_legacy_kp_presets(Settings(id=1)) is False


@pytest.mark.unit
def test_presets_410_when_flag_false(kp_client_factory):
    client = kp_client_factory(allow_presets=False)
    list_res = client.get("/api/knowledge-profile/presets")
    assert list_res.status_code == 410
    assert list_res.json()["detail"] == LEGACY_KP_PRESETS_DISABLED_DETAIL
    assert list_res.json()["detail"]["code"] == LEGACY_KP_PRESETS_DISABLED_CODE
    assert list_res.json()["detail"]["message"] == LEGACY_KP_PRESETS_DISABLED_MESSAGE

    load_res = client.post(
        "/api/knowledge-profile/presets/load",
        json={"preset_id": PRESET_ID},
    )
    assert load_res.status_code == 410
    assert load_res.json()["detail"]["code"] == LEGACY_KP_PRESETS_DISABLED_CODE


@pytest.mark.unit
def test_presets_enabled_preserves_behavior(kp_client_factory):
    client = kp_client_factory(allow_presets=True)
    list_res = client.get("/api/knowledge-profile/presets")
    assert list_res.status_code == 200
    ids = {row["id"] for row in list_res.json()}
    assert "generic_corporate" in ids
    assert "bank_financial" in ids

    expected = KnowledgeProfileService.load_preset(PRESET_ID).model_dump(mode="json")
    load_res = client.post(
        "/api/knowledge-profile/presets/load",
        json={"preset_id": PRESET_ID},
    )
    assert load_res.status_code == 200
    assert load_res.json() == expected
    assert load_res.headers.get("Deprecation") == "true"
    assert load_res.headers.get("Link") == KNOWLEDGE_PROFILE_PRESET_LOAD_DEPRECATION_LINK


@pytest.mark.unit
def test_unknown_preset_404_when_enabled(kp_client_factory):
    client = kp_client_factory(allow_presets=True)
    res = client.post(
        "/api/knowledge-profile/presets/load",
        json={"preset_id": "does_not_exist"},
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Preset not found"


@pytest.mark.unit
def test_presets_still_require_auth_when_disabled(monkeypatch):
    _stub_kp_repo(monkeypatch, allow_presets=False)
    app.dependency_overrides.clear()

    def deny():
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Not authenticated")

    app.dependency_overrides[require_authenticated] = deny
    app.dependency_overrides[require_admin] = deny

    def override_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        assert client.get("/api/knowledge-profile/presets").status_code == 401
        assert (
            client.post(
                "/api/knowledge-profile/presets/load",
                json={"preset_id": PRESET_ID},
            ).status_code
            == 401
        )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
def test_empty_profile_fallback_and_presets_dict_unchanged():
    default = KnowledgeProfileService.default_profile()
    generic = PRESETS["generic_corporate"]
    assert default.model_dump() == generic.model_dump()
    assert "bank_financial" in PRESETS
    assert KnowledgeProfileService.load_preset("bank_financial") is not None


@pytest.mark.unit
def test_cache_namespace_excludes_allow_legacy_flag():
    from app.services.cache_namespace_service import build_retrieval_namespace

    s = Settings()
    s.allow_legacy_kp_presets = True
    ns = build_retrieval_namespace(s)
    blob = str(ns)
    assert "allow_legacy_kp_presets" not in blob


@pytest.mark.unit
def test_settings_api_exposes_and_updates_flag(monkeypatch):
    from pydantic_core import PydanticUndefined

    from app.api import settings as settings_api

    stored = Settings(id=1, knowledge_version=1, memory_version=1)
    for name, field in SettingsUpdate.model_fields.items():
        if field.default_factory is not None:
            setattr(stored, name, field.default_factory())
        elif field.default is not PydanticUndefined:
            setattr(stored, name, field.default)
    stored.allow_legacy_kp_presets = False
    stored.allowed_domains_json = "[]"
    stored.deny_url_patterns_json = "[]"
    stored.allowed_file_types_json = "[]"

    class FakeRepo:
        def get_or_create(self):
            return stored

        def save(self, s):
            return s

    monkeypatch.setattr(settings_api, "SettingsRepository", lambda db: FakeRepo())
    monkeypatch.setattr(
        settings_api,
        "CacheInvalidationService",
        lambda db, s: MagicMock(
            invalidate_retrieval_cache=lambda reason: None,
            invalidate_answer_cache=lambda reason: None,
        ),
    )

    app.dependency_overrides[require_admin] = lambda: MagicMock()
    app.dependency_overrides[require_authenticated] = lambda: MagicMock()

    def override_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        get_res = client.get("/api/settings")
        assert get_res.status_code == 200
        assert get_res.json()["allow_legacy_kp_presets"] is False

        put_res = client.put("/api/settings", json={"allow_legacy_kp_presets": True})
        assert put_res.status_code == 200
        assert put_res.json()["allow_legacy_kp_presets"] is True
        assert stored.allow_legacy_kp_presets is True
    finally:
        app.dependency_overrides.clear()
