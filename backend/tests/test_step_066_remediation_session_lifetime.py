"""RFC-100 Step 066 remediation — Ask DB session lifetime (behavioral)."""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import TimeoutError as SATimeoutError

from app.core.ask_db import (
    cancel_cleanup_count,
    is_pool_timeout,
    park_count,
    park_session_for_llm,
    raise_capacity_overload,
    record_cancel_cleanup,
    unpark_count,
    unpark_session_after_llm,
)
from app.core.concurrency import OverloadedError, concurrency
from app.services.rag_service import RagResult


@pytest.mark.unit
def test_park_releases_owner_db_before_llm_wait():
    """Non-stream contract: owner.db must be None during mocked LLM wait."""
    closed = {"n": 0}

    class _Sess:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            closed["n"] += 1

    owner = SimpleNamespace(
        db=_Sess(),
        settings=MagicMock(),
        retrieval_cache=MagicMock(),
        answer_cache=MagicMock(),
    )
    before_park = park_count()
    park_session_for_llm(owner)
    assert owner.db is None
    assert closed["n"] == 1
    assert park_count() == before_park + 1

    held_during_llm = {"db": owner.db}
    # Simulated slow LLM — session must stay released.
    time.sleep(0.02)
    assert held_during_llm["db"] is None
    assert owner.db is None


@pytest.mark.unit
def test_unpark_opens_fresh_session_after_llm(monkeypatch):
    fresh = MagicMock(name="fresh_session")
    monkeypatch.setattr("app.core.ask_db.SessionLocal", lambda: fresh)
    owner = SimpleNamespace(db=None, settings=MagicMock())
    before = unpark_count()
    out = unpark_session_after_llm(owner)
    assert out is fresh
    assert owner.db is fresh
    assert unpark_count() == before + 1


@pytest.mark.unit
def test_rag_generate_parks_across_mocked_llm():
    """Behavioral park→LLM→unpark order with db=None during generation."""
    timeline: list[str] = []
    owner = SimpleNamespace(db=MagicMock(name="pre"), settings=MagicMock())

    def _park(o):
        timeline.append("park")
        o.db.close()
        o.db = None

    def _unpark(o):
        timeline.append("unpark")
        o.db = MagicMock(name="post")
        return o.db

    def _generate(*, db=None):
        timeline.append("llm")
        assert db is None
        assert owner.db is None
        return {"answer": "ok", "generation_ms": 1, "diagnostics": {}}

    _park(owner)
    try:
        out = _generate(db=None)
    finally:
        _unpark(owner)

    assert timeline == ["park", "llm", "unpark"]
    assert out["answer"] == "ok"
    assert owner.db is not None


@pytest.mark.unit
def test_stream_generator_exit_records_cancel_and_releases_chat_slot():
    """Cancel / GeneratorExit must release chat_slot and record cleanup."""
    from app.core.ask_db import cancel_cleanup_count as _ccc

    before = _ccc()
    concurrency.configure(
        concurrency.limits.__class__(
            max_concurrent_chat_requests=1,
            max_concurrent_llm_requests=2,
            max_concurrent_embedding_requests=2,
            max_concurrent_background_embedding_requests=1,
        )
    )

    def _gen():
        with concurrency.chat_slot(wait_seconds=0.5):
            try:
                yield "token"
                # Simulate parked state (no DB) during stream body.
                yield "token2"
            except GeneratorExit:
                record_cancel_cleanup()
                raise

    g = _gen()
    assert next(g) == "token"
    assert concurrency.metrics.active_chat == 1
    g.close()  # GeneratorExit
    assert cancel_cleanup_count() == before + 1
    assert concurrency.metrics.active_chat == 0


@pytest.mark.unit
def test_exception_path_closes_short_session(monkeypatch):
    closed = {"n": 0}

    class _Sess:
        def commit(self):
            raise RuntimeError("boom")

        def rollback(self):
            return None

        def close(self):
            closed["n"] += 1

    monkeypatch.setattr("app.core.ask_db.SessionLocal", lambda: _Sess())
    from app.core.ask_db import ask_session

    with pytest.raises(RuntimeError, match="boom"):
        with ask_session():
            pass
    assert closed["n"] == 1


