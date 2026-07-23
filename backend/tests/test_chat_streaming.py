"""Unit tests for streaming SSE event protocol shape."""
from __future__ import annotations

import json

import pytest

from app.services.chat_response_builder import ChatResponseBuilder, DiagnosticsCollector
from app.services.rag_service import RagResult, RagSource


class _SettingsStub:
    knowledge_version = 1
    retrieval_mode = "hybrid"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _parse_sse_events(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    current = "message"
    for line in body.split("\n"):
        if line.startswith("event:"):
            current = line[6:].strip()
        elif line.startswith("data:"):
            payload = line[5:].strip()
            if payload == "[DONE]":
                continue
            events.append((current, json.loads(payload)))
    return events


@pytest.mark.unit
def test_streaming_protocol_event_sequence():
    """Simulates RagStreamingService output and validates protocol contract."""
    builder = ChatResponseBuilder(_SettingsStub())
    collector = DiagnosticsCollector(request_id="req-1", session_id="sess-1")
    sources = [RagSource(title="About", url="https://site/about", source_type="page", score=0.8)]
    result = RagResult(
        answer="Company overview text",
        sources=sources,
        used_context=True,
        request_id="req-1",
        retrieval_ms=20,
        generation_ms=80,
        polish_ms=0,
        total_ms=100,
        trace={"steps": [{"name": "retrieval", "status": "completed"}]},
        retrieval_debug={"selected_chunks": 2},
        query_intent="overview",
        prompt_diagnostics={"streaming_enabled": True, "tokens_per_second": 10.0},
        cache=None,
    )
    response = builder.from_rag_result(result, request_id="req-1", session_id="sess-1")
    body = "".join(
        [
            _sse(
                "start",
                {
                    "request_id": "req-1",
                    "session_id": "sess-1",
                    "message_id": "req-1-assistant",
                    "streaming": True,
                },
            ),
            _sse("status", collector.status("retrieval", "running")),
            _sse("retrieval", {
                "sources": [{"title": "About", "url": "https://site/about", "source_type": "page", "score": 0.8}],
                "used_context": True,
                "retrieval_debug": {"selected_chunks": 2},
                "trace_partial": {"steps": [{"name": "retrieval", "status": "running"}]},
            }),
            _sse("token", {"delta": "Company", "text": "Company"}),
            _sse("token", {"delta": " overview", "text": " overview"}),
            _sse(
                "diagnostics",
                {
                    "prompt_diagnostics": result.prompt_diagnostics,
                    "timing_partial": {"retrieval_ms": 20, "generation_ms": 80, "total_ms": 100},
                },
            ),
            _sse("final", builder.final_event_payload(response)),
            "data: [DONE]\n\n",
        ]
    )
    events = _parse_sse_events(body)
    names = [name for name, _ in events]
    assert names[0] == "start"
    assert "retrieval" in names
    assert names.index("retrieval") < names.index("token")
    assert names.count("token") == 2
    assert names[-1] == "final"

    final_data = events[-1][1]
    assert "response" in final_data
    final_response = final_data["response"]
    assert final_response["sources"]
    assert final_response["trace"] is not None
    assert final_response["metadata"] is not None
    assert final_response["retrieval_debug"] is not None
    assert final_response["prompt_diagnostics"]["streaming_enabled"] is True
    assert final_response["answer"] == "Company overview text"


@pytest.mark.unit
def test_streaming_final_schema_matches_non_streaming_fields():
    builder = ChatResponseBuilder(_SettingsStub())
    result = RagResult(
        answer="A",
        sources=[RagSource(title="T", url="https://t", source_type="page", score=0.5)],
        used_context=True,
        request_id="r",
        cache_hit=True,
        cache_type="answer_success",
        total_ms=10,
        retrieval_ms=1,
        generation_ms=9,
        trace={"steps": [{"name": "retrieval", "status": "completed"}]},
    )
    non_streaming = builder.from_rag_result(result, request_id="r", session_id="s")
    streaming_final = builder.final_event_payload(non_streaming)["response"]
    for key in (
        "session_id",
        "request_id",
        "answer",
        "sources",
        "used_context",
        "cache_hit",
        "cache_type",
        "timing",
        "trace",
        "metadata",
        "retrieval_debug",
        "prompt_diagnostics",
        "cache",
        "error_type",
    ):
        assert key in streaming_final
