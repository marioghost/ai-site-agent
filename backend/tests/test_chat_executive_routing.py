"""RFC-100 Step 002 — non-streaming chat routing via knowledge_os_executive_enabled."""
from __future__ import annotations

import pytest

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
def test_knowledge_os_executive_enabled_defaults_false(monkeypatch):
    from app.core.config import get_config

    monkeypatch.delenv("KNOWLEDGE_OS_EXECUTIVE_ENABLED", raising=False)
    get_config.cache_clear()
    from app.services.feature_flags import knowledge_os_executive_enabled

    assert knowledge_os_executive_enabled() is False


@pytest.mark.unit
def test_knowledge_os_executive_enabled_reads_env(monkeypatch):
    from app.core.config import get_config

    monkeypatch.setenv("KNOWLEDGE_OS_EXECUTIVE_ENABLED", "true")
    get_config.cache_clear()
    from app.services.feature_flags import knowledge_os_executive_enabled

    assert knowledge_os_executive_enabled() is True


@pytest.mark.unit
def test_dispatch_flag_off_uses_rag_service(monkeypatch):
    """When flag is OFF, dispatch must call RagService directly."""
    from unittest.mock import MagicMock

    from app.api.chat import _dispatch_non_stream_answer

    rag_called = {"n": 0}
    executive_called = {"n": 0}

    class _FakeRag:
        def answer(self, message, session_id, **kwargs):
            rag_called["n"] += 1
            return _fake_rag_result(request_id=kwargs.get("request_id", "req"))

    class _FakeExecutive:
        def __init__(self, db, settings):
            executive_called["n"] += 1

        def answer(self, *args, **kwargs):
            raise AssertionError("ExecutiveService must not be used when flag is OFF")

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: False,
    )
    monkeypatch.setattr("app.api.chat.RagService", lambda db, settings: _FakeRag())
    monkeypatch.setattr("app.api.chat.ExecutiveService", _FakeExecutive)

    result = _dispatch_non_stream_answer(
        MagicMock(),
        MagicMock(),
        "hello",
        "sess-1",
        request_id="req-1",
    )

    assert rag_called["n"] == 1
    assert executive_called["n"] == 0
    assert result.answer == "Test answer"


@pytest.mark.unit
def test_dispatch_flag_on_uses_executive_service(monkeypatch):
    """When flag is ON, dispatch must call ExecutiveService.answer."""
    from unittest.mock import MagicMock

    from app.api.chat import _dispatch_non_stream_answer

    rag_called = {"n": 0}
    executive_called = {"n": 0}

    class _FakeRag:
        def __init__(self, db, settings):
            rag_called["n"] += 1

        def answer(self, *args, **kwargs):
            raise AssertionError("RagService must not be used directly when flag is ON")

    class _FakeExecutive:
        def answer(self, message, session_id, **kwargs):
            executive_called["n"] += 1
            return _fake_rag_result(request_id=kwargs.get("request_id", "req"))

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: True,
    )
    monkeypatch.setattr("app.api.chat.RagService", _FakeRag)
    monkeypatch.setattr("app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive())

    result = _dispatch_non_stream_answer(
        MagicMock(),
        MagicMock(),
        "hello",
        "sess-1",
        request_id="req-2",
    )

    assert executive_called["n"] == 1
    assert rag_called["n"] == 0
    assert result.answer == "Test answer"


@pytest.mark.unit
def test_dispatch_both_paths_return_same_result(monkeypatch):
    """Executive passthrough must return the same RagResult as legacy."""
    from unittest.mock import MagicMock

    from app.api.chat import _dispatch_non_stream_answer

    shared = _fake_rag_result(request_id="req-3")

    class _SharedFake:
        def answer(self, *args, **kwargs):
            return shared

    monkeypatch.setattr("app.api.chat.RagService", lambda db, settings: _SharedFake())
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _SharedFake()
    )

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: False,
    )
    legacy = _dispatch_non_stream_answer(
        MagicMock(), MagicMock(), "q", "s", request_id="req-3"
    )

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: True,
    )
    executive = _dispatch_non_stream_answer(
        MagicMock(), MagicMock(), "q", "s", request_id="req-3"
    )

    assert legacy == executive


@pytest.mark.unit
def test_dispatch_logs_path(monkeypatch, caplog):
    """Structured dispatch logging uses path=legacy|executive (Step 004)."""
    import logging
    from unittest.mock import MagicMock

    from app.api.chat import _dispatch_non_stream_answer
    from app.api.chat_dispatch_log import log_chat_dispatch

    class _FakeRag:
        def answer(self, *args, **kwargs):
            return _fake_rag_result()

    monkeypatch.setattr("app.api.chat.RagService", lambda db, settings: _FakeRag())
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeRag()
    )

    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-log-1",
            path="legacy",
            mode="non_stream",
        )
        _dispatch_non_stream_answer(
            MagicMock(), MagicMock(), "m", "s", request_id="req-log-1"
        )

        monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
        log_chat_dispatch(
            logging.getLogger("app.api.chat"),
            request_id="req-log-2",
            path="executive",
            mode="non_stream",
        )

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "path=legacy" in messages
    assert "path=executive" in messages


