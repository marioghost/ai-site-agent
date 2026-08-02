"""RFC-100 Step 004/064 — structured chat dispatch logging."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.chat_dispatch_log import log_chat_dispatch, resolve_chat_path


@pytest.mark.unit
def test_log_chat_dispatch_non_stream_executive_disabled(caplog):
    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-1",
            path="executive_disabled",
            mode="non_stream",
            duration_ms=42,
        )

    assert len(caplog.records) == 1
    msg = caplog.records[0].getMessage()
    assert "request_id=req-1" in msg
    assert "path=executive_disabled" in msg
    assert "mode=non_stream" in msg
    assert "duration_ms=42" in msg
    assert "stream_lifecycle" not in msg
    assert "path=legacy" not in msg


@pytest.mark.unit
def test_log_chat_dispatch_non_stream_executive(caplog):
    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-2",
            path="executive",
            mode="non_stream",
            duration_ms=10,
        )

    msg = caplog.records[0].getMessage()
    assert "path=executive" in msg
    assert "mode=non_stream" in msg


@pytest.mark.unit
def test_log_chat_dispatch_stream_start_end(caplog):
    logger = logging.getLogger("app.api.chat")
    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        log_chat_dispatch(
            logger,
            request_id="req-3",
            path="executive",
            mode="stream",
            stream_lifecycle="start",
        )
        log_chat_dispatch(
            logger,
            request_id="req-3",
            path="executive",
            mode="stream",
            stream_lifecycle="end",
            events_count=7,
            duration_ms=120,
        )

    start_msg = caplog.records[0].getMessage()
    end_msg = caplog.records[1].getMessage()
    assert "stream_lifecycle=start" in start_msg
    assert "stream_lifecycle=end" in end_msg
    assert "events_count=7" in end_msg
    assert "duration_ms=120" in end_msg


@pytest.mark.unit
def test_log_chat_dispatch_stream_cancelled(caplog):
    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-4",
            path="executive",
            mode="stream",
            stream_lifecycle="cancelled",
            events_count=2,
            duration_ms=15,
        )

    msg = caplog.records[0].getMessage()
    assert "path=executive" in msg
    assert "stream_lifecycle=cancelled" in msg
    assert "events_count=2" in msg


@pytest.mark.unit
def test_log_chat_dispatch_stream_error(caplog):
    with caplog.at_level(logging.WARNING, logger="app.api.chat"):
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-5",
            path="executive_disabled",
            mode="stream",
            stream_lifecycle="error",
            error_type="executive_disabled",
            events_count=1,
            duration_ms=5,
            level=logging.WARNING,
        )

    assert caplog.records[0].levelno == logging.WARNING
    msg = caplog.records[0].getMessage()
    assert "stream_lifecycle=error" in msg
    assert "error_type=executive_disabled" in msg


@pytest.mark.unit
def test_log_chat_dispatch_omits_none_fields(caplog):
    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-6",
            path="executive",
            mode="non_stream",
        )

    msg = caplog.records[0].getMessage()
    assert "events_count" not in msg
    assert "error_type" not in msg
    assert "duration_ms" not in msg


@pytest.mark.unit
def test_resolve_chat_path_respects_flag(monkeypatch):
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled",
        lambda: False,
    )
    assert resolve_chat_path() == "executive_disabled"

    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled",
        lambda: True,
    )
    assert resolve_chat_path() == "executive"


@pytest.mark.unit
def test_non_stream_dispatch_logs_path_executive_disabled(monkeypatch, caplog):
    from app.api.chat import _dispatch_non_stream_answer

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    monkeypatch.setattr("app.api.chat.ExecutiveService", MagicMock())

    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-ns",
            path="executive_disabled",
            mode="non_stream",
        )
        with pytest.raises(HTTPException) as exc_info:
            _dispatch_non_stream_answer(
                MagicMock(), MagicMock(), "hello", "sess", request_id="req-ns"
            )
        assert exc_info.value.status_code == 503

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "path=executive_disabled" in messages
    assert "mode=non_stream" in messages
    assert "path=legacy" not in messages


@pytest.mark.unit
def test_non_stream_dispatch_logs_path_executive(monkeypatch, caplog):
    from app.api.chat import _dispatch_non_stream_answer

    class _FakeExecutive:
        def answer(self, *args, **kwargs):
            from app.services.rag_service import RagResult

            return RagResult(answer="ok", sources=[], used_context=False, request_id="req-ex")

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive()
    )

    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-ex",
            path="executive",
            mode="non_stream",
        )
        _dispatch_non_stream_answer(
            MagicMock(), MagicMock(), "hello", "sess", request_id="req-ex"
        )
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-ex",
            path="executive",
            mode="non_stream",
            duration_ms=1,
        )

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "path=executive" in messages


@pytest.mark.unit
def test_stream_dispatch_logs_lifecycle_via_helper(caplog):
    logger = logging.getLogger("app.api.chat")
    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        log_chat_dispatch(
            logger,
            request_id="req-st",
            path="executive",
            mode="stream",
            stream_lifecycle="start",
        )
        log_chat_dispatch(
            logger,
            request_id="req-st",
            path="executive",
            mode="stream",
            stream_lifecycle="end",
            events_count=5,
            duration_ms=99,
        )

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "stream_lifecycle=start" in messages
    assert "stream_lifecycle=end" in messages
    assert "events_count=5" in messages


@pytest.mark.unit
def test_log_does_not_contain_sensitive_content(caplog):
    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-safe",
            path="executive",
            mode="non_stream",
            duration_ms=3,
        )

    msg = caplog.records[0].getMessage()
    assert "answer" not in msg.lower()
    assert "prompt" not in msg.lower()
    assert "source" not in msg.lower()
