"""Tests for safe retrieval/answer cache behavior."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from tests._dbutil import make_engine
from app.models.cache import AnswerCache, RetrievalCache
from app.models.settings import Settings
from app.services.answer_cache_service import AnswerCacheService
from app.services.cache_invalidation_service import CacheInvalidationService
from app.services.cache_namespace_service import build_retrieval_namespace
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.rag_service import RagService
from app.services.retrieval_cache_service import RetrievalCacheService
from app.utils.time_utils import utcnow_naive


@pytest.fixture()
def db_session():
    engine = make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _settings(**overrides) -> Settings:
    s = Settings(
        top_k=5,
        similarity_threshold=0.55,
        qdrant_collection="site",
        embedding_model="bge-m3",
    )
    for key, value in overrides.items():
        setattr(s, key, value)
    return s


def _chunk() -> dict:
    return {
        "score": 0.9,
        "source_id": 1,
        "chunk_index": 0,
        "title": "About",
        "url": "https://example.com/about",
        "source_type": "page",
        "text": "Company overview",
    }


def test_empty_retrieval_not_stored_as_success(db_session):
    settings = _settings()
    namespace = build_retrieval_namespace(settings)
    key = RetrievalCacheService.make_key(
        normalized_query="test",
        namespace=namespace,
        top_k=5,
        similarity_threshold=0.55,
        qdrant_collection="site",
        rerank_enabled=True,
    )
    svc = RetrievalCacheService(db_session)
    svc.store(
        cache_key=key,
        normalized_query="test",
        knowledge_version=1,
        namespace=namespace,
        chunks=[],
        ttl_seconds=3600,
        cache_type="retrieval_success",
    )
    assert db_session.query(RetrievalCache).count() == 0


def test_cached_empty_retrieval_is_ignored_on_read(db_session):
    settings = _settings()
    namespace = build_retrieval_namespace(settings)
    key = RetrievalCacheService.make_key(
        normalized_query="test",
        namespace=namespace,
        top_k=5,
        similarity_threshold=0.55,
        qdrant_collection="site",
        rerank_enabled=True,
    )
    row = RetrievalCache(
        cache_key=key,
        normalized_query="test",
        knowledge_version=1,
        namespace_hash=RetrievalCacheService.namespace_hash(namespace),
        cache_type="retrieval_success",
        selected_chunks_count=0,
        context_used=False,
        retrieved_chunks_json="[]",
        expires_at=utcnow_naive() + timedelta(hours=1),
    )
    db_session.add(row)
    db_session.commit()

    svc = RetrievalCacheService(db_session)
    assert svc.get(key, knowledge_version=1, namespace=namespace) is None
    assert db_session.query(RetrievalCache).count() == 0


def test_successful_retrieval_is_cached(db_session):
    settings = _settings()
    namespace = build_retrieval_namespace(settings)
    key = RetrievalCacheService.make_key(
        normalized_query="about",
        namespace=namespace,
        top_k=5,
        similarity_threshold=0.55,
        qdrant_collection="site",
        rerank_enabled=True,
    )
    svc = RetrievalCacheService(db_session)
    svc.store(
        cache_key=key,
        normalized_query="about",
        knowledge_version=1,
        namespace=namespace,
        chunks=[_chunk()],
        ttl_seconds=3600,
    )
    hit = svc.get(key, knowledge_version=1, namespace=namespace)
    assert hit is not None
    assert hit.cache_type == "retrieval_success"
    assert hit.selected_chunks_count == 1


def test_profile_change_changes_namespace_hash():
    s1 = _settings(knowledge_profile_json="{}")
    s2 = _settings(
        knowledge_profile_json=KnowledgeProfileService.to_json(
            KnowledgeProfileService.load_preset("bank_financial")
        )
    )
    assert build_retrieval_namespace(s1) != build_retrieval_namespace(s2)


def test_retrieval_settings_change_changes_namespace_hash():
    s1 = _settings(top_k=5)
    s2 = _settings(top_k=8)
    assert build_retrieval_namespace(s1)["retrieval_settings_version"] != build_retrieval_namespace(
        s2
    )["retrieval_settings_version"]


def test_bypass_cache_skips_retrieval_lookup(db_session):
    settings = _settings(
        enable_retrieval_cache=True,
        enable_semantic_answer_cache=False,
        fallback_answer="Я не знайшов цієї інформації на сайті.",
    )
    rag = RagService.__new__(RagService)
    rag.db = db_session
    rag.settings = settings
    rag.retrieval_cache = RetrievalCacheService(db_session)
    rag.answer_cache = AnswerCacheService(db_session, settings)
    rag.embedding_service = MagicMock()
    rag.qdrant_service = MagicMock()
    rag.ollama = MagicMock()
    rag.polisher = MagicMock()

    mock_get = MagicMock()
    rag.retrieval_cache.get = mock_get

    with patch(
        "app.services.rag_service.RetrievalPipelineService.run",
        return_value=MagicMock(
            hits=[],
            context=None,
            diagnostics=MagicMock(to_dict=lambda: {}, expanded_queries=[]),
            intent_result=MagicMock(
                legacy_intent="entity_overview",
                matched_topic=None,
                answer_strategy="overview",
            ),
            applied_config=MagicMock(model_dump=lambda: {}),
        ),
    ):
        result = rag.answer(
            "розкажи про банк",
            None,
            request_id="req-1",
            bypass_cache=True,
        )

    mock_get.assert_not_called()
    assert result.cache is not None
    assert result.cache.bypassed is True


def test_fallback_answer_not_cached(db_session):
    settings = _settings(fallback_answer="Я не знайшов цієї інформації на сайті.")
    svc = AnswerCacheService(db_session, settings)
    svc.qdrant = MagicMock()
    svc.qdrant.ensure_collection = MagicMock()
    svc.qdrant.upsert_chunks = MagicMock()
    namespace = build_retrieval_namespace(settings)
    svc.store(
        normalized_query="test",
        query_text="test",
        query_vector=[0.1, 0.2],
        answer_text=settings.fallback_answer,
        sources_json="[]",
        knowledge_version=1,
        ttl_seconds=3600,
        namespace=namespace,
        used_context=False,
        fallback_answer=settings.fallback_answer,
    )
    assert db_session.query(AnswerCache).count() == 0


def test_purge_poisoned_entries(db_session):
    settings = _settings(fallback_answer="Я не знайшов цієї інформації на сайті.")
    db_session.add(
        RetrievalCache(
            cache_key="empty1",
            normalized_query="x",
            knowledge_version=1,
            retrieved_chunks_json="[]",
            selected_chunks_count=0,
            cache_type="retrieval_success",
        )
    )
    db_session.add(
        AnswerCache(
            vector_id="v1",
            normalized_query="x",
            query_text="x",
            answer_text=settings.fallback_answer,
            sources_json="[]",
            used_context=False,
            knowledge_version=1,
        )
    )
    db_session.commit()
    stats = CacheInvalidationService.purge_poisoned_entries(
        db_session, fallback_answer=settings.fallback_answer
    )
    assert stats["retrieval_empty"] >= 1
    assert stats["answer_fallback"] >= 1
    assert db_session.query(RetrievalCache).count() == 0
    assert db_session.query(AnswerCache).count() == 0
