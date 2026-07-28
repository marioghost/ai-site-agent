"""RFC-100 Step 041 — RPS thinning + Reasoning/EA flag matrix."""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models.settings import Settings
from app.services.evidence_assembly import (
    EVIDENCE_ASSEMBLY_PATH_LEGACY,
    EVIDENCE_ASSEMBLY_PATH_SERVICE,
)
from app.services.qdrant_service import SearchHit
from app.services.rag_service import RagResult
from app.services.reasoning import ReasoningService
from app.services.retrieval_engine.pipeline import DocumentRetrievalResult
from app.services.retrieval_engine.types import RankedDocument, RetrievalQualityMetrics
from app.services.retrieval_pipeline_service import (
    RETRIEVAL_COORDINATOR_RAG,
    RETRIEVAL_COORDINATOR_REASONING,
    RetrievalPipelineService,
)

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
REASONING_PKG = APP_ROOT / "services" / "reasoning"
EA_PKG = APP_ROOT / "services" / "evidence_assembly"
RPS_PATH = APP_ROOT / "services" / "retrieval_pipeline_service.py"
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))


def _hit(url: str = "https://site/about") -> SearchHit:
    return SearchHit(
        score=0.9,
        source_id=10,
        chunk_index=0,
        title="About",
        url=url,
        source_type="page",
        text="About the org",
    )


def _doc(hit: SearchHit | None = None) -> RankedDocument:
    h = hit or _hit()
    return RankedDocument(
        source_id=h.source_id,
        url=h.url,
        title=h.title or "About",
        document_type="generic_page",
        representative_chunk=h,
    )


def _dfp_result() -> DocumentRetrievalResult:
    hit = _hit()
    selected = _doc(hit)
    return DocumentRetrievalResult(
        selected_hits=[hit],
        all_documents=[selected],
        selected_documents=[selected],
        rejected_documents=[],
        quality_metrics=RetrievalQualityMetrics(
            chunks_retrieved=1,
            documents_found=1,
            documents_after_deduplication=1,
            documents_after_reranking=1,
            documents_sent_to_llm=1,
        ),
        pipeline_stages=[{"stage": "chunk_retrieval", "status": "completed"}],
        chunk_debug={"match_query": "about"},
        retrieval_ms=11,
    )


def _pipeline_settings() -> Settings:
    return Settings(
        top_k=5,
        qdrant_collection="test_collection",
        enable_intent_aware_retrieval=False,
        enable_query_expansion=False,
        enable_broad_question_mode=False,
        enable_canonical_source_selection=False,
        enable_context_builder=False,
        enable_semantic_answer_cache=False,
        enable_retrieval_cache=False,
        enable_tracing=False,
        enable_chat_logs=False,
        enable_trace_storage=False,
        enable_sources=True,
        enable_source_links=True,
    )


def _install_fake_dfp(monkeypatch, counter: dict):
    class _FakeDFP:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, **kwargs):
            counter["dfp"] = counter.get("dfp", 0) + 1
            return _dfp_result()

    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.DocumentFirstRetrievalPipeline",
        _FakeDFP,
    )
    monkeypatch.setattr(
        "app.services.evidence_assembly.evidence_assembly_service.DocumentFirstRetrievalPipeline",
        _FakeDFP,
    )


def _install_fake_llm(monkeypatch, counter: dict, answer: str = "Grounded answer"):
    class _FakeGen:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def generate(self, **kwargs):
            counter["llm"] = counter.get("llm", 0) + 1
            return {"answer": answer, "generation_ms": 1, "diagnostics": {}}

    monkeypatch.setattr("app.services.rag_service.LlmGenerationService", _FakeGen)


def _patch_rag_language_side_effects(monkeypatch):
    decision = MagicMock(enabled=False, reason="test", should_polish=False)
    monkeypatch.setattr(
        "app.services.rag_service.evaluate_polish",
        lambda *a, **k: decision,
    )
    monkeypatch.setattr(
        "app.services.rag_service.SourceFormattingService.format",
        lambda hits: [
            type(
                "S",
                (),
                {
                    "title": h.title,
                    "url": h.url,
                    "source_type": h.source_type,
                    "score": h.score,
                },
            )()
            for h in hits
        ],
    )

    class _Validator:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def validate(self, answer, **kwargs):
            return MagicMock(applied_fixes=[], warnings=[], cleaned_answer=answer)

    monkeypatch.setattr("app.services.rag_service.ResponseValidatorService", _Validator)