@pytest.mark.unit
def test_dispatch_overloaded_error_propagates(monkeypatch):
    """OverloadedError must propagate unchanged from both paths."""
    from unittest.mock import MagicMock

    from app.api.chat import _dispatch_non_stream_answer

    class _Overloaded:
        def answer(self, *args, **kwargs):
            raise OverloadedError("too many requests")

    monkeypatch.setattr("app.api.chat.RagService", lambda db, settings: _Overloaded())
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _Overloaded()
    )

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    with pytest.raises(OverloadedError, match="too many requests"):
        _dispatch_non_stream_answer(
            MagicMock(), MagicMock(), "q", "s", request_id="req-err-1"
        )

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    with pytest.raises(OverloadedError, match="too many requests"):
        _dispatch_non_stream_answer(
            MagicMock(), MagicMock(), "q", "s", request_id="req-err-2"
        )


def test_chat_flag_off_uses_rag_service(monkeypatch, client, auth_headers):
    """When flag is OFF, /api/chat must call RagService directly."""
    rag_called = {"n": 0}
    executive_called = {"n": 0}

    class _FakeRag:
        def answer(self, message, session_id, **kwargs):
            rag_called["n"] += 1
            return _fake_rag_result(request_id=kwargs.get("request_id", "req"))

    class _FakeExecutive:
        def __init__(self, db, settings):
            executive_called["n"] += 1

        def answer(self, *args, **kwargs):
            raise AssertionError("ExecutiveService must not be used when flag is OFF")

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: False,
    )
    monkeypatch.setattr("app.api.chat.RagService", lambda db, settings: _FakeRag())
    monkeypatch.setattr("app.api.chat.ExecutiveService", _FakeExecutive)

    sid = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]
    res = client.post(
        "/api/chat",
        json={"message": "hello", "session_id": sid},
        headers=auth_headers,
    )

    assert res.status_code == 200
    assert rag_called["n"] == 1
    assert executive_called["n"] == 0
    body = res.json()
    assert body["answer"] == "Test answer"
    assert body["used_context"] is True
    assert len(body["sources"]) == 1


def test_chat_flag_on_uses_executive_service(monkeypatch, client, auth_headers):
    """When flag is ON, /api/chat must call ExecutiveService.answer."""
    rag_called = {"n": 0}
    executive_called = {"n": 0}

    class _FakeRag:
        def __init__(self, db, settings):
            rag_called["n"] += 1

        def answer(self, *args, **kwargs):
            raise AssertionError("RagService must not be used directly when flag is ON")

    class _FakeExecutive:
        def answer(self, message, session_id, **kwargs):
            executive_called["n"] += 1
            return _fake_rag_result(request_id=kwargs.get("request_id", "req"))

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: True,
    )
    monkeypatch.setattr("app.api.chat.RagService", _FakeRag)
    monkeypatch.setattr("app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive())

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
    assert rag_called["n"] == 0
    body = res.json()
    assert body["answer"] == "Test answer"
    assert body["metadata"]["query_intent"] == "overview"


def test_chat_flag_on_and_off_return_identical_schema(monkeypatch, client, auth_headers):
    """Executive passthrough must produce the same response shape as legacy."""
    sid = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]
    payload = {"message": "schema check", "session_id": sid}

    class _SharedFake:
        def answer(self, message, session_id, **kwargs):
            return _fake_rag_result(request_id=kwargs.get("request_id", "req"))

    monkeypatch.setattr("app.api.chat.RagService", lambda db, settings: _SharedFake())
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _SharedFake()
    )

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: False,
    )
    legacy = client.post("/api/chat", json=payload, headers=auth_headers)
    assert legacy.status_code == 200

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: True,
    )
    executive = client.post("/api/chat", json=payload, headers=auth_headers)
    assert executive.status_code == 200

    legacy_body = legacy.json()
    executive_body = executive.json()
    assert set(legacy_body.keys()) == set(executive_body.keys())
    assert legacy_body["answer"] == executive_body["answer"]
    assert legacy_body["used_context"] == executive_body["used_context"]
    assert legacy_body["sources"] == executive_body["sources"]


def test_chat_overloaded_error_propagates_same_for_both_paths(
    monkeypatch, client, auth_headers
):
    """OverloadedError must return 429 on both legacy and executive paths."""

    class _OverloadedRag:
        def answer(self, *args, **kwargs):
            raise OverloadedError("too many requests")

    class _OverloadedExecutive:
        def answer(self, *args, **kwargs):
            raise OverloadedError("too many requests")

    sid = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]
    payload = {"message": "overload", "session_id": sid}

    monkeypatch.setattr("app.api.chat.RagService", lambda db, settings: _OverloadedRag())
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _OverloadedExecutive()
    )

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: False,
    )
    legacy = client.post("/api/chat", json=payload, headers=auth_headers)
    assert legacy.status_code == 429

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: True,
    )
    executive = client.post("/api/chat", json=payload, headers=auth_headers)
    assert executive.status_code == 429
    assert executive.json()["detail"] == legacy.json()["detail"]
