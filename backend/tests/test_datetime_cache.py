"""Datetime-safe cache lookups and repeated-query behavior."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import app
from tests._dbutil import make_engine
from app.models.cache import AnswerCache, RetrievalCache
from app.models.settings import Settings
from app.services.answer_cache_service import AnswerCacheService
from app.services.cache_namespace_service import build_retrieval_namespace
from app.services.retrieval_cache_service import RetrievalCacheService
from app.utils.time_utils import is_expired, to_naive_utc, utcnow_naive


@pytest.fixture()
def db_session():
    engine = make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _sample_chunks() -> list[dict]:
    return [
        {
            "score": 0.9,
            "source_id": 1,
            "chunk_index": 0,
            "title": "Page",
            "url": "https://example.com",
            "source_type": "page",
            "text": "укрсиббанк",
        }
    ]


def _namespace() -> dict[str, str]:
    settings = Settings()
    return build_retrieval_namespace(settings)


def _cache_key(namespace: dict[str, str] | None = None) -> str:
    namespace = namespace or _namespace()
    return RetrievalCacheService.make_key(
        normalized_query="укрсиббанк",
        namespace=namespace,
        top_k=5,
        similarity_threshold=0.55,
        qdrant_collection="site",
        rerank_enabled=True,
    )


def test_is_expired_handles_naive_and_aware():
    past_naive = utcnow_naive() - timedelta(hours=1)
    future_aware = datetime.now(timezone.utc) + timedelta(hours=1)
    assert is_expired(past_naive) is True
    assert is_expired(future_aware) is False
    assert is_expired(None) is False


def test_to_naive_utc_strips_tzinfo():
    aware = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    naive = to_naive_utc(aware)
    assert naive is not None
    assert naive.tzinfo is None
    assert naive.hour == 12


def test_retrieval_cache_hit_with_naive_expires_at(db_session):
    key = _cache_key()
    namespace = _namespace()
    service = RetrievalCacheService(db_session)
    service.store(
        cache_key=key,
        normalized_query="укрсиббанк",
        knowledge_version=1,
        namespace=namespace,
        chunks=_sample_chunks(),
        ttl_seconds=3600,
        cache_type="retrieval_success",
    )
    row = db_session.get(RetrievalCache, 1)
    assert row is not None
    assert row.expires_at.tzinfo is None

    result = service.get(key, knowledge_version=1, namespace=namespace)
    assert result is not None
    assert result.chunks == _sample_chunks()


def test_retrieval_cache_hit_with_aware_expires_at(db_session):
    key = _cache_key()
    namespace = _namespace()
    future_aware = datetime.now(timezone.utc) + timedelta(hours=1)
    row = RetrievalCache(
        cache_key=key,
        normalized_query="укрсиббанк",
        knowledge_version=1,
        namespace_hash=RetrievalCacheService.namespace_hash(namespace),
        cache_type="retrieval_success",
        selected_chunks_count=1,
        context_used=True,
        retrieved_chunks_json='[{"text": "cached", "score": 0.9, "source_id": 1, "chunk_index": 0, "title": "P", "url": "https://x", "source_type": "page"}]',
        expires_at=future_aware,
    )
    db_session.add(row)
    db_session.commit()

    service = RetrievalCacheService(db_session)
    result = service.get(key, knowledge_version=1, namespace=namespace)
    assert result is not None
    assert result.chunks == [
        {
            "text": "cached",
            "score": 0.9,
            "source_id": 1,
            "chunk_index": 0,
            "title": "P",
            "url": "https://x",
            "source_type": "page",
        }
    ]


def test_retrieval_cache_expired_returns_miss(db_session):
    key = _cache_key()
    past_naive = utcnow_naive() - timedelta(minutes=5)
    row = RetrievalCache(
        cache_key=key,
        normalized_query="укрсиббанк",
        knowledge_version=1,
        retrieved_chunks_json='[{"text": "stale"}]',
        expires_at=past_naive,
    )
    db_session.add(row)
    db_session.commit()

    service = RetrievalCacheService(db_session)
    assert service.get(key, knowledge_version=1, namespace=_namespace()) is None
    assert db_session.get(RetrievalCache, row.id) is None


def test_retrieval_cache_invalid_json_returns_miss(db_session):
    key = _cache_key()
    row = RetrievalCache(
        cache_key=key,
        normalized_query="укрсиббанк",
        knowledge_version=1,
        retrieved_chunks_json="not-json",
        expires_at=utcnow_naive() + timedelta(hours=1),
    )
    db_session.add(row)
    db_session.commit()

    service = RetrievalCacheService(db_session)
    assert service.get(key, knowledge_version=1, namespace=_namespace()) is None


def test_answer_cache_lookup_with_mixed_expires_at(db_session):
    settings = Settings(qdrant_collection="test")
    service = AnswerCacheService(db_session, settings)

    future_aware = datetime.now(timezone.utc) + timedelta(hours=1)
    row = AnswerCache(
        vector_id="vec-1",
        normalized_query="укрсиббанк",
        query_text="укрсиббанк",
        answer_text="cached answer",
        sources_json="[]",
        knowledge_version=1,
        expires_at=future_aware,
    )
    db_session.add(row)
    db_session.commit()

    service.qdrant = MagicMock()
    service.qdrant.search_ids.return_value = [("vec-1", 0.99)]

    hit = service.lookup([0.1], knowledge_version=1, similarity_threshold=0.9)
    assert hit is not None
    assert hit.answer_text == "cached answer"


def test_answer_cache_expired_purged_on_lookup(db_session):
    settings = Settings(qdrant_collection="test")
    service = AnswerCacheService(db_session, settings)

    past_naive = utcnow_naive() - timedelta(minutes=1)
    row = AnswerCache(
        vector_id="vec-expired",
        normalized_query="укрсиббанк",
        query_text="укрсиббанк",
        answer_text="old",
        sources_json="[]",
        knowledge_version=1,
        expires_at=past_naive,
    )
    db_session.add(row)
    db_session.commit()

    service.qdrant = MagicMock()
    service.qdrant.search_ids.return_value = [("vec-expired", 0.99)]

    assert service.lookup([0.1], knowledge_version=1, similarity_threshold=0.9) is None
    service.qdrant.delete_points.assert_called_once_with(["vec-expired"])


def test_answer_cache_purge_expired(db_session):
    settings = Settings(qdrant_collection="test")
    service = AnswerCacheService(db_session, settings)
    service.qdrant = MagicMock()

    past = utcnow_naive() - timedelta(hours=1)
    future = utcnow_naive() + timedelta(hours=1)
    db_session.add_all(
        [
            AnswerCache(
                vector_id="old",
                normalized_query="a",
                query_text="a",
                answer_text="a",
                sources_json="[]",
                knowledge_version=1,
                expires_at=past,
            ),
            AnswerCache(
                vector_id="fresh",
                normalized_query="b",
                query_text="b",
                answer_text="b",
                sources_json="[]",
                knowledge_version=1,
                expires_at=future,
            ),
        ]
    )
    db_session.commit()

    removed = service.purge_expired()
    assert removed == 1
    remaining = db_session.query(AnswerCache).all()
    assert len(remaining) == 1
    assert remaining[0].vector_id == "fresh"


def test_repeated_chat_request_returns_cache_hit(monkeypatch, client, auth_headers):
    """Second identical chat call must not 500 and should report cache_hit."""
    from app.services import rag_service as rag_module

    call_count = {"n": 0}

    class _FakeRag:
        def answer(self, message, session_id, **kwargs):
            call_count["n"] += 1
            cache_hit = call_count["n"] > 1
            return rag_module.RagResult(
                answer="Відповідь про Укрсиббанк",
                sources=[],
                used_context=True,
                request_id=kwargs.get("request_id", "req"),
                cache_hit=cache_hit,
                cache_type="retrieval" if cache_hit else "none",
            )

    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeRag()
    )
    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: True
    )

    sid = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]
    payload = {"message": "укрсиббанк", "session_id": sid}

    first = client.post("/api/chat", json=payload)
    assert first.status_code == 200
    assert first.json()["cache_hit"] is False

    second = client.post("/api/chat", json=payload)
    assert second.status_code == 200
    assert second.json()["cache_hit"] is True