def _capture_finalize(monkeypatch, captured: dict):
    real_finalize = RetrievalPipelineService.finalize_pipeline

    def _wrapped(self, prepared, doc_result, **kwargs):
        result = real_finalize(self, prepared, doc_result, **kwargs)
        captured["diag"] = result.diagnostics
        captured["hits"] = result.hits
        captured["context"] = result.context
        return result

    monkeypatch.setattr(RetrievalPipelineService, "finalize_pipeline", _wrapped)


@pytest.mark.unit
@pytest.mark.parametrize(
    "reasoning_on,ea_on,expect_ea_path,expect_coordinator",
    [
        (False, False, EVIDENCE_ASSEMBLY_PATH_LEGACY, RETRIEVAL_COORDINATOR_RAG),
        (True, False, EVIDENCE_ASSEMBLY_PATH_LEGACY, RETRIEVAL_COORDINATOR_RAG),
        (False, True, EVIDENCE_ASSEMBLY_PATH_SERVICE, RETRIEVAL_COORDINATOR_RAG),
        (True, True, EVIDENCE_ASSEMBLY_PATH_SERVICE, RETRIEVAL_COORDINATOR_REASONING),
    ],
)
def test_flag_matrix_one_retrieval_one_llm(
    monkeypatch,
    reasoning_on,
    ea_on,
    expect_ea_path,
    expect_coordinator,
):
    counter: dict = {"dfp": 0, "llm": 0}
    _install_fake_dfp(monkeypatch, counter)
    _install_fake_llm(monkeypatch, counter)
    _patch_rag_language_side_effects(monkeypatch)
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.evidence_assembly_enabled",
        lambda: ea_on,
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.evidence_assembly_enabled",
        lambda: ea_on,
    )

    settings = _pipeline_settings()
    db = MagicMock()
    captured: dict = {}
    _capture_finalize(monkeypatch, captured)

    if reasoning_on:
        result = ReasoningService(db, settings).answer(
            "What is the org?", "s1", request_id="req-041"
        )
        assert result.reasoning_path == "reasoning_service"
    else:
        from app.services.rag_service import RagService

        result = RagService(db, settings).answer(
            "What is the org?", "s1", request_id="req-041"
        )

    assert result.answer == "Grounded answer"
    assert captured["diag"].evidence_assembly_path == expect_ea_path
    assert captured["diag"].retrieval_coordinator == expect_coordinator
    assert [h.url for h in captured["hits"]] == ["https://site/about"]
    assert counter["dfp"] == 1
    assert counter["llm"] == 1


@pytest.mark.unit
def test_flag_matrix_hit_and_context_parity(monkeypatch):
    settings = _pipeline_settings()
    results = {}
    for reasoning_on, ea_on in [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ]:
        counter: dict = {"dfp": 0}
        _install_fake_dfp(monkeypatch, counter)
        monkeypatch.setattr(
            "app.services.retrieval_pipeline_service.evidence_assembly_enabled",
            lambda ea=ea_on: ea,
        )
        rps = RetrievalPipelineService(MagicMock(), settings, MagicMock(), MagicMock())
        if reasoning_on and ea_on:
            prepared = rps.prepare_query("q", "q")
            docs = rps.assemble_evidence(prepared)
            pipe = rps.finalize_pipeline(
                prepared,
                docs,
                retrieval_coordinator=RETRIEVAL_COORDINATOR_REASONING,
            )
        else:
            pipe = rps.run("q", "q")
        results[(reasoning_on, ea_on)] = (
            [h.url for h in pipe.hits],
            pipe.diagnostics.quality_metrics,
            pipe.diagnostics.retrieval_pipeline_stages,
            counter["dfp"],
        )

    baseline = results[(False, False)]
    for key, value in results.items():
        assert value[0] == baseline[0], key
        assert value[1] == baseline[1], key
        assert value[2] == baseline[2], key
        assert value[3] == 1, key


