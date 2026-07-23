"""RFC-100 Step 025 — operational memory_version gauge tests."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.settings import Settings
from app.services.memory_version_service import MemoryVersionService
from app.services.operational_metrics_service import OperationalMetricsService

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
METRICS_SERVICE = APP_ROOT / "services/operational_metrics_service.py"
METRICS_API = APP_ROOT / "api/metrics.py"


def _fake_repo(state: Settings):
    class FakeRepo:
        def get_or_create(self) -> Settings:
            return state

        def save(self, settings: Settings) -> Settings:
            return settings

    return FakeRepo


@pytest.fixture()
def metrics_client(monkeypatch) -> TestClient:
    state = Settings(knowledge_version=11, memory_version=3)

    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )

    def override_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.unit
def test_operational_metrics_json_reports_current_memory_version(metrics_client: TestClient):
    res = metrics_client.get("/api/metrics/operational")
    assert res.status_code == 200
    body = res.json()
    assert body["memory_version"] == 3
    assert body["knowledge_version"] == 11


@pytest.mark.unit
def test_prometheus_metrics_exports_memory_version_gauge(metrics_client: TestClient):
    res = metrics_client.get("/api/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    text = res.text
    assert "# TYPE kos_memory_version gauge" in text
    assert re.search(r"^kos_memory_version 3$", text, re.MULTILINE)
    assert "# TYPE kos_knowledge_version gauge" in text
    assert re.search(r"^kos_knowledge_version 11$", text, re.MULTILINE)


@pytest.mark.unit
def test_bumping_memory_version_changes_exported_value(monkeypatch):
    state = Settings(knowledge_version=5, memory_version=1)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    svc = OperationalMetricsService(db=None)
    assert svc.collect_gauges().memory_version == 1
    MemoryVersionService(db=None).bump()
    assert svc.collect_gauges().memory_version == 2
    assert svc.collect_gauges().knowledge_version == 5


@pytest.mark.unit
def test_knowledge_version_remains_separate_from_memory_version(monkeypatch):
    state = Settings(knowledge_version=99, memory_version=2)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    gauges = OperationalMetricsService(db=None).collect_gauges()
    assert gauges.memory_version == 2
    assert gauges.knowledge_version == 99
    assert gauges.memory_version != gauges.knowledge_version


@pytest.mark.unit
def test_uninitialized_memory_version_reports_one_via_service(monkeypatch):
    state = Settings(knowledge_version=1)
    object.__setattr__(state, "memory_version", None)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    assert OperationalMetricsService(db=None).collect_gauges().memory_version == 1


@pytest.mark.unit
def test_metrics_service_does_not_mutate_memory_version(monkeypatch):
    state = Settings(knowledge_version=1, memory_version=4)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    svc = OperationalMetricsService(db=None)
    for _ in range(5):
        svc.collect_gauges()
        svc.render_prometheus()
    assert state.memory_version == 4
    assert state.knowledge_version == 1


@pytest.mark.unit
def test_metrics_service_uses_version_services_not_direct_settings_reads():
    source = METRICS_SERVICE.read_text(encoding="utf-8")
    assert "MemoryVersionService" in source
    assert "KnowledgeVersionService" in source
    assert "settings.memory_version" not in source
    assert ".bump(" not in source


@pytest.mark.unit
def test_metrics_api_does_not_mutate_versions():
    api_source = METRICS_API.read_text(encoding="utf-8")
    service_source = METRICS_SERVICE.read_text(encoding="utf-8")
    assert ".bump(" not in api_source
    assert ".bump(" not in service_source
    tree = ast.parse(service_source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                name = ast.unparse(target)
                assert "memory_version" not in name
                assert "knowledge_version" not in name
