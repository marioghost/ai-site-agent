"""RFC-100 Step 023 — cache namespace v2 (memory_version in namespace when flag ON)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.models.settings import Settings
from app.services.cache_namespace_service import (
    build_retrieval_namespace,
    namespace_hash,
)
from app.services.memory_version_service import MemoryVersionService
from app.services.retrieval_cache_service import RetrievalCacheService


def _baseline_settings(**overrides) -> Settings:
    settings = Settings(
        knowledge_version=1,
        embedding_model="bge-m3",
        qdrant_collection="site",
        llm_model="test-model",
    )
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


@pytest.mark.unit
def test_flag_off_namespace_unchanged_when_memory_version_differs():
    """Flag OFF: memory_version on settings row must not affect namespace or cache keys."""
    baseline = _baseline_settings()
    with_memory = _baseline_settings(memory_version=99)
    assert build_retrieval_namespace(baseline) == build_retrieval_namespace(with_memory)
    assert "memory_version" not in build_retrieval_namespace(baseline)


@pytest.mark.unit
def test_flag_off_namespace_matches_legacy_snapshot():
    """Flag OFF: namespace keys and index_version behavior unchanged from pre-023."""
    ns = build_retrieval_namespace(_baseline_settings(knowledge_version=7))
    assert ns["index_version"] == "7"
    assert set(ns.keys()) == {
        "index_version",
        "knowledge_profile_version",
        "retrieval_settings_version",
        "embedding_model",
        "collection_name",
        "source_intelligence_version",
        "prompt_template_version",
        "context_builder_version",
        "llm_model",
        "speech_act_language",
        "memory_evidence_assist",
        "document_type_rules_version",
        "content_hint_rules_version",
        "source_priority_rules_version",
        "query_expansion_version",
    }
    assert ns["speech_act_language"] == "off"


@pytest.mark.unit
def test_flag_on_includes_memory_version_via_service(monkeypatch):
    settings = _baseline_settings(cache_namespace_v2_enabled=True)
    db = MagicMock()
    calls: list[str] = []

    class TrackingService(MemoryVersionService):
        def get(self) -> int:
            calls.append("get")
            return 3

    monkeypatch.setattr(
        "app.services.cache_namespace_service.MemoryVersionService",
        lambda session: TrackingService(session),
    )
    ns = build_retrieval_namespace(settings, db=db)
    assert ns["memory_version"] == "3"
    assert calls == ["get"]


@pytest.mark.unit
def test_flag_on_namespace_changes_when_memory_version_changes(monkeypatch):
    settings = _baseline_settings(cache_namespace_v2_enabled=True)
    db = MagicMock()
    versions = iter([1, 2])

    monkeypatch.setattr(
        "app.services.cache_namespace_service.MemoryVersionService",
        lambda session: MagicMock(get=lambda: next(versions)),
    )
    ns1 = build_retrieval_namespace(settings, db=db)
    ns2 = build_retrieval_namespace(settings, db=db)
    assert ns1["memory_version"] == "1"
    assert ns2["memory_version"] == "2"
    assert namespace_hash(ns1) != namespace_hash(ns2)


@pytest.mark.unit
def test_flag_on_requires_db_session():
    settings = _baseline_settings(cache_namespace_v2_enabled=True)
    with pytest.raises(ValueError, match="db session is required"):
        build_retrieval_namespace(settings)


@pytest.mark.unit
def test_knowledge_version_behavior_unchanged_when_flag_on(monkeypatch):
    settings_v1 = _baseline_settings(
        cache_namespace_v2_enabled=True,
        knowledge_version=1,
    )
    settings_v2 = _baseline_settings(
        cache_namespace_v2_enabled=True,
        knowledge_version=2,
    )
    db = MagicMock()
    monkeypatch.setattr(
        "app.services.cache_namespace_service.MemoryVersionService",
        lambda session: MagicMock(get=lambda: 1),
    )
    ns1 = build_retrieval_namespace(settings_v1, db=db)
    ns2 = build_retrieval_namespace(settings_v2, db=db)
    assert ns1["index_version"] == "1"
    assert ns2["index_version"] == "2"
    assert ns1["memory_version"] == ns2["memory_version"] == "1"
    assert ns1["index_version"] != ns2["index_version"]


@pytest.mark.unit
def test_retrieval_cache_key_unchanged_when_flag_off():
    base = dict(
        normalized_query="яка комісія",
        top_k=5,
        similarity_threshold=0.55,
        qdrant_collection="site",
        rerank_enabled=True,
    )
    ns = build_retrieval_namespace(_baseline_settings())
    key = RetrievalCacheService.make_key(namespace=ns, **base)
    key_with_memory_on_row = RetrievalCacheService.make_key(
        namespace=build_retrieval_namespace(_baseline_settings(memory_version=50)),
        **base,
    )
    assert key == key_with_memory_on_row


@pytest.mark.unit
def test_retrieval_cache_key_changes_when_flag_on_and_memory_version_changes(monkeypatch):
    base = dict(
        normalized_query="яка комісія",
        top_k=5,
        similarity_threshold=0.55,
        qdrant_collection="site",
        rerank_enabled=True,
    )
    settings = _baseline_settings(cache_namespace_v2_enabled=True)
    db = MagicMock()
    versions = iter([1, 2])
    monkeypatch.setattr(
        "app.services.cache_namespace_service.MemoryVersionService",
        lambda session: MagicMock(get=lambda: next(versions)),
    )
    key1 = RetrievalCacheService.make_key(
        namespace=build_retrieval_namespace(settings, db=db),
        **base,
    )
    key2 = RetrievalCacheService.make_key(
        namespace=build_retrieval_namespace(settings, db=db),
        **base,
    )
    assert key1 != key2


@pytest.mark.unit
def test_answer_cache_namespace_hash_unchanged_when_flag_off():
    ns = build_retrieval_namespace(_baseline_settings())
    ns_with_memory = build_retrieval_namespace(_baseline_settings(memory_version=42))
    assert namespace_hash(ns) == namespace_hash(ns_with_memory)


@pytest.mark.unit
def test_answer_cache_namespace_hash_changes_when_flag_on(monkeypatch):
    settings = _baseline_settings(cache_namespace_v2_enabled=True)
    db = MagicMock()
    versions = iter([1, 2])
    monkeypatch.setattr(
        "app.services.cache_namespace_service.MemoryVersionService",
        lambda session: MagicMock(get=lambda: next(versions)),
    )
    h1 = namespace_hash(build_retrieval_namespace(settings, db=db))
    h2 = namespace_hash(build_retrieval_namespace(settings, db=db))
    assert h1 != h2
