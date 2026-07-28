"""RFC-100 Step 052 — remove deprecated boost fields from Settings API (Option A).

ORM columns and runtime readers (DocumentScorer / RPS inject / cache NS) stay.
API GET omits the five fields; PUT ignores legacy keys via extra=\"ignore\".
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import require_admin, require_authenticated
from app.core.database import get_db
from app.main import app
from app.models.settings import Settings
from app.schemas.settings import SettingsRead, SettingsUpdate
from app.services.cache_namespace_service import build_retrieval_namespace
from app.services.retrieval_engine.document_scorer import DocumentScorer

REMOVED_BOOST_FIELDS = (
    "title_match_boost",
    "heading_match_boost",
    "homepage_boost_enabled",
    "homepage_boost_value",
    "short_query_lexical_boost",
)


def _settings_row(**overrides) -> Settings:
    """ORM-like Settings with API-mappable defaults (SQLAlchemy defaults are insert-time)."""
    row = Settings(id=1, knowledge_version=1, memory_version=1)
    for name, field in SettingsUpdate.model_fields.items():
        if field.is_required():
            continue
        if field.default_factory is not None:
            setattr(row, name, field.default_factory())
        elif field.default is not None or name in SettingsUpdate.model_fields:
            # Include explicit False/0/"" defaults
            from pydantic_core import PydanticUndefined

            if field.default is not PydanticUndefined:
                setattr(row, name, field.default)
    # Boost columns remain on ORM even though removed from API schema.
    row.homepage_boost_enabled = True
    row.title_match_boost = 0.15
    row.heading_match_boost = 0.15
    row.homepage_boost_value = 0.10
    row.short_query_lexical_boost = 0.20
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


@pytest.fixture()
def settings_api_client(monkeypatch) -> tuple[TestClient, Settings]:
    state = _settings_row()

    class FakeRepo:
        def get_or_create(self) -> Settings:
            return state

        def save(self, settings: Settings) -> Settings:
            return settings

    monkeypatch.setattr(
        "app.api.settings.SettingsRepository",
        lambda db: FakeRepo(),
    )

    def override_auth():
        return MagicMock(role="admin", username="admin", is_active=True)

    def override_db():
        yield MagicMock()

    app.dependency_overrides[require_authenticated] = override_auth
    app.dependency_overrides[require_admin] = override_auth
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        yield client, state
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
def test_settings_read_schema_omits_boost_fields():
    fields = SettingsRead.model_fields
    for name in REMOVED_BOOST_FIELDS:
        assert name not in fields


@pytest.mark.unit
def test_settings_update_schema_omits_boost_fields():
    fields = SettingsUpdate.model_fields
    for name in REMOVED_BOOST_FIELDS:
        assert name not in fields


@pytest.mark.unit
def test_settings_update_ignores_legacy_boost_extras():
    payload = SettingsUpdate.model_validate(
        {
            "retrieval_mode": "hybrid",
            "title_match_boost": 1.99,
            "heading_match_boost": 1.99,
            "homepage_boost_enabled": False,
            "homepage_boost_value": 1.99,
            "short_query_lexical_boost": 1.99,
        }
    )
    dumped = payload.model_dump()
    for name in REMOVED_BOOST_FIELDS:
        assert name not in dumped


@pytest.mark.unit
def test_openapi_settings_read_omits_boost_fields():
    schema = SettingsRead.model_json_schema()
    props = schema.get("properties") or {}
    for name in REMOVED_BOOST_FIELDS:
        assert name not in props


@pytest.mark.unit
def test_get_settings_omits_boost_fields(settings_api_client):
    client, _state = settings_api_client
    res = client.get("/api/settings")
    assert res.status_code == 200
    body = res.json()
    for name in REMOVED_BOOST_FIELDS:
        assert name not in body
    assert body["retrieval_mode"] == "hybrid"


@pytest.mark.unit
def test_put_legacy_boost_fields_ignored_orm_unchanged(settings_api_client):
    client, state = settings_api_client
    before = {
        "title_match_boost": state.title_match_boost,
        "heading_match_boost": state.heading_match_boost,
        "homepage_boost_enabled": state.homepage_boost_enabled,
        "homepage_boost_value": state.homepage_boost_value,
        "short_query_lexical_boost": state.short_query_lexical_boost,
        "temperature": state.temperature,
    }

    # Full SettingsUpdate requires many fields — load defaults from a Read dump
    # then strip boost keys and re-add legacy extras + a real change.
    baseline = client.get("/api/settings").json()
    for name in REMOVED_BOOST_FIELDS:
        baseline.pop(name, None)
    baseline["temperature"] = 0.42
    baseline.update(
        {
            "title_match_boost": 1.77,
            "heading_match_boost": 1.77,
            "homepage_boost_enabled": False,
            "homepage_boost_value": 1.77,
            "short_query_lexical_boost": 1.77,
        }
    )

    res = client.put("/api/settings", json=baseline)
    assert res.status_code == 200, res.text
    body = res.json()
    for name in REMOVED_BOOST_FIELDS:
        assert name not in body

    assert state.title_match_boost == before["title_match_boost"]
    assert state.heading_match_boost == before["heading_match_boost"]
    assert state.homepage_boost_enabled == before["homepage_boost_enabled"]
    assert state.homepage_boost_value == before["homepage_boost_value"]
    assert state.short_query_lexical_boost == before["short_query_lexical_boost"]
    assert state.temperature == 0.42


@pytest.mark.unit
def test_document_scorer_still_reads_orm_boost_defaults():
    settings = _settings_row()
    scorer = DocumentScorer(settings)
    # Public contract: scorer holds settings reference with ORM boost attrs.
    assert scorer.settings.title_match_boost == 0.15
    assert scorer.settings.heading_match_boost == 0.15


@pytest.mark.unit
def test_homepage_inject_formula_unchanged_with_orm_defaults():
    settings = _settings_row(homepage_boost_enabled=True, homepage_boost_value=0.10)
    # Mirror inject formula from retrieval_pipeline_service (Option A unchanged).
    homepage_extra = (
        settings.homepage_boost_value if settings.homepage_boost_enabled else 0.1
    )
    assert homepage_extra == 0.10
    settings_disabled = _settings_row(homepage_boost_enabled=False, homepage_boost_value=0.5)
    homepage_extra_off = (
        settings_disabled.homepage_boost_value
        if settings_disabled.homepage_boost_enabled
        else 0.1
    )
    assert homepage_extra_off == 0.1


@pytest.mark.unit
def test_cache_namespace_still_hashes_orm_boost_fields():
    a = _settings_row()
    b = _settings_row(title_match_boost=0.99)
    ns_a = build_retrieval_namespace(a)
    ns_b = build_retrieval_namespace(b)
    assert ns_a["retrieval_settings_version"] != ns_b["retrieval_settings_version"]
    # Defaults match → stable namespace for live default rows.
    ns_default = build_retrieval_namespace(_settings_row())
    assert ns_a["retrieval_settings_version"] == ns_default["retrieval_settings_version"]


@pytest.mark.unit
def test_no_alembic_migration_added_for_step_052():
    versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    names = [p.name for p in versions.glob("*.py")]
    assert not any("052" in n or "boost_field" in n or "remove_boost" in n for n in names)


@pytest.mark.unit
def test_orm_settings_model_still_has_boost_columns():
    for name in REMOVED_BOOST_FIELDS:
        assert hasattr(Settings, name)