@pytest.mark.unit
def test_both_off_uses_rps_run_not_reasoning_coordinator(monkeypatch):
    counter = {"dfp": 0}
    _install_fake_dfp(monkeypatch, counter)
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.evidence_assembly_enabled",
        lambda: False,
    )
    result = RetrievalPipelineService(
        MagicMock(), _pipeline_settings(), MagicMock(), MagicMock()
    ).run("q", "q")
    assert result.diagnostics.retrieval_coordinator == RETRIEVAL_COORDINATOR_RAG
    assert result.diagnostics.evidence_assembly_path == EVIDENCE_ASSEMBLY_PATH_LEGACY
    assert counter["dfp"] == 1


@pytest.mark.unit
def test_reasoning_both_on_coordinates_stages_exactly_once(monkeypatch):
    stages = {"prepare": 0, "assemble": 0, "finalize": 0, "dfp": 0, "llm": 0}
    _install_fake_dfp(monkeypatch, stages)
    _install_fake_llm(monkeypatch, stages)
    _patch_rag_language_side_effects(monkeypatch)

    real_prepare = RetrievalPipelineService.prepare_query
    real_assemble = RetrievalPipelineService.assemble_evidence
    real_finalize = RetrievalPipelineService.finalize_pipeline

    monkeypatch.setattr(
        RetrievalPipelineService,
        "prepare_query",
        lambda self, *a, **k: (stages.__setitem__("prepare", stages["prepare"] + 1) or real_prepare(self, *a, **k)),
    )
    monkeypatch.setattr(
        RetrievalPipelineService,
        "assemble_evidence",
        lambda self, *a, **k: (
            stages.__setitem__("assemble", stages["assemble"] + 1)
            or real_assemble(self, *a, **k)
        ),
    )
    monkeypatch.setattr(
        RetrievalPipelineService,
        "finalize_pipeline",
        lambda self, *a, **k: (
            stages.__setitem__("finalize", stages["finalize"] + 1)
            or real_finalize(self, *a, **k)
        ),
    )
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.evidence_assembly_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.evidence_assembly_enabled",
        lambda: True,
    )

    ReasoningService(MagicMock(), _pipeline_settings()).answer(
        "q", None, request_id="r"
    )
    assert stages["prepare"] == 1
    assert stages["assemble"] == 1
    assert stages["finalize"] == 1
    assert stages["dfp"] == 1
    assert stages["llm"] == 1


@pytest.mark.unit
def test_error_propagation_parity_reasoning_path(monkeypatch):
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.evidence_assembly_enabled",
        lambda: False,
    )

    class _BoomRag:
        def answer(self, *args, **kwargs):
            return RagResult(
                answer="fallback",
                sources=[],
                used_context=False,
                request_id="r",
                error_type="llm_timeout",
            )

    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagService",
        lambda db, settings: _BoomRag(),
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RagStreamingService",
        lambda rag: MagicMock(),
    )
    result = ReasoningService(MagicMock(), MagicMock()).answer(
        "q", None, request_id="r"
    )
    assert result.error_type == "llm_timeout"
    assert result.answer == "fallback"


@pytest.mark.unit
def test_no_version_mutation_during_coordination(monkeypatch):
    counter: dict = {}
    _install_fake_dfp(monkeypatch, counter)
    settings = _pipeline_settings()
    settings.knowledge_version = 9
    settings.memory_version = 4
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.evidence_assembly_enabled",
        lambda: True,
    )
    rps = RetrievalPipelineService(MagicMock(), settings, MagicMock(), MagicMock())
    prepared = rps.prepare_query("q", "q")
    docs = rps.assemble_evidence(prepared)
    rps.finalize_pipeline(
        prepared, docs, retrieval_coordinator=RETRIEVAL_COORDINATOR_REASONING
    )
    assert settings.knowledge_version == 9
    assert settings.memory_version == 4


