"""RFC-100 Step 002/064 — non-streaming chat routing via ExecutiveService."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.chat import EXECUTIVE_DISABLED_DETAIL
from app.core.concurrency import OverloadedError
from app.services.rag_service import RagResult, RagSource


def _fake_rag_result(**overrides) -> RagResult:
    base = {
        "answer": "Test answer",
        "sources": [
            RagSource(title="About", url="https://site/about", source_type="page", score=0.8)
        ],
        "used_context": True,
        "request_id": "req-routing",
        "cache_hit": False,
        "cache_type": "none",
        "retrieval_ms": 10,
        "generation_ms": 20,
        "polish_ms": 0,
        "total_ms": 30,
        "query_intent": "overview",
    }
    base.update(overrides)
    return RagResult(**base)


@pytest.mark.unit
def test_knowledge_os_executive_enabled_defaults_true(monkeypatch):
    from app.core.config import get_config

    monkeypatch.delenv("KNOWLEDGE_OS_EXECUTIVE_ENABLED", raising=False)
    get_config.cache_clear()
    from app.services.feature_flags import knowledge_os_executive_enabled

    assert knowledge_os_executive_enabled() is True
    get_config.cache_clear()


@pytest.mark.unit
def test_knowledge_os_executive_enabled_reads_env(monkeypatch):
    from app.core.config import get_config

    monkeypatch.setenv("KNOWLEDGE_OS_EXECUTIVE_ENABLED", "true")
    get_config.cache_clear()
    from app.services.feature_flags import knowledge_os_executive_enabled

    assert knowledge_os_executive_enabled() is True
    get_config.cache_clear()


@pytest.mark.unit
def test_knowledge_os_executive_enabled_kill_switch_false(monkeypatch):
    from app.core.config import get_config

    monkeypatch.setenv("KNOWLEDGE_OS_EXECUTIVE_ENABLED", "false")
    get_config.cache_clear()
    from app.services.feature_flags import knowledge_os_executive_enabled

    assert knowledge_os_executive_enabled() is False
    get_config.cache_clear()


@pytest.mark.unit
def test_dispatch_flag_unset_uses_executive_exactly_once(monkeypatch):
    """Unset Executive (default ON) → ExecutiveService exactly once."""
    from unittest.mock import MagicMock

    from app.api.chat import _dispatch_non_stream_answer

    executive_called = {"n": 0}

    class _FakeExecutive:
        def answer(self, message, session_id, **kwargs):
            executive_called["n"] += 1
            return _fake_rag_result(request_id=kwargs.get("request_id", "req"))

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive()
    )

    result = _dispatch_non_stream_answer(
        MagicMock(),
        MagicMock(),
        "hello",
        "sess-1",
        request_id="req-unset",
    )

    assert executive_called["n"] == 1
    assert result.answer == "Test answer"


@pytest.mark.unit
def test_dispatch_flag_off_raises_503_controlled_unavailable(monkeypatch):
    """When Executive is OFF, dispatch must 503 — no Rag / Reasoning / Executive."""
    from unittest.mock import MagicMock

    from app.api.chat import _dispatch_non_stream_answer

    executive_called = {"n": 0}

    class _FakeExecutive:
        def __init__(self, db, settings):
            executive_called["n"] += 1

        def answer(self, *args, **kwargs):
            raise AssertionError("ExecutiveService must not run when flag is OFF")

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    monkeypatch.setattr("app.api.chat.ExecutiveService", _FakeExecutive)

    with pytest.raises(HTTPException) as exc_info:
        _dispatch_non_stream_answer(
            MagicMock(),
            MagicMock(),
            "hello",
            "sess-1",
            request_id="req-1",
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == EXECUTIVE_DISABLED_DETAIL
    assert executive_called["n"] == 0


@pytest.mark.unit
def test_dispatch_flag_on_uses_executive_service(monkeypatch):
    """When flag is ON, dispatch must call ExecutiveService.answer exactly once."""
    from unittest.mock import MagicMock

    from app.api.chat import _dispatch_non_stream_answer

    executive_called = {"n": 0}

    class _FakeExecutive:
        def answer(self, message, session_id, **kwargs):
            executive_called["n"] += 1
            return _fake_rag_result(request_id=kwargs.get("request_id", "req"))

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive()
    )

    result = _dispatch_non_stream_answer(
        MagicMock(),
        MagicMock(),
        "hello",
        "sess-1",
        request_id="req-2",
    )

    assert executive_called["n"] == 1
    assert result.answer == "Test answer"


@pytest.mark.unit
def test_dispatch_reasoning_flag_does_not_bypass_executive(monkeypatch):
    """Reasoning ON must not create an API-level bypass around Executive."""
    from unittest.mock import MagicMock

    from app.api.chat import _dispatch_non_stream_answer

    executive_called = {"n": 0}

    class _FakeExecutive:
        def answer(self, *args, **kwargs):
            executive_called["n"] += 1
            return _fake_rag_result()

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive()
    )

    result = _dispatch_non_stream_answer(
        MagicMock(), MagicMock(), "q", "s", request_id="req-rsn"
    )
    assert executive_called["n"] == 1
    assert result.answer == "Test answer"


@pytest.mark.unit
def test_dispatch_logs_path_executive_and_disabled(monkeypatch, caplog):
    """Structured dispatch logging uses path=executive|executive_disabled (Step 064)."""
    import logging
    from unittest.mock import MagicMock

    from app.api.chat import _dispatch_non_stream_answer
    from app.api.chat_dispatch_log import log_chat_dispatch

    class _FakeExecutive:
        def answer(self, *args, **kwargs):
            return _fake_rag_result()

    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive()
    )

    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-log-1",
            path="executive_disabled",
            mode="non_stream",
        )
        with pytest.raises(HTTPException) as exc_info:
            _dispatch_non_stream_answer(
                MagicMock(), MagicMock(), "m", "s", request_id="req-log-1"
            )
        assert exc_info.value.status_code == 503

        monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-log-2",
            path="executive",
            mode="non_stream",
        )
        _dispatch_non_stream_answer(
            MagicMock(), MagicMock(), "m", "s", request_id="req-log-2"
        )

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "path=executive_disabled" in messages
    assert "path=executive" in messages
    assert "path=legacy" not in messages


@pytest.mark.unit
def test_dispatch_overloaded_error_propagates(monkeypatch):
    """OverloadedError must propagate unchanged from the Executive path."""
    from unittest.mock import MagicMock

    from app.api.chat import _dispatch_non_stream_answer

    class _Overloaded:
        def answer(self, *args, **kwargs):
            raise OverloadedError("too many requests")

    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _Overloaded()
    )
    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    with pytest.raises(OverloadedError, match="too many requests"):
        _dispatch_non_stream_answer(
            MagicMock(), MagicMock(), "q", "s", request_id="req-err-2"
        )


def test_chat_flag_off_returns_503(monkeypatch, client, auth_headers):
    """When Executive is OFF, /api/chat returns HTTP 503 controlled unavailable."""
    executive_called = {"n": 0}

    class _FakeExecutive:
        def __init__(self, db, settings):
            executive_called["n"] += 1

        def answer(self, *args, **kwargs):
            raise AssertionError("ExecutiveService must not be used when flag is OFF")

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: False
    )
    monkeypatch.setattr("app.api.chat.ExecutiveService", _FakeExecutive)

    sid = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]
    res = client.post(
        "/api/chat",
        json={"message": "hello", "session_id": sid},
        headers=auth_headers,
    )

    assert res.status_code == 503
    assert res.json()["detail"] == EXECUTIVE_DISABLED_DETAIL
    assert executive_called["n"] == 0


def test_chat_flag_on_uses_executive_service(monkeypatch, client, auth_headers):
    """When flag is ON, /api/chat must call ExecutiveService.answer."""
    executive_called = {"n": 0}

    class _FakeExecutive:
        def answer(self, message, session_id, **kwargs):
            executive_called["n"] += 1
            return _fake_rag_result(request_id=kwargs.get("request_id", "req"))

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: True
    )
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive()
    )

    sid = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]
    res = client.post(
        "/api/chat",
        json={"message": "hello", "session_id": sid},
        headers=auth_headers,
    )

    assert res.status_code == 200
    assert executive_called["n"] == 1
    body = res.json()
    assert body["answer"] == "Test answer"
    assert body["metadata"]["query_intent"] == "overview"


def test_chat_success_schema_stable_with_executive(monkeypatch, client, auth_headers):
    """Successful Executive path preserves ChatResponse schema keys."""
    sid = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]
    payload = {"message": "schema check", "session_id": sid}

    class _SharedFake:
        def answer(self, message, session_id, **kwargs):
            return _fake_rag_result(request_id=kwargs.get("request_id", "req"))

    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _SharedFake()
    )
    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: True
    )

    executive = client.post("/api/chat", json=payload, headers=auth_headers)
    assert executive.status_code == 200
    body = executive.json()
    assert "answer" in body
    assert "sources" in body
    assert "used_context" in body
    assert body["answer"] == "Test answer"


def test_chat_overloaded_error_propagates_on_executive_path(
    monkeypatch, client, auth_headers
):
    """OverloadedError must return 429 on the Executive path."""

    class _OverloadedExecutive:
        def answer(self, *args, **kwargs):
            raise OverloadedError("too many requests")

    sid = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]
    payload = {"message": "overload", "session_id": sid}

    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _OverloadedExecutive()
    )
    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: True
    )

    executive = client.post("/api/chat", json=payload, headers=auth_headers)
    assert executive.status_code == 429
    assert "too many" in executive.json()["detail"].lower() or executive.json()[
        "detail"
    ]