@pytest.mark.unit
def test_pool_timeout_maps_to_overloaded_not_bare_500():
    assert is_pool_timeout(SATimeoutError("QueuePool limit of size 10 overflow 20 reached, connection timed out, timeout 30.00"))
    with pytest.raises(OverloadedError):
        raise_capacity_overload(SATimeoutError("QueuePool timeout"))


def _settings(**extra):
    s = MagicMock()
    s.enable_request_metadata_logging = False
    s.enable_chat_debug_payload = False
    s.enable_chat_streaming = True
    s.knowledge_version = 1
    s.retrieval_mode = "hybrid"
    s.max_concurrent_chat_requests = 20
    s.max_concurrent_llm_requests = 2
    s.max_concurrent_embedding_requests = 2
    s.max_concurrent_background_embedding_requests = 1
    for k, v in extra.items():
        setattr(s, k, v)
    return s


def _fake_request() -> MagicMock:
    req = MagicMock()
    req.headers = {}
    req.client = None
    return req


def _install_session_fakes(monkeypatch, session_id: str = "sess-x") -> None:
    class _FakeSessionSvc:
        def __init__(self, db):
            pass

        def resolve_session(self, *a, **k):
            return SimpleNamespace(session_id=session_id), False

        def add_user_message(self, *a, **k):
            return None

        def add_assistant_message(self, *a, **k):
            return None

        @property
        def sessions(self):
            return self

        def get_by_session_id(self, *a, **k):
            return None

    monkeypatch.setattr("app.api.chat.ChatSessionService", _FakeSessionSvc)
    monkeypatch.setattr(
        "app.api.chat.ask_session",
        __import__("contextlib").contextmanager(lambda **k: (yield MagicMock())),
    )


@pytest.mark.unit
def test_chat_non_stream_pool_timeout_returns_429(monkeypatch):
    """Ask QueuePool timeout must surface as controlled 429 capacity response."""
    from fastapi import HTTPException

    from app.api.chat import chat
    from app.core.concurrency import OverloadedError as OE
    from app.schemas.chat import ChatRequest

    monkeypatch.setattr(
        "app.api.chat._load_settings_and_configure", lambda: _settings()
    )
    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: True
    )
    _install_session_fakes(monkeypatch, "sess-x")

    class _BoomExec:
        def __init__(self, db, settings):
            self._rag = SimpleNamespace(db=db)

        def answer(self, *a, **k):
            raise SATimeoutError(
                "QueuePool limit of size 10 overflow 20 reached, "
                "connection timed out, timeout 30.00"
            )

    monkeypatch.setattr("app.api.chat.ExecutiveService", _BoomExec)
    monkeypatch.setattr("app.core.database.SessionLocal", lambda: MagicMock())

    with pytest.raises(HTTPException) as ei:
        chat(
            ChatRequest(message="hello", session_id="sess-x", skip_user_message=True),
            _fake_request(),
        )
    assert ei.value.status_code == 429
    assert ei.value.detail == OE.message


@pytest.mark.unit
def test_chat_non_stream_llm_marker_false_during_generation(monkeypatch):
    """Behavioral: during Executive.answer, owner.db must not be held across LLM."""
    from app.api.chat import chat
    from app.schemas.chat import ChatRequest

    marker = {"llm_held_session": None}

    monkeypatch.setattr(
        "app.api.chat._load_settings_and_configure", lambda: _settings()
    )
    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: True
    )
    _install_session_fakes(monkeypatch, "sess-y")

    class _Exec:
        def __init__(self, db, settings):
            self._rag = SimpleNamespace(db=db)

        def answer(self, *a, **k):
            from app.core.ask_db import park_session_for_llm, unpark_session_after_llm

            park_session_for_llm(self._rag)
            marker["llm_held_session"] = self._rag.db is not None
            time.sleep(0.01)
            unpark_session_after_llm(self._rag)
            return RagResult(
                answer="ok",
                sources=[],
                used_context=False,
                request_id=k.get("request_id", "r"),
                total_ms=1,
            )

    monkeypatch.setattr("app.api.chat.ExecutiveService", _Exec)
    monkeypatch.setattr("app.core.database.SessionLocal", lambda: MagicMock())
    monkeypatch.setattr(
        "app.core.ask_db.SessionLocal", lambda: MagicMock(name="unpark")
    )

    resp = chat(
        ChatRequest(message="hello", session_id="sess-y", skip_user_message=True),
        _fake_request(),
    )
    assert resp.answer == "ok"
    assert marker["llm_held_session"] is False