@pytest.mark.unit
def test_reasoning_and_ea_have_no_epistemic_imports():
    forbidden_modules = ("epistemic_memory", "EpistemicMemoryService")
    allowed_reasoning = frozenset(
        {
            "memory_assist_types.py",
            "memory_assist_policy.py",
            "memory_request_builder.py",
        }
    )
    for pkg in (REASONING_PKG, EA_PKG):
        for path in pkg.rglob("*.py"):
            if pkg == REASONING_PKG and path.name in allowed_reasoning:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for bad in forbidden_modules:
                        assert bad not in mod
                    for alias in node.names:
                        assert alias.name not in forbidden_modules


@pytest.mark.unit
def test_ea_has_no_prompt_llm_imports():
    bad = ("llm_generation", "prompt_builder", "answer_polish", "ollama_service")
    for path in EA_PKG.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in bad:
            assert token not in text


@pytest.mark.unit
def test_reasoning_service_stateless_coordinator(monkeypatch):
    counter: dict = {"dfp": 0, "llm": 0}
    _install_fake_dfp(monkeypatch, counter)
    _install_fake_llm(monkeypatch, counter)
    _patch_rag_language_side_effects(monkeypatch)
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.evidence_assembly_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.evidence_assembly_enabled",
        lambda: True,
    )
    svc = ReasoningService(MagicMock(), _pipeline_settings())
    svc.answer("a", None, request_id="1")
    svc.answer("b", None, request_id="2")
    assert not hasattr(svc, "_last_pipeline")
    assert counter["dfp"] == 2
    assert counter["llm"] == 2


@pytest.mark.unit
def test_rps_run_is_thin_coordinator():
    source = RPS_PATH.read_text(encoding="utf-8")
    start = source.index("def run(")
    end = source.index("def prepare_query(")
    run_body = source[start:end]
    assert "prepare_query(" in run_body
    assert "assemble_evidence(" in run_body
    assert "finalize_pipeline(" in run_body
    assert "DocumentFirstRetrievalPipeline(" not in run_body
    assert "RetrievalContextBuilder(" not in run_body
    assert run_body.count("\n") < 45


@pytest.mark.unit
def test_streaming_parity_both_flags_on(monkeypatch):
    """Streaming uses the same Reasoning coordinator injection."""
    events = [("token", {"text": "Hi"}), ("final", {"answer": "Hi", "sources": []})]

    class _FakeStream:
        def iter_events(self, *args, **kwargs):
            assert kwargs.get("pipeline_provider") is not None
            yield from events

    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.evidence_assembly_enabled",
        lambda: True,
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
    assert out[0][0] == "token"
    assert out[-1][0] == "final"
    assert out[-1][1]["reasoning_path"] == "reasoning_service"


@pytest.mark.unit
def test_golden_parity_with_both_migration_flags_on(monkeypatch):
    from app.api.chat import _dispatch_non_stream_answer
    from golden.parity_runner import (
        build_chat_response,
        build_fixture_rag_result,
        compare_structural_parity,
        load_golden_smoke,
        validate_golden_invariants,
    )

    golden = load_golden_smoke()
    item = golden["queries"][0]
    fixture = build_fixture_rag_result(golden, item)

    class _FakeReasoning:
        def answer(self, *args, **kwargs):
            fixture.reasoning_path = "reasoning_service"
            return fixture

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    monkeypatch.setattr("app.api.chat.reasoning_service_enabled", lambda: True)
    monkeypatch.setattr(
        "app.api.chat.ReasoningService", lambda db, settings: _FakeReasoning()
    )
    monkeypatch.setenv("EVIDENCE_ASSEMBLY_ENABLED", "true")

    result = _dispatch_non_stream_answer(
        MagicMock(),
        MagicMock(),
        item["query"],
        "golden-session",
        request_id=f"golden-{item['id']}",
    )
    response = build_chat_response(result)
    fixture_response = build_chat_response(fixture)
    validate_golden_invariants(response, item, golden)
    compare_structural_parity(response, fixture_response, query_id=item["id"])
