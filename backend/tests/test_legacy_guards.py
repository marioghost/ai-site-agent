"""RFC-100 Step 007 — guard tests for legacy boost/profile mechanisms.

Proves production chat routing does not invoke legacy boost tables, category_boost,
or legacy JSON weight columns. Uses runtime spies (monkeypatch) so CI fails if
someone wires these back into the hot path.

Scope: tests only — no production changes, no legacy code removal.
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from app.models.settings import Settings
from app.schemas.knowledge_profile import AppliedKnowledgeConfig
from app.services.content_category_service import category_boost as _category_boost_ref
from app.services.context_builder_service import BuiltContext, ContextBuilderService
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.ollama_service import OllamaChatResult, OllamaStreamChunk
from app.services.qdrant_service import SearchHit
from app.services.retrieval_intent_service import RetrievalIntentResult

LEGACY_JSON_FIELDS = frozenset(
    {
        "document_priorities_json",
        "intent_profiles_json",
        "scoring_weights_json",
    }
)


class LegacyJsonAccessTracker:
    """Proxy Settings that records runtime reads of legacy JSON columns."""

    def __init__(self, inner: Settings) -> None:
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "reads", [])

    def __getattr__(self, name: str):
        if name in LEGACY_JSON_FIELDS:
            self.reads.append(name)
        return getattr(self._inner, name)


def _minimal_chat_settings(**overrides) -> Settings:
    """Settings stub for unit chat-path guards (no PostgreSQL)."""
    base = dict(
        top_k=3,
        similarity_threshold=0.0,
        qdrant_collection="site",
        embedding_model="bge-m3",
        fallback_answer="Я не знайшов цієї інформації на сайті.",
        llm_model="test-model",
        system_prompt="sys",
        temperature=0.1,
        max_tokens=512,
        ollama_generation_timeout_seconds=90,
        enable_source_links=True,
        enable_sources=True,
        enable_semantic_answer_cache=False,
        enable_retrieval_cache=False,
        enable_reranking=False,
        enable_ukrainian_polish_pass=False,
        enable_chat_debug_payload=False,
        enable_tracing=False,
        enable_trace_storage=False,
        enable_chat_logs=False,
        knowledge_version=1,
        enable_broad_question_mode=False,
        enable_canonical_source_selection=False,
        enable_context_builder=True,
        enable_query_expansion=False,
        enable_intent_aware_retrieval=False,
        enable_chat_streaming=True,
        document_priorities_json='{"product_page": 0.99}',
        intent_profiles_json='{"overview": {"broken": true}',
        scoring_weights_json="NOT-JSON",
        knowledge_profile_json="",
    )
    base.update(overrides)
    return Settings(**base)


def _fake_pipeline_result() -> object:
    hit = SearchHit(
        score=0.8,
        source_id=1,
        chunk_index=0,
        title="About",
        url="https://example.com/about",
        source_type="page",
        text="About us content for guard test.",
    )
    context = ContextBuilderService().build([hit])
    intent = RetrievalIntentResult(intent="overview", legacy_intent="overview")

    @dataclass
    class FakePipeResult:
        hits: list[SearchHit]
        context: BuiltContext
        diagnostics: MagicMock
        intent_result: RetrievalIntentResult
        applied_config: AppliedKnowledgeConfig

    return FakePipeResult(
        hits=[hit],
        context=context,
        diagnostics=MagicMock(
            retrieval_debug=None,
            expanded_queries=[],
            to_dict=lambda: {},
        ),
        intent_result=intent,
        applied_config=AppliedKnowledgeConfig(detected_intent="overview"),
    )


class _FakeOllama:
    def embed(self, model: str, text: str, **kwargs) -> list[float]:
        return [0.1] * 8

    def embed_batch(self, model: str, texts: list[str], **kwargs) -> list[list[float]]:
        return [[0.1] * 8 for _ in texts]

    def chat(self, **kwargs) -> OllamaChatResult:
        return OllamaChatResult(content="Guard test answer from LLM.")

    def chat_stream(self, **kwargs):
        yield OllamaStreamChunk(text="Guard ", done=False)
        yield OllamaStreamChunk(
            text="stream answer.",
            done=True,
            stats=OllamaChatResult(content="Guard stream answer."),
        )


class _FakePipeline:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def run(self, *args, **kwargs):
        return _fake_pipeline_result()


def _install_chat_mocks(monkeypatch) -> None:
    monkeypatch.setattr("app.services.rag_service.OllamaService", _FakeOllama)
    monkeypatch.setattr("app.services.rag_service.RetrievalPipelineService", _FakePipeline)
    monkeypatch.setattr(
        "app.services.rag_streaming.RetrievalPipelineService", _FakePipeline
    )


def _install_legacy_spies(monkeypatch) -> dict[str, list]:
    calls = {"build_boost_tables": [], "category_boost": []}

    @staticmethod
    def _forbidden_build_boost_tables(profile, *args, **kwargs):
        calls["build_boost_tables"].append(profile)
        raise AssertionError(
            "build_boost_tables() must not run on the production chat path "
            "(RFC-100 Step 007)"
        )

    def _forbidden_category_boost(*args, **kwargs):
        calls["category_boost"].append((args, kwargs))
        raise AssertionError(
            "category_boost() must not run on the production chat path "
            "(RFC-100 Step 007)"
        )

    monkeypatch.setattr(
        KnowledgeProfileService,
        "build_boost_tables",
        _forbidden_build_boost_tables,
    )
    monkeypatch.setattr(
        "app.services.content_category_service.category_boost",
        _forbidden_category_boost,
    )
    return calls


def _run_non_stream_dispatch(
    monkeypatch,
    *,
    executive: bool,
    settings: Settings | LegacyJsonAccessTracker,
) -> object:
    from app.api.chat import _dispatch_non_stream_answer

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: executive,
    )
    monkeypatch.setattr(
        "app.api.chat.reasoning_service_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.services.executive.executive_service.reasoning_service_enabled",
        lambda: False,
    )
    return _dispatch_non_stream_answer(
        MagicMock(),
        settings,
        "What does the company do?",
        "guard-session",
        request_id=f"guard-non-stream-{'exec' if executive else 'legacy'}",
        bypass_cache=True,
    )


def _run_stream_dispatch(
    monkeypatch,
    *,
    executive: bool,
    settings: Settings | LegacyJsonAccessTracker,
) -> list[tuple[str, dict]]:
    from app.api.chat import _dispatch_stream_events
    from app.services.chat_response_builder import DiagnosticsCollector

    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: executive,
    )
    monkeypatch.setattr(
        "app.api.chat.reasoning_service_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.services.executive.executive_service.reasoning_service_enabled",
        lambda: False,
    )
    collector = DiagnosticsCollector(
        request_id=f"guard-stream-{'exec' if executive else 'legacy'}",
        session_id="guard-session",
    )
    return list(
        _dispatch_stream_events(
            MagicMock(),
            settings,
            "What does the company do?",
            "guard-session",
            request_id=collector.request_id,
            collector=collector,
            bypass_cache=True,
        )
    )


@pytest.mark.unit
@pytest.mark.parametrize("executive", [False, True], ids=["legacy", "executive"])
def test_non_stream_chat_does_not_call_build_boost_tables(monkeypatch, executive):
    """Production non-streaming chat must not invoke build_boost_tables()."""
    calls = _install_legacy_spies(monkeypatch)
    _install_chat_mocks(monkeypatch)
    settings = _minimal_chat_settings()

    result = _run_non_stream_dispatch(monkeypatch, executive=executive, settings=settings)

    assert result.answer
    assert result.used_context is True
    assert calls["build_boost_tables"] == []


@pytest.mark.unit
@pytest.mark.parametrize("executive", [False, True], ids=["legacy", "executive"])
def test_non_stream_chat_does_not_call_category_boost(monkeypatch, executive):
    """Production non-streaming chat must not invoke category_boost()."""
    calls = _install_legacy_spies(monkeypatch)
    _install_chat_mocks(monkeypatch)
    settings = _minimal_chat_settings()

    result = _run_non_stream_dispatch(monkeypatch, executive=executive, settings=settings)

    assert result.answer
    assert calls["category_boost"] == []


@pytest.mark.unit
@pytest.mark.parametrize("executive", [False, True], ids=["legacy", "executive"])
def test_stream_chat_does_not_call_legacy_boost_helpers(monkeypatch, executive):
    """Production streaming chat must not invoke build_boost_tables or category_boost."""
    calls = _install_legacy_spies(monkeypatch)
    _install_chat_mocks(monkeypatch)
    settings = _minimal_chat_settings()

    events = _run_stream_dispatch(monkeypatch, executive=executive, settings=settings)

    assert events[0][0] == "start"
    event_names = [name for name, _ in events]
    assert "final" in event_names
    assert calls["build_boost_tables"] == []
    assert calls["category_boost"] == []


@pytest.mark.unit
@pytest.mark.parametrize("executive", [False, True], ids=["legacy", "executive"])
def test_legacy_json_columns_not_read_during_non_stream_routing(monkeypatch, executive):
    """Legacy JSON weight columns are not required for production chat routing."""
    _install_legacy_spies(monkeypatch)
    _install_chat_mocks(monkeypatch)
    inner = _minimal_chat_settings()
    tracked = LegacyJsonAccessTracker(inner)

    result = _run_non_stream_dispatch(
        monkeypatch, executive=executive, settings=tracked
    )

    assert result.answer
    assert tracked.reads == []


@pytest.mark.unit
@pytest.mark.parametrize("executive", [False, True], ids=["legacy", "executive"])
def test_legacy_json_columns_not_read_during_stream_routing(monkeypatch, executive):
    """Legacy JSON weight columns are not read on the streaming chat path."""
    _install_legacy_spies(monkeypatch)
    _install_chat_mocks(monkeypatch)
    inner = _minimal_chat_settings()
    tracked = LegacyJsonAccessTracker(inner)

    events = _run_stream_dispatch(
        monkeypatch, executive=executive, settings=tracked
    )

    assert events[0][0] == "start"
    assert tracked.reads == []


@pytest.mark.unit
def test_legacy_boost_helpers_importable_without_runtime_use():
    """Harmless imports of legacy helpers must remain allowed (no import-time side effects)."""
    import app.services.content_category_service as ccs  # noqa: F401
    import app.services.knowledge_profile_service as kps  # noqa: F401

    assert callable(_category_boost_ref)
    assert callable(KnowledgeProfileService.build_boost_tables)
    assert ccs.category_boost is _category_boost_ref


@pytest.mark.unit
def test_hybrid_retrieval_service_module_deleted():
    """RFC-100 Step 010 — legacy HybridRetrievalService module must not exist."""
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]
    assert not (backend / "app/services/hybrid_retrieval_service.py").exists()


@pytest.mark.unit
def test_no_hybrid_retrieval_service_imports_in_app_or_tests():
    """RFC-100 Step 010 — no app/ or tests/ code may import HybridRetrievalService."""
    import ast
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for root_name in ("app", "tests"):
        for path in (backend / root_name).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "hybrid_retrieval" in alias.name:
                            offenders.append(f"{path.relative_to(backend)}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if "hybrid_retrieval" in module:
                        offenders.append(
                            f"{path.relative_to(backend)}: from {module} import ..."
                        )
                    for alias in node.names:
                        if alias.name == "HybridRetrievalService":
                            offenders.append(
                                f"{path.relative_to(backend)}: from {module} import HybridRetrievalService"
                            )
    assert offenders == [], (
        "HybridRetrievalService imports remain:\n" + "\n".join(offenders)
    )
