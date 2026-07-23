"""Unit tests for ExecutiveService passthrough (RFC-100 Step 001)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.chat_response_builder import DiagnosticsCollector
from app.services.executive import ExecutiveService
from app.services.rag_service import RagResult, RagSource


@pytest.mark.unit
def test_executive_answer_delegates_to_rag_service():
    expected = RagResult(
        answer="test answer",
        sources=[RagSource(title="T", url="https://x", source_type="page", score=0.9)],
        used_context=True,
        request_id="req-1",
    )
    mock_rag = MagicMock()
    mock_rag.answer.return_value = expected

    db = MagicMock()
    settings = MagicMock()

    with patch("app.services.executive.executive_service.RagService", return_value=mock_rag):
        with patch("app.services.executive.executive_service.RagStreamingService"):
            svc = ExecutiveService(db, settings)
            result = svc.answer(
                "hello",
                "sess-1",
                request_id="req-1",
                user_ip="1.2.3.4",
                user_agent="test-agent",
                referrer="https://ref",
                debug=True,
                bypass_cache=True,
            )

    assert result is expected
    mock_rag.answer.assert_called_once_with(
        "hello",
        "sess-1",
        request_id="req-1",
        user_ip="1.2.3.4",
        user_agent="test-agent",
        referrer="https://ref",
        debug=True,
        bypass_cache=True,
    )


@pytest.mark.unit
def test_executive_answer_stream_delegates_to_rag_streaming():
    events = [("start", {"request_id": "req-2"}), ("token", {"delta": "hi"})]
    mock_streaming = MagicMock()
    mock_streaming.iter_events.return_value = iter(events)

    db = MagicMock()
    settings = MagicMock()
    collector = DiagnosticsCollector(request_id="req-2", session_id="sess-2")

    with patch("app.services.executive.executive_service.RagService"):
        with patch(
            "app.services.executive.executive_service.RagStreamingService",
            return_value=mock_streaming,
        ):
            svc = ExecutiveService(db, settings)
            collected = list(
                svc.answer_stream(
                    "stream me",
                    "sess-2",
                    request_id="req-2",
                    collector=collector,
                    debug=False,
                    bypass_cache=False,
                )
            )

    assert collected == events
    mock_streaming.iter_events.assert_called_once_with(
        "stream me",
        "sess-2",
        request_id="req-2",
        collector=collector,
        user_ip=None,
        user_agent=None,
        referrer=None,
        debug=False,
        bypass_cache=False,
    )


@pytest.mark.unit
def test_executive_service_does_not_add_orchestration_logic():
    """Step 001: Executive must not transform results — pure delegation."""
    mock_rag = MagicMock()
    mock_rag.answer.return_value = RagResult(
        answer="unchanged",
        sources=[],
        used_context=False,
        request_id="req-3",
        query_intent="overview",
    )

    with patch("app.services.executive.executive_service.RagService", return_value=mock_rag):
        with patch("app.services.executive.executive_service.RagStreamingService"):
            svc = ExecutiveService(MagicMock(), MagicMock())
            result = svc.answer("q", None, request_id="req-3")

    assert result.answer == "unchanged"
    assert result.query_intent == "overview"
    mock_rag.answer.assert_called_once()
