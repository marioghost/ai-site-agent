"""RFC-100 Step 044 — speech-act selection (advisory)."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.rag_service import RagResult, RagSource
from app.services.reasoning import (
    REASONING_PATH_SERVICE,
    ReasoningRequest,
    ReasoningService,
    assess_evidence_sufficiency,
    select_speech_act,
)
from app.services.reasoning.evidence_sufficiency import EvidenceSufficiencyAssessment
from app.services.reasoning.speech_act import SpeechActDecision

REASONING_PKG = Path(__file__).resolve().parents[1] / "app" / "services" / "reasoning"
FORBIDDEN_IMPORT_STEMS = frozenset(
    {
        "epistemic_memory",
        "tension_surfacing",
        "memory_version",
    }
)


def _src(url: str = "https://site/about", title: str = "About", score: float = 0.9) -> RagSource:
    return RagSource(title=title, url=url, source_type="page", score=score)


def _result(**overrides) -> RagResult:
    base = {
        "answer": "Grounded answer",
        "sources": [_src()],
        "used_context": True,
        "request_id": "req-044",
        "query_intent": "contacts_query",
        "applied_knowledge_config": {"answer_strategy": "contact"},
        "error_type": None,
    }
    base.update(overrides)
    return RagResult(**base)


def _decide(**result_overrides) -> SpeechActDecision:
    assessment = assess_evidence_sufficiency(_result(**result_overrides))
    need = result_overrides.get("query_intent")
    return select_speech_act(assessment, information_need=need)


@pytest.mark.unit
def test_sufficient_narrow_fact_answers():
    d = _decide(
        query_intent="contacts_query",
        applied_knowledge_config={"answer_strategy": "contact"},
    )
    assert d.speech_act == "answer"
    assert d.qualification_required is False
    assert d.clarification_required is False
    assert d.refusal_required is False
    assert d.user_message_hint == "answer_normally"


@pytest.mark.unit
def test_enumeration_completeness_risk_qualifies():
    d = _decide(
        query_intent="entity_overview",
        applied_knowledge_config={"answer_strategy": "list"},
        sources=[_src(), _src("https://site/services", "Services")],
    )
    assert d.speech_act == "qualify"
    assert d.qualification_required is True
    assert d.speech_act_reason == "completeness_risk"
    assert d.user_message_hint == "qualify_due_to_incomplete_evidence"


@pytest.mark.unit
def test_ambiguous_request_clarifies():
    d = _decide(query_intent="clarification")
    assert d.speech_act == "clarify"
    assert d.clarification_required is True
    assert d.clarification_question_hint is not None
    assert d.user_message_hint == "ask_for_clarification"


@pytest.mark.unit
def test_no_evidence_refuses():
    d = _decide(sources=[], used_context=False, answer="fallback")
    assert d.speech_act == "refuse"
    assert d.refusal_required is True
    assert d.refusal_reason is not None
    assert d.user_message_hint == "refuse_due_to_missing_site_evidence"


@pytest.mark.unit
def test_unknown_sufficiency_with_evidence_qualifies():
    # Need shape unclear → sufficiency unknown with evidence present
    d = _decide(
        query_intent="custom_need_shape",
        applied_knowledge_config={"answer_strategy": "custom_strategy"},
    )
    assert d.speech_act == "qualify"
    assert d.qualification_required is True
    assert d.speech_act_reason == "sufficiency_unknown_with_evidence"


@pytest.mark.unit
def test_invalid_provenance_refuses():
    d = _decide(sources=[_src(url="")], query_intent="contacts_query")
    assert d.speech_act == "refuse"
    assert d.refusal_required is True
    assert "provenance" in (d.speech_act_reason + (d.refusal_reason or "")).lower() or (
        d.speech_act_reason == "missing_source_provenance"
    )


@pytest.mark.unit
def test_reasoning_service_sets_speech_act_diagnostics_without_changing_answer(monkeypatch):
    expected = _result(answer="Unchanged answer text")

    class _FakeRag:
        def answer(self, *args, **kwargs):
            return expected

    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagService",
        lambda db, settings: _FakeRag(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagStreamingService",
        lambda rag: MagicMock(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.evidence_assembly_enabled",
        lambda: False,
    )

    wrapped = ReasoningService(MagicMock(), MagicMock()).run(
        ReasoningRequest(message="hours?", session_id=None, request_id="r")
    )
    out = wrapped.as_rag_result()
    assert out.answer == "Unchanged answer text"
    assert out.sources == expected.sources
    assert wrapped.speech_act == "answer"
    assert wrapped.speech_act_decision is not None
    assert wrapped.speech_act_decision.speech_act == "answer"
    assert wrapped.reasoning_diagnostics["speech_act"]["speech_act"] == "answer"
    assert wrapped.reasoning_diagnostics["qualification_required"] is False
    phases = [s["phase"] for s in wrapped.reasoning_diagnostics["understanding_steps"]]
    assert phases == [
        "information_need_assessed",
        "evidence_sufficiency_assessed",
        "speech_act_selected",
    ]


@pytest.mark.unit
def test_no_extra_retrieval_or_llm(monkeypatch):
    calls = {"answer": 0}

    class _FakeRag:
        def answer(self, *args, **kwargs):
            calls["answer"] += 1
            return _result()

    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagService",
        lambda db, settings: _FakeRag(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagStreamingService",
        lambda rag: MagicMock(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.evidence_assembly_enabled",
        lambda: False,
    )
    ReasoningService(MagicMock(), MagicMock()).run(
        ReasoningRequest(message="q", session_id=None, request_id="r")
    )
    assert calls["answer"] == 1


@pytest.mark.unit
def test_stream_preserves_event_order_and_stamps_speech_act(monkeypatch):
    class _FakeStream:
        def iter_events(self, *args, **kwargs):
            yield ("token", {"text": "Hi"})
            yield (
                "final",
                {
                    "answer": "Hi",
                    "sources": [
                        {"title": "A", "url": "https://site/a", "source_type": "page", "score": 0.9}
                    ],
                    "used_context": True,
                    "metadata": {
                        "query_intent": "contacts_query",
                        "applied_knowledge_config": {"answer_strategy": "contact"},
                    },
                    "retrieval_debug": {"hits": 1},
                    "request_id": "s1",
                },
            )

    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagService",
        lambda db, settings: MagicMock(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagStreamingService",
        lambda rag: _FakeStream(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.evidence_assembly_enabled",
        lambda: False,
    )
    events = list(
        ReasoningService(MagicMock(), MagicMock()).answer_stream(
            "q", None, request_id="s1"
        )
    )
    assert [e[0] for e in events] == ["token", "final"]
    final = events[1][1]
    assert final["answer"] == "Hi"
    assert final["reasoning_path"] == REASONING_PATH_SERVICE
    assert final["retrieval_debug"]["speech_act"]["speech_act"] == "answer"


@pytest.mark.unit
def test_no_epistemic_memory_imports_in_reasoning_package():
    for path in REASONING_PKG.rglob("*.py"):
        if path.name == "__pycache__":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    assert not FORBIDDEN_IMPORT_STEMS.intersection(parts), path
            elif isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                assert not FORBIDDEN_IMPORT_STEMS.intersection(parts), path


@pytest.mark.unit
def test_reasoning_does_not_own_final_language_strings():
    """Speech-act module must not embed final user-facing answer prose."""
    src = (REASONING_PKG / "speech_act.py").read_text(encoding="utf-8")
    # Hints are instruction codes, not rendered answers.
    assert "I'm sorry" not in src
    assert "Based on our website" not in src
    assert "user_message_hint" in src
    # Decision returns hints only — no long answer templates.
    assert "answer_normally" in src
    assert "refuse_due_to_missing_site_evidence" in src


@pytest.mark.unit
def test_select_speech_act_does_not_mutate_assessment():
    assessment = EvidenceSufficiencyAssessment(
        evidence_sufficient=True,
        sufficiency_status="sufficient",
        sufficiency_reasons=("selected_evidence_with_provenance",),
        evidence_count=1,
        independent_source_count=1,
        completeness_risk=False,
    )
    before = assessment.to_diagnostics()
    select_speech_act(assessment, information_need="contacts_query")
    assert assessment.to_diagnostics() == before


@pytest.mark.unit
def test_chat_debug_exposes_speech_act():
    from app.services.chat_response_builder import ChatResponseBuilder

    result = _result()
    result.reasoning_path = REASONING_PATH_SERVICE
    result.reasoning_diagnostics = {
        "reasoning_path": REASONING_PATH_SERVICE,
        "evidence_sufficiency": {"status": "sufficient"},
        "speech_act": {"speech_act": "answer", "speech_act_reason": "sufficient_scoped_evidence"},
        "qualification_required": False,
        "clarification_required": False,
        "refusal_required": False,
    }
    result.retrieval_debug = {"ok": True}
    debug = ChatResponseBuilder.build_retrieval_debug(result)
    assert debug is not None
    assert debug["speech_act"]["speech_act"] == "answer"
