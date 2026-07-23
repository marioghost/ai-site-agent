"""RFC-100 Step 022 — manual admin memory_version bump API."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.main import app
from app.models.settings import Settings
from app.services.memory_version_service import MemoryVersionService


@pytest.fixture()
def bump_client(monkeypatch) -> TestClient:
    state = Settings(knowledge_version=11, memory_version=2)

    class FakeRepo:
        def get_or_create(self) -> Settings:
            return state

        def save(self, settings: Settings) -> Settings:
            return settings

    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: FakeRepo(),
    )

    def override_admin():
        return MagicMock(role="admin", username="admin")

    def override_db():
        yield MagicMock()

    app.dependency_overrides[require_admin] = override_admin
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.unit
def test_bump_memory_version_requires_auth():
    client = TestClient(app)
    res = client.post("/api/settings/memory-version/bump")
    assert res.status_code == 401


@pytest.mark.unit
def test_bump_memory_version_requires_admin_role():
    viewer = MagicMock(role="viewer", is_active=True, username="viewer")
    app.dependency_overrides[get_current_user] = lambda: viewer
    app.dependency_overrides[get_db] = lambda: iter([MagicMock()])
    try:
        client = TestClient(app)
        res = client.post(
            "/api/settings/memory-version/bump",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
def test_bump_memory_version_increments_by_one(bump_client: TestClient):
    res = bump_client.post("/api/settings/memory-version/bump")
    assert res.status_code == 200
    body = res.json()
    assert body["previous_memory_version"] == 2
    assert body["new_memory_version"] == 3
    assert body["reason"] == "manual_admin_stub"


@pytest.mark.unit
def test_bump_memory_version_accepts_optional_reason(bump_client: TestClient):
    res = bump_client.post(
        "/api/settings/memory-version/bump",
        json={"reason": "pre-release validation"},
    )
    assert res.status_code == 200
    assert res.json()["reason"] == "pre-release validation"


@pytest.mark.unit
def test_repeated_bump_calls_are_monotonic(bump_client: TestClient):
    first = bump_client.post("/api/settings/memory-version/bump").json()
    second = bump_client.post("/api/settings/memory-version/bump").json()
    assert first["new_memory_version"] == 3
    assert second["previous_memory_version"] == 3
    assert second["new_memory_version"] == 4


@pytest.mark.unit
def test_bump_memory_version_uses_memory_version_service(monkeypatch, bump_client: TestClient):
    calls: list[str] = []

    class TrackingService(MemoryVersionService):
        def get(self) -> int:
            calls.append("get")
            return super().get()

        def bump(self) -> int:
            calls.append("bump")
            return super().bump()

    monkeypatch.setattr("app.api.settings.MemoryVersionService", TrackingService)
    res = bump_client.post("/api/settings/memory-version/bump")
    assert res.status_code == 200
    assert calls == ["get", "bump"]


@pytest.mark.unit
def test_bump_memory_version_does_not_change_knowledge_version(bump_client: TestClient, monkeypatch):
    repo = Settings(knowledge_version=11, memory_version=1)

    class FakeRepo:
        def get_or_create(self) -> Settings:
            return repo

        def save(self, settings: Settings) -> Settings:
            return settings

    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: FakeRepo(),
    )
    bump_client.post("/api/settings/memory-version/bump")
    assert repo.knowledge_version == 11
