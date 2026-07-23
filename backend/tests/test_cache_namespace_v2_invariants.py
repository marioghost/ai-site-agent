"""RFC-100 Step 024 — Cache Namespace v2 architectural invariant tests.

Validates that cache invalidation is driven by namespace evolution only.
No production behavior changes — tests and documentation only.
"""
from __future__ import annotations

import ast
import itertools
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models.settings import Settings
from app.services.cache_namespace_service import (
    build_retrieval_namespace,
    namespace_hash,
)
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.memory_version_service import MemoryVersionService
from app.services.retrieval_cache_service import RetrievalCacheService

BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT / "app"

CACHE_SERVICE_FILES = (
    "services/answer_cache_service.py",
    "services/retrieval_cache_service.py",
    "services/cache_invalidation_service.py",
    "services/cache_namespace_service.py",
    "services/cache_cleanup_worker.py",
)

# Modules allowed to reference settings.memory_version directly.
MEMORY_VERSION_DIRECT_ACCESS_ALLOWLIST = frozenset(
    {
        "services/memory_version_service.py",
        "models/settings.py",
        "schemas/settings.py",
        "api/settings.py",
    }
)

RETRIEVAL_KEY_BASE = dict(
    normalized_query="яка комісія",
    top_k=5,
    similarity_threshold=0.55,
    qdrant_collection="site",
    rerank_enabled=True,
)


def _settings(**overrides) -> Settings:
    settings = Settings(
        knowledge_version=1,
        embedding_model="bge-m3",
        qdrant_collection="site",
        llm_model="test-model",
    )
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _fake_repo(state: Settings):
    class FakeRepo:
        def get_or_create(self) -> Settings:
            return state

        def save(self, settings: Settings) -> Settings:
            return settings

    return FakeRepo()


# --- Invariant 1: flag OFF, memory change → namespace identical ---


@pytest.mark.unit
def test_invariant_flag_off_memory_change_namespace_identical():
    baseline = _settings(memory_version=1)
    bumped_row = _settings(memory_version=99)
    assert build_retrieval_namespace(baseline) == build_retrieval_namespace(bumped_row)


# --- Invariant 2: flag ON, memory change → namespace changes ---


@pytest.mark.unit
def test_invariant_flag_on_memory_change_namespace_differs(monkeypatch):
    settings = _settings(cache_namespace_v2_enabled=True)
    db = MagicMock()
    versions = iter([1, 5])
    monkeypatch.setattr(
        "app.services.cache_namespace_service.MemoryVersionService",
        lambda session: MagicMock(get=lambda: next(versions)),
    )
    ns_before = build_retrieval_namespace(settings, db=db)
    ns_after = build_retrieval_namespace(settings, db=db)
    assert ns_before != ns_after
    assert namespace_hash(ns_before) != namespace_hash(ns_after)


# --- Invariant 3: knowledge_version changes preserve existing namespace behavior ---


@pytest.mark.unit
def test_invariant_knowledge_version_changes_index_version(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(
        "app.services.cache_namespace_service.MemoryVersionService",
        lambda session: MagicMock(get=lambda: 1),
    )
    ns_v3 = build_retrieval_namespace(
        _settings(knowledge_version=3, cache_namespace_v2_enabled=True),
        db=db,
    )
    ns_v8 = build_retrieval_namespace(
        _settings(knowledge_version=8, cache_namespace_v2_enabled=True),
        db=db,
    )
    assert ns_v3["index_version"] == "3"
    assert ns_v8["index_version"] == "8"
    assert namespace_hash(ns_v3) != namespace_hash(ns_v8)


@pytest.mark.unit
def test_invariant_knowledge_version_only_affects_index_version_key():
    ns1 = build_retrieval_namespace(_settings(knowledge_version=2))
    ns2 = build_retrieval_namespace(_settings(knowledge_version=9))
    diff_keys = {k for k in ns1 if ns1[k] != ns2[k]}
    assert diff_keys == {"index_version"}


# --- Invariant 4: memory bump never mutates knowledge_version ---


@pytest.mark.unit
def test_invariant_memory_bump_preserves_knowledge_version(monkeypatch):
    state = Settings(knowledge_version=42, memory_version=1)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: _fake_repo(state),
    )
    svc = MemoryVersionService(db=None)
    svc.bump()
    svc.bump()
    assert state.knowledge_version == 42
    assert state.memory_version == 3


# --- Invariant 5: knowledge bump never mutates memory_version ---


@pytest.mark.unit
def test_invariant_knowledge_bump_preserves_memory_version(monkeypatch):
    state = Settings(knowledge_version=1, memory_version=7)
    monkeypatch.setattr(
        "app.services.knowledge_version_service.SettingsRepository",
        lambda db: _fake_repo(state),
    )
    svc = KnowledgeVersionService(db=None)
    svc.bump()
    svc.bump()
    assert state.memory_version == 7
    assert state.knowledge_version == 3


# --- Invariant 6: identical namespace → identical cache keys ---


@pytest.mark.unit
def test_invariant_identical_namespace_produces_identical_cache_keys():
    ns = build_retrieval_namespace(_settings())
    key_a = RetrievalCacheService.make_key(namespace=ns, **RETRIEVAL_KEY_BASE)
    key_b = RetrievalCacheService.make_key(namespace=ns, **RETRIEVAL_KEY_BASE)
    assert key_a == key_b
    assert len(key_a) == 64


