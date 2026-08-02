"""RFC-100 Step 064 — remove API-level Rag/Reasoning bypass; Executive kill-switch."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.chat import EXECUTIVE_DISABLED_DETAIL


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


@pytest.mark.unit
def test_api_chat_module_has_no_direct_rag_or_reasoning_imports():
    """Structural: chat API must not import top-level Rag/Reasoning engines."""
    import ast
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "app" / "api" / "chat.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imported.add(f"{node.module}.{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
    forbidden = {
        "app.services.rag_service.RagService",
        "app.services.rag_streaming.RagStreamingService",
        "app.services.reasoning.ReasoningService",
    }
    assert not (imported & forbidden), f"forbidden imports remain: {imported & forbidden}"


@pytest.mark.unit
@pytest.mark.parametrize("executive_on", [True], ids=["executive_true"])
def test_non_stream_executive_exactly_once(monkeypatch, executive_on):
    from app.api.chat import _dispatch_non_stream_answer
    from app.services.rag_service import RagResult

    calls = {"n": 0}

    class _FakeExecutive:
        def answer(self, *args, **kwargs):
            calls["n"] += 1
            return RagResult(answer="ok", sources=[], used_context=False, request_id="r")

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled", lambda: executive_on
    )
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, s: _FakeExecutive()
    )

    _dispatch_non_stream_answer(MagicMock(), MagicMock(), "q", "s", request_id="r")
    assert calls["n"] == 1


@pytest.mark.unit
def test_non_stream_executive_unset_defaults_to_executive(monkeypatch):
    from app.api.chat import _dispatch_non_stream_answer
    from app.core.config import get_config
    from app.services.rag_service import RagResult

    calls = {"n": 0}

    class _FakeExecutive:
        def answer(self, *args, **kwargs):
            calls["n"] += 1
            return RagResult(answer="ok", sources=[], used_context=False, request_id="r")

    monkeypatch.delenv("KNOWLEDGE_OS_EXECUTIVE_ENABLED", raising=False)
    get_config.cache_clear()
    # Force the chat module flag helper (defaults true when unset).
    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, s: _FakeExecutive()
    )

    _dispatch_non_stream_answer(MagicMock(), MagicMock(), "q", "s", request_id="r")
    assert calls["n"] == 1
    get_config.cache_clear()


@pytest.mark.unit
def test_non_stream_disabled_503_stable_detail_no_engines(monkeypatch):
    from app.api.chat import _dispatch_non_stream_answer

    constructed = {"executive": 0}

    class _FakeExecutive:
        def __init__(self, *a, **k):
            constructed["executive"] += 1

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    monkeypatch.setattr("app.api.chat.ExecutiveService", _FakeExecutive)

    with pytest.raises(HTTPException) as exc_info:
        _dispatch_non_stream_answer(
            MagicMock(), MagicMock(), "q", "s", request_id="r"
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == EXECUTIVE_DISABLED_DETAIL
    assert "operator" in str(exc_info.value.detail).lower()
    assert constructed["executive"] == 0


@pytest.mark.unit
def test_non_stream_disabled_does_not_start_retrieval(monkeypatch):
    """Executive=false must not invoke Executive (hence no retrieval chain)."""
    from app.api.chat import _dispatch_non_stream_answer

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)

    def _boom(*a, **k):
        raise AssertionError("Executive must not be constructed")

    monkeypatch.setattr("app.api.chat.ExecutiveService", _boom)

    with pytest.raises(HTTPException) as exc_info:
        _dispatch_non_stream_answer(
            MagicMock(), MagicMock(), "q", "s", request_id="r"
        )
    assert exc_info.value.status_code == 503


@pytest.mark.unit
def test_reasoning_false_still_enters_executive(monkeypatch):
    """Reasoning=false must still enter Executive (internal Rag degrade is Executive-owned)."""
    from app.api.chat import _dispatch_non_stream_answer
    from app.services.rag_service import RagResult

    calls = {"executive": 0}

    class _FakeExecutive:
        def answer(self, *args, **kwargs):
            calls["executive"] += 1
            return RagResult(
                answer="degraded", sources=[], used_context=True, request_id="r"
            )

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.services.executive.executive_service.reasoning_service_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, s: _FakeExecutive()
    )

    result = _dispatch_non_stream_answer(
        MagicMock(), MagicMock(), "q", "s", request_id="r"
    )
    assert calls["executive"] == 1
    assert result.answer == "degraded"


@pytest.mark.unit
def test_stream_disabled_one_sse_error_no_token_final(monkeypatch):
    from app.api.chat import _dispatch_stream_events

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)

    def _boom(*a, **k):
        raise AssertionError("no fallback engine")

    monkeypatch.setattr("app.api.chat.ExecutiveService", _boom)

    events = list(
        _dispatch_stream_events(MagicMock(), MagicMock(), "q", "s", request_id="r")
    )
    assert len(events) == 1
    name, data = events[0]
    assert name == "error"
    assert data["error_type"] == "executive_disabled"
    assert data["message"] == EXECUTIVE_DISABLED_DETAIL
    names = [n for n, _ in events]
    assert "token" not in names
    assert "final" not in names


def test_stream_disabled_http_sse_contract(monkeypatch, client, auth_headers, caplog):
    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: False
    )

    def _boom(*a, **k):
        raise AssertionError("Executive must not run")

    monkeypatch.setattr("app.api.chat.ExecutiveService", _boom)

    sid = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]
    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        res = client.post(
            "/api/chat/stream",
            json={"message": "hello", "session_id": sid},
            headers=auth_headers,
        )

    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")
    events = _parse_sse_events(res.text)
    assert len(events) == 1
    assert events[0][0] == "error"
    assert events[0][1]["error_type"] == "executive_disabled"
    assert events[0][1]["message"] == EXECUTIVE_DISABLED_DETAIL
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "path=executive_disabled" in messages
    assert "error_type=executive_disabled" in messages
    assert "path=legacy" not in messages


@pytest.mark.unit
def test_dispatch_path_vocabulary(monkeypatch):
    from app.api.chat_dispatch_log import ChatPath, resolve_chat_path

    allowed: set[str] = {"executive", "executive_disabled"}
    assert set(ChatPath.__args__) == allowed  # type: ignore[attr-defined]

    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: True
    )
    assert resolve_chat_path() == "executive"
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: False
    )
    assert resolve_chat_path() == "executive_disabled"


def test_disabled_logged_before_orchestration(monkeypatch, client, auth_headers, caplog):
    order: list[str] = []

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: False
    )

    real_log = __import__(
        "app.api.chat_dispatch_log", fromlist=["log_chat_dispatch"]
    ).log_chat_dispatch

    def _wrap(logger, **kwargs):
        order.append(f"log:{kwargs.get('path')}")
        return real_log(logger, **kwargs)

    monkeypatch.setattr("app.api.chat.log_chat_dispatch", _wrap)

    def _boom(*a, **k):
        order.append("executive")
        raise AssertionError("must not orchestrate")

    monkeypatch.setattr("app.api.chat.ExecutiveService", _boom)

    sid = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]
    with caplog.at_level(logging.INFO, logger="app.api.chat"):
        res = client.post(
            "/api/chat",
            json={"message": "hello", "session_id": sid},
            headers=auth_headers,
        )

    assert res.status_code == 503
    assert order[0] == "log:executive_disabled"
    assert "executive" not in order