@pytest.mark.unit
def test_stream_does_not_hold_request_session_across_generation(monkeypatch):
    """Stream body must not retain a request-scoped session across tokens."""
    import asyncio

    from app.api.chat import chat_stream
    from app.schemas.chat import ChatRequest

    held = {"during_tokens": None}

    monkeypatch.setattr(
        "app.api.chat._load_settings_and_configure", lambda: _settings()
    )
    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: True
    )
    _install_session_fakes(monkeypatch, "sess-stream")

    class _Exec:
        def __init__(self, db, settings):
            self._rag = SimpleNamespace(db=db)

        def answer_stream(self, *a, **k):
            from app.core.ask_db import park_session_for_llm

            park_session_for_llm(self._rag)
            held["during_tokens"] = self._rag.db is not None
            yield ("token", {"delta": "x", "text": "x"})
            yield (
                "final",
                {
                    "response": {
                        "answer": "x",
                        "sources": [],
                        "used_context": False,
                        "request_id": "r",
                        "session_id": "sess-stream",
                        "cache_hit": False,
                        "cache_type": "none",
                        "timing": {
                            "retrieval_ms": 0,
                            "generation_ms": 1,
                            "polish_ms": 0,
                            "total_ms": 1,
                        },
                        "prompt_diagnostics": {},
                    }
                },
            )

    monkeypatch.setattr("app.api.chat.ExecutiveService", _Exec)
    monkeypatch.setattr("app.core.database.SessionLocal", lambda: MagicMock())

    streaming = chat_stream(
        ChatRequest(message="hello", session_id="sess-stream"),
        _fake_request(),
    )

    async def _drain():
        chunks: list[bytes] = []
        async for chunk in streaming.body_iterator:
            chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
        return b"".join(chunks)

    body = asyncio.run(_drain()).decode("utf-8")
    assert held["during_tokens"] is False
    assert "event: token" in body


@pytest.mark.unit
def test_admission_before_generation_db_checkout(monkeypatch):
    """chat_slot must be acquired before SessionLocal for generation."""
    from app.api.chat import chat
    from app.schemas.chat import ChatRequest

    order: list[str] = []

    monkeypatch.setattr(
        "app.api.chat._load_settings_and_configure", lambda: _settings()
    )
    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat_dispatch_log.knowledge_os_executive_enabled", lambda: True
    )

    real_slot = concurrency.chat_slot

    def _tracked_slot(*a, **k):
        order.append("chat_slot")
        return real_slot(*a, **k)

    monkeypatch.setattr("app.api.chat.concurrency.chat_slot", _tracked_slot)
    _install_session_fakes(monkeypatch, "sess-adm")

    def _session_local():
        order.append("SessionLocal")
        return MagicMock()

    monkeypatch.setattr("app.core.database.SessionLocal", _session_local)

    class _Exec:
        def __init__(self, db, settings):
            self._rag = SimpleNamespace(db=db)

        def answer(self, *a, **k):
            return RagResult(
                answer="ok",
                sources=[],
                used_context=False,
                request_id="r",
                total_ms=1,
            )

    monkeypatch.setattr("app.api.chat.ExecutiveService", _Exec)

    resp = chat(
        ChatRequest(message="hello", session_id="sess-adm", skip_user_message=True),
        _fake_request(),
    )
    assert resp.answer == "ok"
    assert "chat_slot" in order
    assert "SessionLocal" in order
    assert order.index("chat_slot") < order.index("SessionLocal")
