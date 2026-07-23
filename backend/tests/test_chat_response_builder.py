"""Unit tests for shared chat response builder."""
from __future__ import annotations

import json

import pytest

from app.schemas.chat import ChatResponse
from app.services.chat_response_builder import ChatResponseBuilder, DiagnosticsCollector
from app.services.rag_service import CacheStatusInfo, RagResult, RagSource


class _SettingsStub:
    knowledge_version = 2
    retrieval_mode = "hybrid"


@pytest.mark.unit
def test_from_rag_result_includes_sources_trace_metadata_cache():
    builder = ChatResponseBuilder(_SettingsStub())
    result = RagResult(
        answer="Test answer",
        sources=[RagSource(title="Page", url="https://x.test", source_type="page", score=0.9)],
        used_context=True,
        request_id="req-1",
        cache_hit=False,
        cache_type="none",
        retrieval_ms=10,
        generation_ms=100,
        polish_ms=5,
        total_ms=115,
        trace={"steps": [{"name": "retrieval", "status": "completed"}]},
        created_at="2026-01-01T00:00:00Z",
        retrieval_debug={"selected_chunks": 3},
        retrieval_diagnostics={"rerank_ms": 2},
        query_intent="overview",
        applied_knowledge_config={"profile": "default"},
        cache=CacheStatusInfo(retrieval_cache_hit=True, cache_type="retrieval_success"),
        prompt_diagnostics={"tokens_per_second": 12.5},
    )
    response = builder.from_rag_result(
        result,
        request_id="req-1",
        session_id="sess-1",
        user_ip="127.0.0.1",
        user_agent="test",
        referrer=None,
    )
    assert response.answer == "Test answer"
    assert len(response.sources) == 1
    assert response.sources[0].title == "Page"
    assert response.trace is not None
    assert response.metadata is not None
    assert response.metadata.query_intent == "overview"
    assert response.cache is not None
    assert response.cache.retrieval_cache_hit is True
    assert response.retrieval_debug is not None
    assert response.retrieval_debug.get("selected_chunks") == 3
    assert response.prompt_diagnostics == {"tokens_per_second": 12.5}


@pytest.mark.unit
def test_final_event_wraps_full_response():
    builder = ChatResponseBuilder(_SettingsStub())
    response = ChatResponse(
        session_id="sess-1",
        request_id="req-1",
        answer="Hi",
        sources=[],
        used_context=False,
        cache_hit=False,
        cache_type="none",
    )
    payload = builder.final_event_payload(response)
    assert "response" in payload
    assert payload["response"]["answer"] == "Hi"
    assert payload["response"]["session_id"] == "sess-1"


@pytest.mark.unit
def test_diagnostics_collector_persistence_json():
    builder = ChatResponseBuilder(_SettingsStub())
    response = builder.from_rag_result(
        RagResult(
            answer="A",
            sources=[],
            used_context=False,
            request_id="req-1",
            total_ms=50,
            retrieval_ms=10,
            generation_ms=40,
        ),
        request_id="req-1",
        session_id="sess-1",
    )
    collector = DiagnosticsCollector(request_id="req-1", session_id="sess-1")
    collector.status("retrieval", "completed", duration_ms=10)
    collector.set_prompt_diagnostics({"streaming_enabled": True})
    raw = collector.to_persistence_json(response)
    data = json.loads(raw)
    assert data["request_id"] == "req-1"
    assert data["trace"] is None or isinstance(data["trace"], dict)
    assert data["metadata"] is not None
    assert data["pipeline_stages"][0]["stage"] == "retrieval"
    assert data["prompt_diagnostics"]["streaming_enabled"] is True


@pytest.mark.unit
def test_from_stream_payload_backward_compat():
    builder = ChatResponseBuilder(_SettingsStub())
    payload = {
        "session_id": "sess-1",
        "request_id": "req-1",
        "answer": "Streamed",
        "sources": [{"title": "T", "url": "https://t", "source_type": "page", "score": 1.0}],
        "used_context": True,
        "cache_hit": False,
        "cache_type": "none",
        "timing": {"total_ms": 1, "retrieval_ms": 1, "generation_ms": 0, "polish_ms": 0},
        "trace": None,
        "metadata": {
            "request_id": "req-1",
            "session_id": "sess-1",
            "query_intent": "faq",
            "knowledge_version": 2,
            "retrieval_mode": "hybrid",
            "created_at": None,
        },
        "retrieval_debug": {"chunks": 2},
        "prompt_diagnostics": {"streaming_enabled": True},
        "cache": None,
        "error_type": None,
    }
    response = builder.from_stream_payload(payload, request_id="req-1", session_id="sess-1")
    assert response.answer == "Streamed"
    assert response.sources[0].url == "https://t"
    assert response.retrieval_debug == {"chunks": 2}
