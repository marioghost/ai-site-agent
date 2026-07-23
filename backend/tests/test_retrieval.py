"""Tests for retrieval threshold + no-hallucination fallback logic."""
from __future__ import annotations

import pytest

from app.models.settings import Settings
from app.services.qdrant_service import SearchHit
from app.services.retrieval_service import RetrievalService


class _FakeEmbedding:
    def embed_query(self, text: str):
        return [0.1, 0.2, 0.3]


class _FakeQdrant:
    def __init__(self, hits):
        self._hits = hits

    def search(self, vector, top_k):
        return self._hits[:top_k]


def _hit(score: float) -> SearchHit:
    return SearchHit(
        score=score,
        source_id=1,
        chunk_index=0,
        title="Page",
        url="https://example.com",
        source_type="page",
        text="content",
    )


def test_retrieval_filters_below_threshold():
    qdrant = _FakeQdrant([_hit(0.9), _hit(0.6), _hit(0.3)])
    service = RetrievalService(_FakeEmbedding(), qdrant)
    passing = service.retrieve("q", top_k=10, similarity_threshold=0.55)
    assert len(passing) == 2
    assert all(h.score >= 0.55 for h in passing)


def test_retrieval_returns_empty_when_nothing_passes():
    qdrant = _FakeQdrant([_hit(0.4), _hit(0.2)])
    service = RetrievalService(_FakeEmbedding(), qdrant)
    passing = service.retrieve("q", top_k=10, similarity_threshold=0.55)
    assert passing == []


def test_rag_returns_fallback_without_calling_llm(monkeypatch):
    """If no chunks pass threshold, the LLM must NOT be called."""
    from app.services import rag_service as rag_module

    settings = Settings(
        llm_model="qwen2.5:7b",
        embedding_model="bge-m3",
        qdrant_collection="test",
        top_k=5,
        similarity_threshold=0.55,
        temperature=0.1,
        max_tokens=512,
        system_prompt="system",
        fallback_answer="Я не знайшов цієї інформації на сайті.",
        enable_sources=True,
        enable_chat_logs=False,
    )

    # Disable caches so the no-context fallback path is exercised directly.
    settings.enable_retrieval_cache = False
    settings.enable_semantic_answer_cache = False
    settings.enable_chat_logs = False

    rag = rag_module.RagService.__new__(rag_module.RagService)
    rag.db = None
    rag.settings = settings
    rag.embedding_service = _FakeEmbedding()
    rag.qdrant_service = _FakeQdrant([])  # nothing retrieved -> fallback

    def _fail_chat(*args, **kwargs):  # pragma: no cover
        raise AssertionError("LLM should not be called when no chunks pass threshold")

    class _OllamaGuard:
        chat = staticmethod(_fail_chat)

    rag.ollama = _OllamaGuard()

    result = rag.answer_legacy("anything", session_id=None)
    assert result.used_context is False
    assert result.answer == "Я не знайшов цієї інформації на сайті."
    assert result.sources == []
    assert result.cache_hit is False
    assert result.cache_type == "none"
