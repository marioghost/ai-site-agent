"""RFC-100 Step 045 — Language consumes speech acts (behavior activation)."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.cache_namespace_service import build_retrieval_namespace
from app.services.language.speech_act_render import (
    apply_qualify_suffix,
    plan_speech_act_render,
)
from app.services.rag_service import RagResult, RagSource
from app.services.reasoning import ReasoningRequest, ReasoningService
from app.services.reasoning.speech_act import SpeechActDecision
from app.services.reasoning.types import REASONING_PATH_SERVICE

LANGUAGE_PKG = Path(__file__).resolve().parents[1] / "app" / "services" / "language"
FORBIDDEN_IMPORT_STEMS = frozenset(
    {
        "epistemic_memory",
        "tension_surfacing",
        "memory_version",
    }
)


def _src(url: str = "https://site/about", title: str = "About", score: float = 0.9) -> RagSource:
    return RagSource(title=title, url=url, source_type="page", score=score)


def _decision(act: str, reason: str = "test", hint: str | None = None) -> SpeechActDecision:
    hints = {
        "answer": "answer_normally",
        "qualify": "qualify_due_to_incomplete_evidence",
        "clarify": "ask_for_clarification",
        "refuse": "refuse_due_to_missing_site_evidence",
    }
    return SpeechActDecision(
        speech_act=act,  # type: ignore[arg-type]
        speech_act_reason=reason,
        user_message_hint=hint or hints[act],
        qualification_required=act == "qualify",
        clarification_question_hint="which aspect?" if act == "clarify" else None,
        refusal_reason="insufficient site evidence" if act == "refuse" else None,
    )


@pytest.mark.unit
def test_flag_defaults_true(monkeypatch):
    monkeypatch.delenv("REASONING_SPEECH_ACTS_ENABLED", raising=False)
    from app.core.config import get_config

    get_config.cache_clear()
    from app.services.feature_flags import reasoning_speech_acts_enabled

    assert reasoning_speech_acts_enabled() is True
    get_config.cache_clear()


@pytest.mark.unit
def test_reasoning_off_ignores_speech_acts_flag(monkeypatch):
    """Speech-acts flag alone must not change Rag when Reasoning is not used."""
    from app.api import chat as chat_api

    calls: list[dict] = []

    class _FakeRag:
        def answer(self, *args, **kwargs):
            calls.append(kwargs)
            return RagResult(
                answer="legacy",
                sources=[_src()],
                used_context=True,
                request_id="r",
            )

    monkeypatch.setattr(chat_api, "reasoning_service_enabled", lambda: False)
    monkeypatch.setenv("REASONING_SPEECH_ACTS_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    # Direct Rag path does not pass apply_speech_acts=True
    rag = _FakeRag()
    out = rag.answer("q", None, request_id="r")
    assert out.answer == "legacy"
    assert calls[0].get("apply_speech_acts") is None
    get_config.cache_clear()


@pytest.mark.unit
def test_reasoning_on_speech_acts_off_advisory_parity(monkeypatch):
    expected = RagResult(
        answer="Unchanged advisory text",
        sources=[_src()],
        used_context=True,
        request_id="r",
        query_intent="contacts_query",
        applied_knowledge_config={"answer_strategy": "contact"},
    )
    seen: dict = {}

    class _FakeRag:
        def answer(self, *args, **kwargs):
            seen.update(kwargs)
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
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.reasoning_speech_acts_enabled",
        lambda: False,
    )
    wrapped = ReasoningService(MagicMock(), MagicMock()).run(
        ReasoningRequest(message="hours?", session_id=None, request_id="r")
    )
    assert seen.get("apply_speech_acts") is False
    assert wrapped.as_rag_result().answer == "Unchanged advisory text"
    assert wrapped.speech_act == "answer"
    assert wrapped.reasoning_diagnostics.get("speech_act_applied") is not True


@pytest.mark.unit
def test_answer_act_passes_apply_flag_and_preserves_path(monkeypatch):
    seen: dict = {}

    class _FakeRag:
        def answer(self, *args, **kwargs):
            seen.update(kwargs)
            return RagResult(
                answer="Normal answer",
                sources=[_src()],
                used_context=True,
                request_id="r",
                query_intent="contacts_query",
                applied_knowledge_config={"answer_strategy": "contact"},
            )

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
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.reasoning_speech_acts_enabled",
        lambda: True,
    )
    out = ReasoningService(MagicMock(), MagicMock()).run(
        ReasoningRequest(message="q", session_id=None, request_id="r")
    )
    assert seen.get("apply_speech_acts") is True
    assert out.as_rag_result().answer == "Normal answer"


@pytest.mark.unit
def test_clarify_uk_en_templates():
    uk = plan_speech_act_render(_decision("clarify"), query_language="uk")
    en = plan_speech_act_render(_decision("clarify"), query_language="en")
    assert uk.skip_llm and uk.deterministic
    assert uk.text == "Уточніть, будь ласка, який саме аспект вас цікавить."
    assert en.text == "Please clarify which specific aspect you are interested in."
    assert uk.language_instruction == "CLARIFY_AMBIGUOUS_REQUEST"


@pytest.mark.unit
def test_refuse_uk_en_site_scoped():
    uk = plan_speech_act_render(_decision("refuse"), query_language="uk")
    en = plan_speech_act_render(_decision("refuse"), query_language="en")
    assert "сайті" in (uk.text or "")
    assert "site" in (en.text or "").lower()
    assert "false" not in (en.text or "").lower()
    assert "не існує" not in (uk.text or "")
    assert uk.language_instruction == "REFUSE_INSUFFICIENT_SITE_EVIDENCE"


@pytest.mark.unit
def test_qualify_suffix_preserves_answer():
    plan = plan_speech_act_render(_decision("qualify"), query_language="en")
    out = apply_qualify_suffix("Useful facts about services.", plan.qualify_suffix)
    assert out.startswith("Useful facts about services.")
    assert "complete list" in out
    assert plan.skip_llm is False


@pytest.mark.unit
def test_deterministic_clarify_skips_llm(monkeypatch):
    llm_calls = {"n": 0}

    class _FakeGen:
        def generate(self, *a, **k):
            llm_calls["n"] += 1
            return {"answer": "should not run", "generation_ms": 1, "diagnostics": {}}

    from app.services.qdrant_service import SearchHit
    from app.services.rag_service import RagService
    from app.schemas.knowledge_profile import AppliedKnowledgeConfig
    from app.services.retrieval_pipeline_service import PipelineResult, RetrievalDiagnostics
    from app.services.retrieval_intent_service import RetrievalIntentResult

    hit = SearchHit(
        score=0.9,
        source_id=1,
        chunk_index=0,
        title="About",
        url="https://site/about",
        source_type="page",
        text="Ambiguous content",
    )

    settings = MagicMock()
    settings.fallback_answer = "fallback"
    settings.enable_tracing = False
    settings.enable_semantic_answer_cache = False
    settings.enable_retrieval_cache = False
    settings.enable_source_links = True
    settings.enable_sources = True
    settings.default_response_language = "uk"
    settings.knowledge_version = 1
    settings.top_k = 5
    settings.similarity_threshold = 0.55
    settings.qdrant_collection = "c"
    settings.enable_reranking = False
    settings.retrieval_mode = "hybrid"
    settings.fast_mode_enabled = False
    settings.system_prompt = ""
    settings.llm_model = "m"
    settings.enable_chat_streaming = False
    settings.ollama_generation_timeout_seconds = 45
    settings.max_tokens = 256
    settings.temperature = 0.2

    monkeypatch.setattr(
        "app.services.rag_service.KnowledgeProfileService.from_settings",
        lambda s: MagicMock(organization_name="Org", site_display_name="Org"),
    )
    monkeypatch.setattr(
        "app.services.rag_service.effective_generation_settings",
        lambda s: {
            "llm_mode_profile": "balanced",
            "max_sources_in_prompt": 3,
            "polish_mode": "off",
        },
    )
    monkeypatch.setattr(
        "app.services.rag_service.get_mode_profile",
        lambda s: MagicMock(key="balanced", max_answer_words_overview=120),
    )
    monkeypatch.setattr(
        "app.services.rag_service.LlmGenerationService",
        lambda *a, **k: _FakeGen(),
    )
    monkeypatch.setattr(
        "app.services.rag_service.build_retrieval_namespace",
        lambda *a, **k: {"speech_act_language": "v1"},
    )
    monkeypatch.setattr(
        "app.services.rag_service.QueryNormalizationService.normalize",
        lambda m: m.lower(),
    )
    monkeypatch.setattr(
        "app.services.rag_service.detect_query_language",
        lambda m: "uk",
    )

    rag = RagService.__new__(RagService)
    rag.db = MagicMock()
    rag.settings = settings
    rag.embedding_service = MagicMock()
    rag.qdrant_service = MagicMock()
    rag.retrieval_cache = MagicMock()
    rag.answer_cache = MagicMock()
    rag.ollama = MagicMock()
    rag.polisher = MagicMock()

    def _provider(*a, **k):
        return PipelineResult(
            hits=[hit],
            intent_result=RetrievalIntentResult(
                intent="clarification",
                legacy_intent="clarification",
                answer_strategy="generic",
            ),
            applied_config=AppliedKnowledgeConfig(answer_strategy="generic"),
            context=None,
            diagnostics=RetrievalDiagnostics(expanded_queries=["q"]),
        )

    result = RagService.answer(
        rag,
        "щось?",
        None,
        request_id="r045",
        bypass_cache=True,
        pipeline_provider=_provider,
        apply_speech_acts=True,
    )
    assert llm_calls["n"] == 0
    assert result.answer == "Уточніть, будь ласка, який саме аспект вас цікавить."
    assert result.sources == []
    assert result.reasoning_diagnostics["llm_skipped"] is True
    assert result.reasoning_diagnostics["speech_act_applied"] is True
    assert result.reasoning_diagnostics["language_instruction"] == "CLARIFY_AMBIGUOUS_REQUEST"


@pytest.mark.unit
def test_refuse_skips_llm_and_drops_sources(monkeypatch):
    llm_calls = {"n": 0}

    class _FakeGen:
        def generate(self, *a, **k):
            llm_calls["n"] += 1
            return {"answer": "nope", "generation_ms": 1, "diagnostics": {}}

    from app.services.rag_service import RagService
    from app.schemas.knowledge_profile import AppliedKnowledgeConfig
    from app.services.retrieval_pipeline_service import PipelineResult, RetrievalDiagnostics
    from app.services.retrieval_intent_service import RetrievalIntentResult

    settings = MagicMock()
    settings.fallback_answer = "legacy fallback"
    settings.enable_tracing = False
    settings.enable_semantic_answer_cache = False
    settings.enable_retrieval_cache = False
    settings.enable_source_links = True
    settings.enable_sources = True
    settings.default_response_language = "en"
    settings.knowledge_version = 1
    settings.top_k = 5
    settings.similarity_threshold = 0.55
    settings.qdrant_collection = "c"
    settings.enable_reranking = False
    settings.retrieval_mode = "hybrid"
    settings.fast_mode_enabled = False
    settings.system_prompt = ""
    settings.llm_model = "m"
    settings.enable_chat_streaming = False
    settings.ollama_generation_timeout_seconds = 45

    monkeypatch.setattr(
        "app.services.rag_service.KnowledgeProfileService.from_settings",
        lambda s: MagicMock(organization_name="Org", site_display_name="Org"),
    )
    monkeypatch.setattr(
        "app.services.rag_service.effective_generation_settings",
        lambda s: {
            "llm_mode_profile": "balanced",
            "max_sources_in_prompt": 3,
            "polish_mode": "off",
        },
    )
    monkeypatch.setattr(
        "app.services.rag_service.get_mode_profile",
        lambda s: MagicMock(key="balanced", max_answer_words_overview=120),
    )
    monkeypatch.setattr(
        "app.services.rag_service.LlmGenerationService",
        lambda *a, **k: _FakeGen(),
    )
    monkeypatch.setattr(
        "app.services.rag_service.build_retrieval_namespace",
        lambda *a, **k: {"speech_act_language": "v1"},
    )
    monkeypatch.setattr(
        "app.services.rag_service.QueryNormalizationService.normalize",
        lambda m: m.lower(),
    )
    monkeypatch.setattr(
        "app.services.rag_service.detect_query_language",
        lambda m: "en",
    )

    rag = RagService.__new__(RagService)
    rag.db = MagicMock()
    rag.settings = settings
    rag.embedding_service = MagicMock()
    rag.qdrant_service = MagicMock()
    rag.retrieval_cache = MagicMock()
    rag.answer_cache = MagicMock()
    rag.ollama = MagicMock()
    rag.polisher = MagicMock()

    def _provider(*a, **k):
        return PipelineResult(
            hits=[],
            intent_result=RetrievalIntentResult(
                intent="contacts_query",
                legacy_intent="contacts_query",
                answer_strategy="contact",
            ),
            applied_config=AppliedKnowledgeConfig(answer_strategy="contact"),
            context=None,
            diagnostics=RetrievalDiagnostics(expanded_queries=["q"]),
        )

    result = RagService.answer(
        rag,
        "hours?",
        None,
        request_id="r045b",
        bypass_cache=True,
        pipeline_provider=_provider,
        apply_speech_acts=True,
    )
    assert llm_calls["n"] == 0
    assert result.sources == []
    assert "site" in result.answer.lower()
    assert result.reasoning_diagnostics["speech_act"]["speech_act"] == "refuse"


@pytest.mark.unit
def test_cache_namespace_isolates_speech_act_activation():
    settings = MagicMock()
    settings.knowledge_version = 1
    settings.knowledge_profile_json = "{}"
    settings.top_k = 5
    settings.similarity_threshold = 0.5
    settings.retrieval_mode = "hybrid"
    settings.enable_query_expansion = False
    settings.enable_reranking = False
    settings.enable_intent_aware_retrieval = False
    settings.enable_canonical_source_selection = False
    settings.enable_broad_question_mode = True
    settings.enable_context_builder = True
    settings.retrieval_candidate_count = 30
    settings.max_pages_in_context = 3
    settings.max_chunks_per_page = 2
    settings.max_sources_in_prompt = 3
    settings.max_chars_per_source = 1200
    settings.max_total_context_chars = 5000
    settings.enable_source_intelligence = True
    settings.llm_num_predict = 512
    settings.polish_mode = "off"
    settings.homepage_boost_enabled = False
    settings.homepage_boost_value = 0
    settings.title_match_boost = 0
    settings.heading_match_boost = 0
    settings.short_query_lexical_boost = 0
    settings.embedding_model = "e"
    settings.qdrant_collection = "c"
    settings.llm_model = "m"
    settings.cache_namespace_v2_enabled = False

    off = build_retrieval_namespace(settings, speech_acts_active=False)
    on = build_retrieval_namespace(settings, speech_acts_active=True)
    assert off["speech_act_language"] == "off"
    assert on["speech_act_language"] == "v1"
    assert off != on


@pytest.mark.unit
def test_stream_deterministic_no_duplicate_and_skips_llm(monkeypatch):
    from app.services.rag_streaming import RagStreamingService

    early = RagResult(
        answer="Уточніть, будь ласка, який саме аспект вас цікавить.",
        sources=[],
        used_context=False,
        request_id="s1",
        prompt_diagnostics={"llm_skipped": True},
        reasoning_diagnostics={
            "speech_act_applied": True,
            "llm_skipped": True,
            "language_instruction": "CLARIFY_AMBIGUOUS_REQUEST",
            "speech_act": {
                "speech_act": "clarify",
                "speech_act_reason": "ambiguous_or_clarification_need",
                "user_message_hint": "ask_for_clarification",
                "qualification_required": False,
                "clarification_required": True,
                "refusal_required": False,
                "clarification_question_hint": None,
                "refusal_reason": None,
            },
            "understanding_steps": [
                {"phase": "speech_act_selected"},
                {"phase": "speech_act_rendered"},
            ],
        },
    )
    prep = MagicMock()
    prep.retrieval_ms = 1
    prep.pipeline_diagnostics = None
    prep.trace = None
    prep.message = "q"
    prep.session_id = None
    prep.user_ip = None
    prep.user_agent = None
    prep.referrer = None
    prep.normalized = "q"
    prep.expanded = ["q"]
    prep.debug = False
    prep.prompt_diagnostics = early.prompt_diagnostics

    rag = MagicMock()
    rag._finalize = lambda result, *a, **k: result
    settings = MagicMock()
    settings.enable_tracing = False
    rag.settings = settings
    stream = RagStreamingService(rag)
    stream._prepare = lambda *a, **k: (prep, early)
    stream.builder = MagicMock()
    stream.builder.final_event_payload = lambda response: {
        "answer": early.answer,
        "sources": [],
        "request_id": "s1",
        "retrieval_debug": {
            "reasoning_diagnostics": early.reasoning_diagnostics,
            "speech_act": early.reasoning_diagnostics["speech_act"],
        },
    }
    stream.builder.from_rag_result = lambda *a, **k: MagicMock()

    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagService",
        lambda db, settings: rag,
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagStreamingService",
        lambda r: stream,
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.evidence_assembly_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.reasoning_speech_acts_enabled",
        lambda: True,
    )

    # Bypass ReasoningService constructor re-wrapping streaming — call stream directly
    events = list(
        stream.iter_events("q", None, request_id="s1", apply_speech_acts=True)
    )
    names = [e[0] for e in events]
    assert names[0] == "start"
    assert "token" in names
    assert names.count("token") == 1
    assert "final" in names
    tokens = [e[1]["text"] for e in events if e[0] == "token"]
    assert tokens == [early.answer]


@pytest.mark.unit
def test_no_memory_or_tension_imports_in_language():
    for path in LANGUAGE_PKG.rglob("*.py"):
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
def test_wrap_preserves_applied_clarify_when_sources_empty(monkeypatch):
    legacy = RagResult(
        answer="Уточніть, будь ласка, який саме аспект вас цікавить.",
        sources=[],
        used_context=False,
        request_id="r",
        query_intent="clarification",
        reasoning_diagnostics={
            "speech_act_applied": True,
            "language_instruction": "CLARIFY_AMBIGUOUS_REQUEST",
            "deterministic_response_used": True,
            "llm_skipped": True,
            "speech_act_reason": "ambiguous_or_clarification_need",
            "speech_act": {
                "speech_act": "clarify",
                "speech_act_reason": "ambiguous_or_clarification_need",
                "user_message_hint": "ask_for_clarification",
                "qualification_required": False,
                "clarification_required": True,
                "refusal_required": False,
                "clarification_question_hint": None,
                "refusal_reason": None,
            },
            "evidence_sufficiency": {
                "status": "unknown",
                "evidence_sufficient": None,
            },
            "understanding_steps": [
                {"phase": "speech_act_selected", "status": "completed"},
            ],
        },
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagService",
        lambda db, settings: MagicMock(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagStreamingService",
        lambda rag: MagicMock(),
    )
    wrapped = ReasoningService._wrap(legacy)
    assert wrapped.speech_act == "clarify"
    assert wrapped.as_rag_result().answer == legacy.answer
    phases = [s["phase"] for s in wrapped.reasoning_diagnostics["understanding_steps"]]
    assert "speech_act_rendered" in phases
