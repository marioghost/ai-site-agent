"""RFC-100 Step 013 — semantic diagnostics schema stubs."""
from __future__ import annotations

import json

import pytest

from app.schemas.chat import ChatResponse
from app.schemas.semantic_diagnostics import (
    ChatDiagnosticsEnvelope,
    UnderstandingTraceRead,
    empty_understanding_trace,
    merge_semantic_debug_fields,
    semantic_debug_fields,
)
from app.services.chat_response_builder import ChatResponseBuilder, DiagnosticsCollector
from app.services.rag_service import RagResult


class _SettingsStub:
    knowledge_version = 1
    retrieval_mode = "hybrid"
    enable_semantic_diagnostics_v2 = False


class _SettingsStubV2Enabled(_SettingsStub):
    enable_semantic_diagnostics_v2 = True


def _minimal_rag_result(**overrides) -> RagResult:
    base = dict(
        answer="Answer",
        sources=[],
        used_context=True,
        request_id="req-1",
        retrieval_debug={"selected_chunks": 1},
    )
    base.update(overrides)
    return RagResult(**base)


@pytest.mark.unit
def test_understanding_trace_stub_defaults_are_empty():
    trace = empty_understanding_trace()
    assert trace.version == "stub"
    assert trace.populated is False
    assert trace.summary is None
    assert trace.steps == []


@pytest.mark.unit
def test_semantic_debug_fields_absent_when_debug_disabled():
    assert semantic_debug_fields(debug=False) == {}


@pytest.mark.unit
def test_semantic_debug_fields_include_understanding_trace_when_debug_enabled():
    fields = semantic_debug_fields(debug=True)
    assert "understanding_trace" in fields
    trace = UnderstandingTraceRead.model_validate(fields["understanding_trace"])
    assert trace.version == "stub"
    assert trace.populated is False
    assert trace.steps == []


@pytest.mark.unit
def test_merge_semantic_debug_fields_preserves_existing_payload():
    merged = merge_semantic_debug_fields(
        {"request_id": "req-1", "pipeline_stages": []},
        debug=True,
    )
    assert merged["request_id"] == "req-1"
    assert merged["pipeline_stages"] == []
    assert "understanding_trace" in merged
    assert merged["understanding_trace"]["version"] == "stub"


@pytest.mark.unit
def test_chat_response_backward_compatible_without_understanding_trace():
    """Legacy clients / payloads without understanding_trace must still validate."""
    legacy_payload = {
        "session_id": "sess-legacy",
        "request_id": "req-legacy",
        "answer": "Hello",
        "sources": [],
        "used_context": False,
        "cache_hit": False,
        "cache_type": "none",
        "error_type": None,
        "prompt_diagnostics": None,
        "cache": None,
        "timing": {
            "total_ms": 10,
            "retrieval_ms": 5,
            "generation_ms": 5,
            "polish_ms": 0,
        },
        "trace": None,
        "metadata": None,
        "retrieval_debug": None,
    }
    response = ChatResponse.model_validate(legacy_payload)
    assert response.understanding_trace is None
    assert response.answer == "Hello"


@pytest.mark.unit
def test_chat_response_builder_unchanged_when_flag_off():
    """Step 014: default flag OFF must not alter production response assembly."""
    builder = ChatResponseBuilder(_SettingsStub())
    response = builder.from_rag_result(
        _minimal_rag_result(),
        request_id="req-1",
        session_id="sess-1",
        debug=True,
    )
    assert response.understanding_trace is None
    assert response.model_dump().get("understanding_trace") is None


@pytest.mark.unit
def test_flag_off_preserves_explicit_understanding_trace_in_stream_payload():
    builder = ChatResponseBuilder(_SettingsStub())
    explicit = empty_understanding_trace().model_copy(update={"summary": "explicit"})
    response = builder.from_stream_payload(
        {
            "session_id": "sess-1",
            "request_id": "req-1",
            "answer": "Streamed",
            "sources": [],
            "used_context": True,
            "cache_hit": False,
            "cache_type": "none",
            "timing": {"total_ms": 1, "retrieval_ms": 1, "generation_ms": 0, "polish_ms": 0},
            "understanding_trace": explicit.model_dump(),
        },
        request_id="req-1",
        session_id="sess-1",
        debug=False,
    )
    assert response.understanding_trace is not None
    assert response.understanding_trace.summary == "explicit"


@pytest.mark.unit
def test_flag_on_debug_enabled_includes_understanding_trace_stub():
    builder = ChatResponseBuilder(_SettingsStubV2Enabled())
    response = builder.from_rag_result(
        _minimal_rag_result(),
        request_id="req-1",
        session_id="sess-1",
        debug=True,
    )
    assert response.understanding_trace is not None
    assert response.understanding_trace.version == "stub"
    assert response.understanding_trace.populated is False
    assert response.understanding_trace.steps == []


@pytest.mark.unit
def test_flag_on_debug_disabled_omits_understanding_trace():
    builder = ChatResponseBuilder(_SettingsStubV2Enabled())
    response = builder.from_rag_result(
        _minimal_rag_result(),
        request_id="req-1",
        session_id="sess-1",
        debug=False,
    )
    assert response.understanding_trace is None


@pytest.mark.unit
def test_flag_on_debug_enabled_persists_understanding_trace_in_diagnostics_json():
    builder = ChatResponseBuilder(_SettingsStubV2Enabled())
    response = builder.from_rag_result(
        _minimal_rag_result(),
        request_id="req-1",
        session_id="sess-1",
        debug=True,
    )
    collector = DiagnosticsCollector(request_id="req-1", session_id="sess-1")
    payload = json.loads(collector.to_persistence_json(response))
    assert "understanding_trace" in payload
    assert payload["understanding_trace"]["version"] == "stub"


@pytest.mark.unit
def test_semantic_diagnostics_v2_enabled_defaults_false():
    from app.services.feature_flags import semantic_diagnostics_v2_enabled

    assert semantic_diagnostics_v2_enabled(_SettingsStub()) is False
    assert semantic_diagnostics_v2_enabled(_SettingsStubV2Enabled()) is True


@pytest.mark.unit
def test_chat_diagnostics_envelope_accepts_legacy_extra_fields():
    raw = {
        "request_id": "req-1",
        "session_id": "sess-1",
        "pipeline_stages": [{"stage": "retrieval", "status": "completed"}],
        "query_intent": "overview",
    }
    envelope = ChatDiagnosticsEnvelope.model_validate(raw)
    assert envelope.understanding_trace is None


@pytest.mark.unit
def test_chat_diagnostics_envelope_validates_understanding_trace_when_debug_enabled():
    payload = merge_semantic_debug_fields(
        {"request_id": "req-debug", "session_id": "sess-debug"},
        debug=True,
    )
    envelope = ChatDiagnosticsEnvelope.model_validate(payload)
    assert envelope.understanding_trace is not None
    assert envelope.understanding_trace.version == "stub"
    assert envelope.understanding_trace.populated is False

    # Round-trip JSON safe for persistence layer (Step 014)
    roundtrip = json.loads(json.dumps(payload))
    ChatDiagnosticsEnvelope.model_validate(roundtrip)
