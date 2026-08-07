"""Cache hygiene: unified invalidation, orphans, SI cleanup, assist bypass, metrics."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.core.concurrency import PerformanceMetrics
from app.models.settings import Settings
from app.services.answer_cache_policy import (
    answer_cache_permitted,
    answer_cache_skip_reason,
)
from app.services.answer_cache_service import AnswerCacheService
from app.services.cache_cleanup_worker import CacheCleanupWorker
from app.services.cache_invalidation_service import CacheInvalidationService
from app.services.cache_namespace_service import build_retrieval_namespace, namespace_hash
from app.services.rag_service import CacheStatusInfo
from app.utils.time_utils import utcnow_naive


def _settings(**overrides) -> Settings:
    s = Settings(
        top_k=5,
        similarity_threshold=0.55,
        qdrant_collection="site",
        embedding_model="bge-m3",
        enable_semantic_answer_cache=True,
        knowledge_version=1,
        cache_namespace_v2_enabled=False,
    )
    for key, value in overrides.items():
        setattr(s, key, value)
    return s


@pytest.mark.unit
def test_invalidate_for_correctness_clears_both_layers():
    db = MagicMock()
    settings = _settings()
    with (
        patch(
            "app.services.cache_invalidation_service.RetrievalCacheService"
        ) as retr_cls,
        patch(
            "app.services.cache_invalidation_service.AnswerCacheService"
        ) as ans_cls,
    ):
        retr_cls.return_value.invalidate_all.return_value = 3
        ans_cls.return_value.invalidate_all.return_value = None
        cleared = CacheInvalidationService(db, settings).invalidate_for_correctness(
            "profile_change"
        )
    assert cleared == 3
    retr_cls.return_value.invalidate_all.assert_called_once()
    ans_cls.return_value.invalidate_all.assert_called_once()


@pytest.mark.unit
def test_answer_lookup_deletes_row_on_namespace_mismatch():
    settings = _settings()
    live_ns = build_retrieval_namespace(settings)
    row = MagicMock()
    row.knowledge_version = 1
    row.namespace_hash = "deadbeef"
    row.expires_at = utcnow_naive() + timedelta(hours=1)
    row.used_context = True
    row.answer_text = "stale"
    row.cache_type = "answer_success"
    row.sources_json = "[]"
    row.vector_id = "orphan-v"

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = row

    svc = AnswerCacheService(db, settings)
    svc.qdrant = MagicMock()
    svc.qdrant.search_ids.return_value = [("orphan-v", 0.99)]

    with patch.object(svc, "_delete_row") as delete_row:
        hit = svc.lookup(
            [0.1, 0.2],
            knowledge_version=1,
            similarity_threshold=0.5,
            namespace=live_ns,
        )
    assert hit is None
    delete_row.assert_called_once_with(row)
    assert namespace_hash(live_ns) != "deadbeef"


@pytest.mark.unit
def test_purge_stale_namespace_deletes_mismatched_only():
    settings = _settings()
    stale = MagicMock(vector_id="old", knowledge_version=1, namespace_hash="stale")
    live = MagicMock(vector_id="live", knowledge_version=1, namespace_hash="current")
    db = MagicMock()
    db.scalars.return_value.all.return_value = [stale, live]

    svc = AnswerCacheService(db, settings)
    svc.qdrant = MagicMock()
    removed = svc.purge_stale_namespace(knowledge_version=1, namespace_hash="current")
    assert removed == 1
    svc.qdrant.delete_points.assert_called_once_with(["old"])
    db.delete.assert_called_once_with(stale)
    db.commit.assert_called()


@pytest.mark.unit
def test_cleanup_worker_targets_si_llm_by_cache_key():
    """Regression: SI LLM PK is cache_key (not id)."""
    import inspect

    from app.models.source_intelligence_llm_cache import SourceIntelligenceLlmCache

    src = inspect.getsource(CacheCleanupWorker.run_once)
    assert "SourceIntelligenceLlmCache" in src
    assert 'pk_attr="cache_key"' in src
    assert hasattr(SourceIntelligenceLlmCache, "cache_key")
    assert not hasattr(SourceIntelligenceLlmCache, "id") or (
        # ORM may inherit id from Base — PK column must be cache_key
        SourceIntelligenceLlmCache.__table__.primary_key.columns.keys() == ["cache_key"]
    )


@pytest.mark.unit
def test_answer_cache_bypassed_when_memory_assist_effective():
    settings = _settings(
        memory_evidence_assist_enabled=True,
        cache_namespace_v2_enabled=True,
    )
    with patch(
        "app.services.answer_cache_policy.memory_assist_effective",
        return_value=True,
    ):
        assert not answer_cache_permitted(
            settings, bypass_cache=False, apply_memory_assist=True
        )
        assert (
            answer_cache_skip_reason(
                settings, bypass_cache=False, apply_memory_assist=True
            )
            == "memory_assist_active"
        )
        assert answer_cache_permitted(
            settings, bypass_cache=False, apply_memory_assist=False
        )


@pytest.mark.unit
def test_metrics_split_answer_and_retrieval():
    m = PerformanceMetrics()
    info = CacheStatusInfo(
        answer_lookup_attempted=True,
        answer_cache_hit=False,
        retrieval_lookup_attempted=True,
        retrieval_cache_hit=True,
    )
    m.record_request_cache(overall_hit=True, cache_info=info)
    assert m.cache_hit_rate() == 1.0
    assert m.answer_cache_hit_rate() == 0.0
    assert m.retrieval_cache_hit_rate() == 1.0

    m.record_request_cache(
        overall_hit=True,
        cache_info=CacheStatusInfo(
            answer_lookup_attempted=True, answer_cache_hit=True
        ),
    )
    assert m.answer_cache_hit_rate() == 0.5


@pytest.mark.unit
def test_boost_fields_excluded_from_namespace():
    a = _settings(title_match_boost=0.15, homepage_boost_enabled=True)
    b = _settings(title_match_boost=0.99, homepage_boost_enabled=False)
    assert (
        build_retrieval_namespace(a)["retrieval_settings_version"]
        == build_retrieval_namespace(b)["retrieval_settings_version"]
    )
    c = _settings(top_k=9)
    assert (
        build_retrieval_namespace(a)["retrieval_settings_version"]
        != build_retrieval_namespace(c)["retrieval_settings_version"]
    )
