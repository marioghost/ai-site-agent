"""RFC-100 Step 039 — ReasoningService passthrough seam tests."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.rag_service import RagResult, RagSource
from app.services.reasoning import (
    REASONING_PATH_SERVICE,
    ReasoningRequest,
    ReasoningService,
)

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
REASONING_PKG = APP_ROOT / "services" / "reasoning"


def _fake_rag_result(**overrides) -> RagResult:
    base = {
        "answer": "Grounded answer",
        "sources": [
            RagSource(title="About", url="https://site/about", source_type="page", score=0.9)
        ],
        "used_context": True,
        "request_id": "req-039",
        "cache_hit": False,
        "cache_type": "none",
        "retrieval_ms": 5,
        "generation_ms": 10,
        "polish_ms": 0,
        "total_ms": 15,
        "query_intent": "overview",
        "error_type": None,
    }
    base.update(overrides)
    return RagResult(**base)


@pytest.mark.unit
def test_reasoning_service_enabled_defaults_true(monkeypatch):
    from app.core.config import get_config

    monkeypatch.delenv("REASONING_SERVICE_ENABLED", raising=False)
    get_config.cache_clear()
    from app.services.feature_flags import reasoning_service_enabled

    assert reasoning_service_enabled() is True
    get_config.cache_clear()


@pytest.mark.unit
def test_reasoning_service_enabled_reads_env(monkeypatch):
    from app.core.config import get_config

    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    get_config.cache_clear()
    from app.services.feature_flags import reasoning_service_enabled

    assert reasoning_service_enabled() is True
    get_config.cache_clear()


@pytest.mark.unit
def test_reasoning_service_enabled_kill_switch_false(monkeypatch):
    from app.core.config import get_config

    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "false")
    get_config.cache_clear()
    from app.services.feature_flags import reasoning_service_enabled

    assert reasoning_service_enabled() is False
    get_config.cache_clear()


@pytest.mark.unit
def test_reasoning_service_passthrough_preserves_answer_and_sources(monkeypatch):
    expected = _fake_rag_result()

    class _FakeRag:
        def answer(self, message, session_id, **kwargs):
            assert message == "What is the org?"
            assert kwargs["request_id"] == "req-039"
            return expected

    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagService",
        lambda db, settings: _FakeRag(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagStreamingService",
        lambda rag: MagicMock(),
    )

    svc = ReasoningService(MagicMock(), MagicMock())
    wrapped = svc.run(
        ReasoningRequest(
            message="What is the org?",
            session_id="s1",
            request_id="req-039",
        )
    )
    result = wrapped.as_rag_result()
    assert result.answer == expected.answer
    assert result.sources == expected.sources
    assert result.used_context is True
    assert result.query_intent == "overview"
    assert result.reasoning_path == REASONING_PATH_SERVICE
    assert wrapped.speech_act == "qualify"
    assert wrapped.information_need == "overview"
    # Overview/list-shaped need → advisory unknown with completeness risk (Step 043)
    # → qualify speech act (Step 044, advisory)
    assert wrapped.evidence_sufficient is None
    assert wrapped.sufficiency is not None
    assert wrapped.sufficiency.completeness_risk is True
    assert wrapped.clarification_needed is False
    assert wrapped.refusal_reason is None
    assert wrapped.speech_act_decision is not None
    assert wrapped.speech_act_decision.qualification_required is True
    assert "evidence_sufficiency" in wrapped.reasoning_diagnostics
    assert wrapped.reasoning_diagnostics["speech_act"]["speech_act"] == "qualify"


@pytest.mark.unit
def test_reasoning_service_propagates_errors_identically(monkeypatch):
    err = _fake_rag_result(
        answer="fallback",
        used_context=False,
        error_type="llm_timeout",
        sources=[],
    )

    class _FakeRag:
        def answer(self, *args, **kwargs):
            return err

    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagService",
        lambda db, settings: _FakeRag(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagStreamingService",
        lambda rag: MagicMock(),
    )
    result = ReasoningService(MagicMock(), MagicMock()).answer(
        "q", "s", request_id="r"
    )
    assert result.error_type == "llm_timeout"
    assert result.answer == "fallback"
    assert result.reasoning_path == REASONING_PATH_SERVICE


@pytest.mark.unit
def test_reasoning_stream_stamps_path_on_final(monkeypatch):
    class _FakeStreaming:
        def iter_events(self, *args, **kwargs):
            yield ("token", {"delta": "Hi"})
            yield ("final", {"answer": "Hi", "sources": [], "retrieval_debug": {}})

    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagService",
        lambda db, settings: MagicMock(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagStreamingService",
        lambda rag: _FakeStreaming(),
    )
    events = list(
        ReasoningService(MagicMock(), MagicMock()).answer_stream(
            "q", "s", request_id="r"
        )
    )
    assert events[0][0] == "token"
    assert events[1][0] == "final"
    assert events[1][1]["reasoning_path"] == REASONING_PATH_SERVICE
    assert events[1][1]["retrieval_debug"]["reasoning_path"] == REASONING_PATH_SERVICE
    assert events[1][1]["answer"] == "Hi"


@pytest.mark.unit
def test_dispatch_flag_off_does_not_use_reasoning(monkeypatch):
    from app.api.chat import _dispatch_non_stream_answer

    calls = {"rag": 0, "reasoning": 0, "executive": 0}

    class _FakeRag:
        def answer(self, *args, **kwargs):
            calls["rag"] += 1
            return _fake_rag_result()

    class _FakeReasoning:
        def __init__(self, *a, **k):
            calls["reasoning"] += 1

        def answer(self, *a, **k):
            raise AssertionError("ReasoningService must not run when flag OFF")

    class _FakeExecutive:
        def __init__(self, *a, **k):
            calls["executive"] += 1

        def answer(self, *a, **k):
            raise AssertionError("Executive must not run when executive flag OFF")

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    monkeypatch.setattr("app.api.chat.reasoning_service_enabled", lambda: False)
    monkeypatch.setattr("app.api.chat.RagService", lambda db, s: _FakeRag())
    monkeypatch.setattr("app.api.chat.ReasoningService", _FakeReasoning)
    monkeypatch.setattr("app.api.chat.ExecutiveService", _FakeExecutive)

    result = _dispatch_non_stream_answer(
        MagicMock(), MagicMock(), "q", "s", request_id="r"
    )
    assert calls == {"rag": 1, "reasoning": 0, "executive": 0}
    assert result.answer == "Grounded answer"
    assert result.reasoning_path is None


@pytest.mark.unit
def test_dispatch_reasoning_flag_on_uses_reasoning_service(monkeypatch):
    from app.api.chat import _dispatch_non_stream_answer

    calls = {"reasoning": 0, "rag": 0}

    class _FakeReasoning:
        def __init__(self, *a, **k):
            pass

        def answer(self, *args, **kwargs):
            calls["reasoning"] += 1
            return _fake_rag_result(reasoning_path=REASONING_PATH_SERVICE)

    class _FakeRag:
        def __init__(self, *a, **k):
            calls["rag"] += 1

        def answer(self, *a, **k):
            raise AssertionError("RagService must not be constructed by dispatch when reasoning ON")

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    monkeypatch.setattr("app.api.chat.reasoning_service_enabled", lambda: True)
    monkeypatch.setattr("app.api.chat.ReasoningService", _FakeReasoning)
    monkeypatch.setattr("app.api.chat.RagService", _FakeRag)

    result = _dispatch_non_stream_answer(
        MagicMock(), MagicMock(), "q", "s", request_id="r"
    )
    assert calls["reasoning"] == 1
    assert calls["rag"] == 0
    assert result.reasoning_path == REASONING_PATH_SERVICE


@pytest.mark.unit
def test_executive_routes_through_reasoning_when_flag_on(monkeypatch):
    from app.services.executive.executive_service import ExecutiveService

    calls = {"reasoning": 0, "rag_answer": 0}

    class _FakeReasoning:
        def __init__(self, *a, **k):
            pass

        def answer(self, *args, **kwargs):
            calls["reasoning"] += 1
            return _fake_rag_result(reasoning_path=REASONING_PATH_SERVICE)

    class _FakeRag:
        def answer(self, *args, **kwargs):
            calls["rag_answer"] += 1
            return _fake_rag_result()

    monkeypatch.setattr(
        "app.services.executive.executive_service.reasoning_service_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.executive.executive_service.ReasoningService",
        _FakeReasoning,
    )
    monkeypatch.setattr(
        "app.services.executive.executive_service.RagService",
        lambda db, s: _FakeRag(),
    )
    monkeypatch.setattr(
        "app.services.executive.executive_service.RagStreamingService",
        lambda rag: MagicMock(),
    )

    result = ExecutiveService(MagicMock(), MagicMock()).answer(
        "q", "s", request_id="r"
    )
    assert calls["reasoning"] == 1
    assert calls["rag_answer"] == 0
    assert result.reasoning_path == REASONING_PATH_SERVICE


@pytest.mark.unit
def test_executive_uses_rag_when_reasoning_flag_off(monkeypatch):
    from app.services.executive.executive_service import ExecutiveService

    calls = {"rag_answer": 0}

    class _FakeRag:
        def answer(self, *args, **kwargs):
            calls["rag_answer"] += 1
            return _fake_rag_result()

    monkeypatch.setattr(
        "app.services.executive.executive_service.reasoning_service_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.services.executive.executive_service.RagService",
        lambda db, s: _FakeRag(),
    )
    monkeypatch.setattr(
        "app.services.executive.executive_service.RagStreamingService",
        lambda rag: MagicMock(),
    )

    result = ExecutiveService(MagicMock(), MagicMock()).answer(
        "q", "s", request_id="r"
    )
    assert calls["rag_answer"] == 1
    assert result.reasoning_path is None


@pytest.mark.unit
def test_reasoning_package_epistemic_imports_limited_to_memory_assist():
    allowed = frozenset(
        {
            "memory_assist_types.py",
            "memory_assist_policy.py",
            "memory_request_builder.py",
        }
    )
    for path in REASONING_PKG.rglob("*.py"):
        if path.name in allowed or path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        for banned in (
            "epistemic_memory",
            "EpistemicClaim",
            "EvidenceLink",
            "ObservationRef",
            "TensionSurfacing",
            "MemoryVersionService",
            "KnowledgeVersionService",
        ):
            assert banned not in source, f"{path.name} contains {banned}"


@pytest.mark.unit
def test_reasoning_service_is_stateless_across_calls(monkeypatch):
    answers = iter([_fake_rag_result(answer="A"), _fake_rag_result(answer="B")])

    class _FakeRag:
        def answer(self, *args, **kwargs):
            return next(answers)

    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagService",
        lambda db, settings: _FakeRag(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagStreamingService",
        lambda rag: MagicMock(),
    )
    svc = ReasoningService(MagicMock(), MagicMock())
    first = svc.answer("q1", "s", request_id="1")
    second = svc.answer("q2", "s", request_id="2")
    assert first.answer == "A"
    assert second.answer == "B"
    # No cross-call state stored on the service:
    assert not hasattr(svc, "_last_answer")
    assert not hasattr(svc, "_cache")


@pytest.mark.unit
def test_chat_response_builder_includes_reasoning_path_in_debug():
    from app.models.settings import Settings
    from app.services.chat_response_builder import ChatResponseBuilder

    result = _fake_rag_result(reasoning_path=REASONING_PATH_SERVICE)
    result.retrieval_debug = {"hits": 1}
    debug = ChatResponseBuilder(Settings()).build_retrieval_debug(result)
    assert debug is not None
    assert debug["reasoning_path"] == REASONING_PATH_SERVICE


@pytest.mark.unit
def test_stream_dispatch_reasoning_flag_on(monkeypatch):
    from app.api.chat import _dispatch_stream_events

    seen = {"n": 0}

    class _FakeReasoning:
        def __init__(self, *a, **k):
            pass

        def answer_stream(self, *args, **kwargs):
            seen["n"] += 1
            yield ("final", {"answer": "ok", "reasoning_path": REASONING_PATH_SERVICE})

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    monkeypatch.setattr("app.api.chat.reasoning_service_enabled", lambda: True)
    monkeypatch.setattr("app.api.chat.ReasoningService", _FakeReasoning)

    events = list(
        _dispatch_stream_events(MagicMock(), MagicMock(), "q", "s", request_id="r")
    )
    assert seen["n"] == 1
    assert events[0][1]["reasoning_path"] == REASONING_PATH_SERVICE
