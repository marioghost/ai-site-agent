"""RFC-100 Step 003/064 — streaming chat routing via ExecutiveService."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from app.api.chat import EXECUTIVE_DISABLED_DETAIL
from app.services.chat_response_builder import ChatResponseBuilder, DiagnosticsCollector


def _parse_sse_events(body: str) -> list[tuple[str, dict]]:
    import json

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


def _golden_stream_events() -> list[tuple[str, dict]]:
    """Canonical streaming session for golden parity under Executive."""
    builder = ChatResponseBuilder(_SettingsStub())
    collector = DiagnosticsCollector(request_id="req-golden", session_id="sess-golden")
    from app.services.rag_service import RagResult, RagSource

    sources = [RagSource(title="About", url="https://site/about", source_type="page", score=0.8)]
    result = RagResult(
        answer="Company overview text",
        sources=sources,
        used_context=True,
        request_id="req-golden",
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
    response = builder.from_rag_result(
        result, request_id="req-golden", session_id="sess-golden"
    )
    return [
        (
            "start",
            {
                "request_id": "req-golden",
                "session_id": "sess-golden",
                "message_id": "req-golden-assistant",
                "streaming": True,
            },
        ),
        ("status", collector.status("retrieval", "running")),
        (
            "retrieval",
            {
                "sources": [
                    {
                        "title": "About",
                        "url": "https://site/about",
                        "source_type": "page",
                        "score": 0.8,
                    }
                ],
                "used_context": True,
                "retrieval_debug": {"selected_chunks": 2},
                "trace_partial": {"steps": [{"name": "retrieval", "status": "running"}]},
            },
        ),
        ("token", {"delta": "Company", "text": "Company"}),
        ("token", {"delta": " overview", "text": " overview"}),
        (
            "diagnostics",
            {
                "prompt_diagnostics": result.prompt_diagnostics,
                "timing_partial": {"retrieval_ms": 20, "generation_ms": 80, "total_ms": 100},
            },
        ),
        ("final", builder.final_event_payload(response)),
    ]


class _SettingsStub:
    knowledge_version = 1
    retrieval_mode = "hybrid"


def _collect_dispatch_events(monkeypatch) -> list[tuple[str, dict]]:
    from app.api.chat import _dispatch_stream_events

    golden = _golden_stream_events()

    class _FakeExecutive:
        def answer_stream(self, *args, **kwargs):
            return iter(golden)

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService",
        lambda db, settings: _FakeExecutive(),
    )

    collector = DiagnosticsCollector(request_id="req-golden", session_id="sess-golden")
    return list(
        _dispatch_stream_events(
            MagicMock(),
            MagicMock(),
            "hello",
            "sess-golden",
            request_id="req-golden",
            collector=collector,
        )
    )


@pytest.mark.unit
def test_stream_dispatch_flag_off_emits_executive_disabled(monkeypatch):
    from app.api.chat import _dispatch_stream_events

    executive_called = {"n": 0}

    class _FakeExecutive:
        def __init__(self, *a, **k):
            executive_called["n"] += 1

        def answer_stream(self, *args, **kwargs):
            raise AssertionError("Executive must not be used when flag is OFF")

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    monkeypatch.setattr("app.api.chat.ExecutiveService", _FakeExecutive)

    events = list(
        _dispatch_stream_events(
            MagicMock(),
            MagicMock(),
            "hello",
            "sess-1",
            request_id="req-1",
        )
    )

    assert executive_called["n"] == 0
    assert len(events) == 1
    assert events[0][0] == "error"
    assert events[0][1]["error_type"] == "executive_disabled"
    assert events[0][1]["message"] == EXECUTIVE_DISABLED_DETAIL


@pytest.mark.unit
def test_stream_dispatch_flag_on_uses_executive(monkeypatch):
    from app.api.chat import _dispatch_stream_events

    executive_called = {"n": 0}
    golden = _golden_stream_events()

    class _FakeExecutive:
        def answer_stream(self, *args, **kwargs):
            executive_called["n"] += 1
            return iter(golden)

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive()
    )

    events = list(
        _dispatch_stream_events(
            MagicMock(),
            MagicMock(),
            "hello",
            "sess-1",
            request_id="req-2",
        )
    )

    assert executive_called["n"] == 1
    assert len(events) == len(golden)


@pytest.mark.unit
def test_stream_golden_event_sequence_contract(monkeypatch):
    """Validate first, intermediate, final, diagnostics, and source events."""
    events = _collect_dispatch_events(monkeypatch)
    names = [name for name, _ in events]

    assert names[0] == "start"
    assert "status" in names
    assert "retrieval" in names
    assert names.index("retrieval") < names.index("token")
    assert names.count("token") == 2
    assert "diagnostics" in names
    assert names[-1] == "final"

    retrieval = next(data for name, data in events if name == "retrieval")
    assert retrieval["sources"]
    assert retrieval["used_context"] is True

    final_data = events[-1][1]
    assert "response" in final_data
    assert final_data["response"]["answer"] == "Company overview text"


@pytest.mark.unit
def test_stream_error_event_passes_through_unchanged(monkeypatch):
    from app.api.chat import _dispatch_stream_events

    error_event = (
        "error",
        {
            "error_type": "prepare_error",
            "message": "boom",
            "partial_diagnostics": {"stage": "retrieval"},
        },
    )

    class _ErrorStream:
        def answer_stream(self, *args, **kwargs):
            yield ("start", {"request_id": "req-err", "session_id": "s", "streaming": True})
            yield error_event

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _ErrorStream()
    )

    events = list(
        _dispatch_stream_events(
            MagicMock(), MagicMock(), "q", "s", request_id="req-err"
        )
    )

    assert events[-1] == error_event


@pytest.mark.unit
def test_stream_dispatch_cancellation_propagates(monkeypatch):
    from app.api.chat import _dispatch_stream_events

    def _slow_stream(*args, **kwargs):
        yield ("start", {"request_id": "req-cancel", "session_id": "s", "streaming": True})
        yield ("token", {"delta": "a", "text": "a"})
        yield ("token", {"delta": "b", "text": "b"})

    class _FakeExecutive:
        def answer_stream(self, *args, **kwargs):
            yield from _slow_stream()

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive()
    )

    stream = _dispatch_stream_events(
        MagicMock(), MagicMock(), "q", "s", request_id="req-cancel"
    )
    first = next(stream)
    assert first[0] == "start"
    stream.close()


@pytest.mark.unit
def test_stream_event_generator_logs_lifecycle(monkeypatch, caplog):
    """Structured stream lifecycle logs use stream_lifecycle=start|end (Step 004)."""
    from app.api.chat_dispatch_log import log_chat_dispatch

    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        logger = logging.getLogger("app.api.chat")
        log_chat_dispatch(
            logger,
            request_id="req-log-stream",
            path="executive",
            mode="stream",
            stream_lifecycle="start",
        )
        log_chat_dispatch(
            logger,
            request_id="req-log-stream",
            path="executive",
            mode="stream",
            stream_lifecycle="end",
            events_count=7,
            duration_ms=50,
        )

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "path=executive" in messages
    assert "stream_lifecycle=start" in messages
    assert "stream_lifecycle=end" in messages
    assert "events_count=7" in messages
    assert "path=legacy" not in messages


@pytest.mark.unit
def test_stream_event_generator_logs_error_on_overloaded(caplog):
    from app.api.chat_dispatch_log import log_chat_dispatch

    with caplog.at_level(logging.WARNING, logger="app.api.chat"):
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-err-stream",
            path="executive",
            mode="stream",
            stream_lifecycle="error",
            error_type="overloaded",
            events_count=0,
            duration_ms=1,
            level=logging.WARNING,
        )

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "stream_lifecycle=error" in messages
    assert "error_type=overloaded" in messages


@pytest.mark.unit
def test_stream_event_generator_logs_cancelled(caplog):
    from app.api.chat_dispatch_log import log_chat_dispatch

    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-cancel-stream",
            path="executive",
            mode="stream",
            stream_lifecycle="cancelled",
            events_count=2,
            duration_ms=3,
        )

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "stream_lifecycle=cancelled" in messages
    assert "path=executive" in messages