@pytest.mark.unit
def test_invariant_repeated_namespace_reads_produce_identical_keys(monkeypatch):
    settings = _settings(cache_namespace_v2_enabled=True)
    db = MagicMock()
    monkeypatch.setattr(
        "app.services.cache_namespace_service.MemoryVersionService",
        lambda session: MagicMock(get=lambda: 4),
    )
    keys = [
        RetrievalCacheService.make_key(
            namespace=build_retrieval_namespace(settings, db=db),
            **RETRIEVAL_KEY_BASE,
        )
        for _ in range(5)
    ]
    assert len(set(keys)) == 1


# --- Invariant 7: namespace generation is deterministic ---


@pytest.mark.unit
def test_invariant_namespace_generation_is_deterministic():
    settings = _settings(knowledge_version=5, top_k=7)
    first = build_retrieval_namespace(settings)
    second = build_retrieval_namespace(settings)
    assert first == second
    assert namespace_hash(first) == namespace_hash(second)


@pytest.mark.unit
@pytest.mark.parametrize(
    "knowledge_version,top_k,memory_version,flag_on",
    list(
        itertools.product(
            [1, 3, 10],
            [3, 5, 8],
            [1, 2, 4],
            [False, True],
        )
    ),
)
def test_property_namespace_hash_is_deterministic_for_inputs(
    monkeypatch,
    knowledge_version: int,
    top_k: int,
    memory_version: int,
    flag_on: bool,
):
    settings = _settings(
        knowledge_version=knowledge_version,
        top_k=top_k,
        memory_version=memory_version,
        cache_namespace_v2_enabled=flag_on,
    )
    db = MagicMock()
    monkeypatch.setattr(
        "app.services.cache_namespace_service.MemoryVersionService",
        lambda session: MagicMock(get=lambda: memory_version),
    )
    kwargs = {"db": db} if flag_on else {}
    runs = [build_retrieval_namespace(settings, **kwargs) for _ in range(3)]
    hashes = [namespace_hash(ns) for ns in runs]
    assert len(set(hashes)) == 1
    assert all(r == runs[0] for r in runs)


@pytest.mark.unit
def test_property_flag_off_hash_independent_of_memory_version_on_row():
    hashes = {
        namespace_hash(
            build_retrieval_namespace(_settings(memory_version=mv))
        )
        for mv in range(1, 12)
    }
    assert len(hashes) == 1


# --- Negative tests: cache layer is version-aware, not memory-aware ---


@pytest.mark.unit
def test_negative_cache_modules_do_not_call_bump():
    for rel_path in CACHE_SERVICE_FILES:
        source = (APP_ROOT / rel_path).read_text(encoding="utf-8")
        assert ".bump(" not in source, f"{rel_path} must not call bump()"


@pytest.mark.unit
def test_negative_cache_modules_except_namespace_do_not_import_memory_version_service():
    for rel_path in CACHE_SERVICE_FILES:
        if rel_path.endswith("cache_namespace_service.py"):
            continue
        source = (APP_ROOT / rel_path).read_text(encoding="utf-8")
        assert "MemoryVersionService" not in source, (
            f"{rel_path} must not import MemoryVersionService"
        )
        assert "memory_version" not in source, (
            f"{rel_path} must not reference memory_version"
        )


@pytest.mark.unit
def test_negative_namespace_service_reads_memory_via_service_get_only():
    source = (APP_ROOT / "services/cache_namespace_service.py").read_text(
        encoding="utf-8"
    )
    assert "MemoryVersionService(db).get()" in source
    assert "settings.memory_version" not in source
    assert ".bump(" not in source


@pytest.mark.unit
def test_negative_no_direct_memory_version_reads_outside_allowlist():
    violations: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        rel = path.relative_to(APP_ROOT).as_posix()
        if rel.startswith("migrations/"):
            continue
        if rel in MEMORY_VERSION_DIRECT_ACCESS_ALLOWLIST:
            continue
        source = path.read_text(encoding="utf-8")
        if "settings.memory_version" in source:
            violations.append(f"{rel}: settings.memory_version")
        if 'getattr(settings, "memory_version"' in source:
            violations.append(f'{rel}: getattr(settings, "memory_version"')
        if "getattr(model, \"memory_version\"" in source:
            violations.append(rel)
    assert violations == []


@pytest.mark.unit
def test_negative_cache_modules_do_not_mutate_version_columns():
    """Cache services compare/store knowledge_version; they must not increment it."""
    for rel_path in CACHE_SERVICE_FILES:
        tree = ast.parse((APP_ROOT / rel_path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.AugAssign):
                target = ast.unparse(node.target)
                assert "knowledge_version" not in target, rel_path
                assert "memory_version" not in target, rel_path
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    name = ast.unparse(target)
                    if "knowledge_version" in name and isinstance(node.value, ast.BinOp):
                        pytest.fail(f"{rel_path} performs knowledge_version arithmetic")
                    if name in {"settings.memory_version", "row.memory_version"} or (
                        name.endswith(".memory_version")
                        and "namespace" not in name
                    ):
                        pytest.fail(f"{rel_path} assigns settings/row memory_version")


@pytest.mark.unit
def test_negative_retrieval_cache_get_is_read_only_on_versions():
    """Retrieval cache invalidates by comparing passed-in versions; no bump side effects."""
    source = (APP_ROOT / "services/retrieval_cache_service.py").read_text(
        encoding="utf-8"
    )
    assert "KnowledgeVersionService" not in source
    assert "MemoryVersionService" not in source
    assert "knowledge_version !=" in source or "row.knowledge_version" in source


@pytest.mark.unit
def test_negative_answer_cache_lookup_is_read_only_on_versions():
    source = (APP_ROOT / "services/answer_cache_service.py").read_text(encoding="utf-8")
    assert "KnowledgeVersionService" not in source
    assert "MemoryVersionService" not in source
    assert "row.knowledge_version" in source
