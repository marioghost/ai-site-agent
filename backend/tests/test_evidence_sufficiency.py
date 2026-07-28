"""RFC-100 Step 043 — evidence sufficiency assessment (advisory)."""
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
)
from app.services.reasoning.evidence_sufficiency import (
    EvidenceSufficiencyAssessment,
    assess_evidence_sufficiency,
)

REASONING_PKG = Path(__file__).resolve().parents[1] / "app" / "services" / "reasoning"


def _src(url: str = "https://site/about", title: str = "About", score: float = 0.9) -> RagSource:
    return RagSource(title=title, url=url, source_type="page", score=score)


def _result(**overrides) -> RagResult:
    base = {
        "answer": "Grounded answer",
        "sources": [_src()],
        "used_context": True,
        "request_id": "req-043",
        "query_intent": "contacts_query",
        "applied_knowledge_config": {"answer_strategy": "contact"},
        "error_type": None,
    }
    base.update(overrides)
    return RagResult(**base)


@pytest.mark.unit
def test_no_evidence_is_insufficient():
    a = assess_evidence_sufficiency(
        _result(sources=[], used_context=False, answer="fallback")
    )
    assert a.sufficiency_status == "insufficient"
    assert a.evidence_sufficient is False
    assert a.evidence_count == 0
    assert a.independent_source_count == 0
    assert "no_selected_evidence" in a.sufficiency_reasons or "context_not_used" in a.sufficiency_reasons


@pytest.mark.unit
def test_context_not_used_insufficient_even_with_sources():
    a = assess_evidence_sufficiency(
        _result(used_context=False, sources=[_src()])
    )
    assert a.sufficiency_status == "insufficient"
    assert a.evidence_sufficient is False
    assert "context_not_used" in a.sufficiency_reasons


@pytest.mark.unit
def test_narrow_factual_with_valid_evidence_sufficient():
    a = assess_evidence_sufficiency(
        _result(
            query_intent="contacts_query",
            applied_knowledge_config={"answer_strategy": "contact"},
        )
    )
    assert a.sufficiency_status == "sufficient"
    assert a.evidence_sufficient is True
    assert a.evidence_count == 1
    assert a.independent_source_count == 1
    assert a.completeness_risk is False


@pytest.mark.unit
def test_enumeration_without_completeness_has_risk():
    a = assess_evidence_sufficiency(
        _result(
            query_intent="entity_overview",
            applied_knowledge_config={"answer_strategy": "list"},
            sources=[_src(), _src("https://site/services", "Services")],
        )
    )
    assert a.sufficiency_status == "unknown"
    assert a.evidence_sufficient is None
    assert a.completeness_risk is True
    assert "enumeration_without_completeness_signal" in a.sufficiency_reasons


@pytest.mark.unit
def test_ambiguous_intent_is_unknown():
    a = assess_evidence_sufficiency(
        _result(query_intent="clarification", applied_knowledge_config={"answer_strategy": "generic"})
    )
    assert a.sufficiency_status == "unknown"
    assert a.evidence_sufficient is None
    assert a.completeness_risk is False
    assert "ambiguous_or_clarification_need" in a.sufficiency_reasons


@pytest.mark.unit
def test_empty_url_provenance_insufficient():
    a = assess_evidence_sufficiency(
        _result(sources=[_src(url="")], query_intent="contacts_query")
    )
    assert a.sufficiency_status == "insufficient"
    assert a.evidence_sufficient is False
    assert "missing_source_provenance" in a.sufficiency_reasons


@pytest.mark.unit
def test_duplicate_urls_count_as_one_independent_source():
    a = assess_evidence_sufficiency(
        _result(
            sources=[
                _src("https://site/about", "About A"),
                _src("https://site/about", "About B"),
                _src("https://site/team", "Team"),
            ],
            query_intent="contacts_query",
            applied_knowledge_config={"answer_strategy": "contact"},
        )
    )
    assert a.evidence_count == 3
    assert a.independent_source_count == 2


@pytest.mark.unit
def test_evidence_count_deterministic():
    sources = [_src(f"https://site/p{i}") for i in range(4)]
    a1 = assess_evidence_sufficiency(_result(sources=sources, query_intent="fact"))
    a2 = assess_evidence_sufficiency(_result(sources=list(sources), query_intent="fact"))
    assert a1.evidence_count == a2.evidence_count == 4
    assert a1.independent_source_count == a2.independent_source_count == 4


