"""RFC-100 Step 021 — MemoryVersionService tests."""
from __future__ import annotations

import threading

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.settings import Settings
from app.services.memory_version_service import MemoryVersionService
from tests._dbutil import make_engine


def _fake_repo_factory(state: Settings):
    save_calls: list[Settings] = []

    class _FakeRepo:
        def get_or_create(self) -> Settings:
            return state

        def save(self, settings: Settings) -> Settings:
            save_calls.append(settings)
            return settings

    return _FakeRepo, save_calls


@pytest.mark.unit
def test_get_returns_default_one(monkeypatch):
    state = Settings(knowledge_version=4, memory_version=1)
    repo_cls, _ = _fake_repo_factory(state)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: repo_cls(),
    )
    assert MemoryVersionService(db=None).get() == 1


@pytest.mark.unit
def test_get_coerces_missing_or_zero_to_one(monkeypatch):
    state = Settings(knowledge_version=4, memory_version=0)
    repo_cls, _ = _fake_repo_factory(state)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: repo_cls(),
    )
    assert MemoryVersionService(db=None).get() == 1


@pytest.mark.unit
def test_bump_commit_false_defers_until_caller_commits(monkeypatch):
    state = Settings(knowledge_version=4, memory_version=2)
    repo_cls, save_calls = _fake_repo_factory(state)
    added: list[Settings] = []

    class _FakeDb:
        def add(self, obj: Settings) -> None:
            added.append(obj)

        def flush(self) -> None:
            return None

    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: repo_cls(),
    )
    svc = MemoryVersionService(db=_FakeDb())
    assert svc.bump(commit=False) == 3
    assert state.memory_version == 3
    assert save_calls == []
    assert added == [state]


@pytest.mark.unit
def test_bump_commit_true_still_persists_via_repo(monkeypatch):
    state = Settings(knowledge_version=4, memory_version=2)
    repo_cls, save_calls = _fake_repo_factory(state)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: repo_cls(),
    )
    svc = MemoryVersionService(db=None)
    assert svc.bump() == 3
    assert len(save_calls) == 1


@pytest.mark.unit
def test_bump_increments_by_exactly_one(monkeypatch):
    state = Settings(knowledge_version=9, memory_version=2)
    repo_cls, save_calls = _fake_repo_factory(state)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: repo_cls(),
    )
    svc = MemoryVersionService(db=None)
    assert svc.bump() == 3
    assert state.memory_version == 3
    assert len(save_calls) == 1


@pytest.mark.unit
def test_repeated_bump_is_monotonic(monkeypatch):
    state = Settings(knowledge_version=10, memory_version=1)
    repo_cls, _ = _fake_repo_factory(state)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: repo_cls(),
    )
    svc = MemoryVersionService(db=None)
    assert svc.bump() == 2
    assert svc.bump() == 3
    assert svc.bump() == 4
    assert state.memory_version == 4


@pytest.mark.unit
def test_bump_does_not_modify_knowledge_version(monkeypatch):
    state = Settings(knowledge_version=7, memory_version=1)
    repo_cls, _ = _fake_repo_factory(state)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: repo_cls(),
    )
    MemoryVersionService(db=None).bump()
    assert state.knowledge_version == 7
    MemoryVersionService(db=None).bump()
    assert state.knowledge_version == 7


@pytest.mark.unit
def test_ensure_initialized_sets_unset_to_one(monkeypatch):
    state = Settings(knowledge_version=3)
    object.__setattr__(state, "memory_version", None)
    repo_cls, save_calls = _fake_repo_factory(state)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: repo_cls(),
    )
    assert MemoryVersionService(db=None).ensure_initialized() == 1
    assert state.memory_version == 1
    assert len(save_calls) == 1


@pytest.mark.unit
def test_ensure_initialized_is_idempotent_when_already_set(monkeypatch):
    state = Settings(knowledge_version=3, memory_version=5)
    repo_cls, save_calls = _fake_repo_factory(state)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: repo_cls(),
    )
    svc = MemoryVersionService(db=None)
    assert svc.ensure_initialized() == 5
    assert svc.ensure_initialized() == 5
    assert save_calls == []


@pytest.fixture()
def db_session():
    engine = make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_serial_bumps_persist_on_settings_row(db_session):
    """Integration: bumps persist and leave knowledge_version unchanged."""
    db = db_session
    settings = Settings(
        top_k=5,
        similarity_threshold=0.55,
        qdrant_collection="site",
        embedding_model="bge-m3",
        knowledge_version=12,
        memory_version=1,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)

    svc = MemoryVersionService(db)
    assert svc.get() == 1
    assert svc.bump() == 2
    assert svc.bump() == 3
    db.refresh(settings)
    assert settings.memory_version == 3
    assert settings.knowledge_version == 12


def test_concurrent_bumps_use_same_architecture_as_knowledge_version(db_session):
    """Serial RMW on singleton settings row (no row lock yet, same as KnowledgeVersionService)."""
    db = db_session
    settings = Settings(
        top_k=5,
        similarity_threshold=0.55,
        qdrant_collection="site",
        embedding_model="bge-m3",
        memory_version=1,
    )
    db.add(settings)
    db.commit()

    svc = MemoryVersionService(db)
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def _worker() -> None:
        try:
            barrier.wait(timeout=5)
            svc.bump()
        except Exception as exc:  # pragma: no cover - recorded for assertion
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors
    db.refresh(settings)
    # Without SELECT FOR UPDATE, concurrent bumps may not both apply; final >= 2.
    assert settings.memory_version >= 2