@pytest.mark.unit
def test_reasoning_service_wrap_sets_advisory_fields_without_changing_answer(monkeypatch):
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
    assert out.reasoning_path == REASONING_PATH_SERVICE
    assert wrapped.evidence_sufficient is True
    assert wrapped.sufficiency is not None
    assert wrapped.sufficiency.sufficiency_status == "sufficient"
    assert wrapped.speech_act == "answer"
    assert wrapped.speech_act_decision is not None
    assert "evidence_sufficiency" in wrapped.reasoning_diagnostics
    assert wrapped.reasoning_diagnostics["speech_act"]["speech_act"] == "answer"
    assert out.reasoning_diagnostics is not None
    assert out.reasoning_diagnostics["evidence_sufficiency"]["status"] == "sufficient"


@pytest.mark.unit
def test_no_extra_retrieval_or_llm_from_assessment(monkeypatch):
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
    ReasoningService(MagicMock(), MagicMock()).answer("q", None, request_id="r")
    assert calls["answer"] == 1


@pytest.mark.unit
def test_stream_final_stamps_sufficiency_without_answer_change(monkeypatch):
    events = [
        ("token", {"text": "Hi"}),
        (
            "final",
            {
                "response": {
                    "answer": "Hi",
                    "sources": [
                        {
                            "title": "About",
                            "url": "https://site/about",
                            "source_type": "page",
                            "score": 0.9,
                        }
                    ],
                    "used_context": True,
                    "metadata": {
                        "query_intent": "contacts_query",
                        "applied_knowledge_config": {"answer_strategy": "contact"},
                    },
                },
                "retrieval_debug": {"selected_chunks": 1},
            },
        ),
    ]

    class _FakeStream:
        def iter_events(self, *args, **kwargs):
            yield from events

    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.evidence_assembly_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagService",
        lambda db, settings: MagicMock(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagStreamingService",
        lambda rag: _FakeStream(),
    )
    out = list(
        ReasoningService(MagicMock(), MagicMock()).answer_stream(
            "q", None, request_id="r"
        )
    )
    assert [e[0] for e in out] == ["token", "final"]
    final = out[-1][1]
    assert final["response"]["answer"] == "Hi"
    assert final["reasoning_path"] == REASONING_PATH_SERVICE
    assert final["retrieval_debug"]["evidence_sufficiency"]["status"] == "sufficient"


@pytest.mark.unit
def test_no_version_mutation():
    settings = MagicMock()
    settings.knowledge_version = 11
    settings.memory_version = 5
    result = _result()
    assess_evidence_sufficiency(result)
    assert settings.knowledge_version == 11
    assert settings.memory_version == 5
    assert result.answer == "Grounded answer"


@pytest.mark.unit
def test_reasoning_package_no_epistemic_memory_imports():
    allowed = frozenset(
        {
            "memory_assist_types.py",
            "memory_assist_policy.py",
            "memory_request_builder.py",
        }
    )
    for path in REASONING_PKG.rglob("*.py"):
        if path.name in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "epistemic" not in mod.lower()
                for alias in node.names:
                    assert alias.name not in {
                        "EpistemicMemoryService",
                        "ClaimRecord",
                        "TensionView",
                    }


@pytest.mark.unit
def test_assessment_dataclass_is_frozen():
    a = assess_evidence_sufficiency(_result(sources=[]))
    assert isinstance(a, EvidenceSufficiencyAssessment)
    with pytest.raises(Exception):
        a.evidence_count = 99  # type: ignore[misc]


@pytest.mark.unit
def test_chat_response_builder_includes_sufficiency_diagnostics():
    from app.services.chat_response_builder import ChatResponseBuilder

    result = _result()
    result.reasoning_path = REASONING_PATH_SERVICE
    result.reasoning_diagnostics = {
        "reasoning_path": REASONING_PATH_SERVICE,
        "evidence_sufficiency": {"status": "sufficient", "evidence_count": 1},
    }
    result.retrieval_debug = {"selected_chunks": 1}
    debug = ChatResponseBuilder.build_retrieval_debug(result)
    assert debug is not None
    assert debug["evidence_sufficiency"]["status"] == "sufficient"
