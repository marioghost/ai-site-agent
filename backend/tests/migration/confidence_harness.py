"""Migration Confidence Gate harness (RFC-100 Step 042).

Instrumented dispatch paths for all Executive × Reasoning × Evidence Assembly
combinations. Counts subsystem invocations — no wall-clock benchmarks.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from app.models.settings import Settings
from app.services.context_builder_service import BuiltContext
from app.services.qdrant_service import SearchHit
from app.services.rag_service import RagResult
from app.services.retrieval_engine.pipeline import DocumentRetrievalResult
from app.services.retrieval_engine.types import RankedDocument, RetrievalQualityMetrics

_TESTS_DIR = Path(__file__).resolve().parents[1]
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from golden.parity_runner import (  # noqa: E402
    build_chat_response,
    build_fixture_rag_result,
    compare_structural_parity,
    load_golden_smoke,
    validate_golden_invariants,
)


@dataclass(frozen=True)
class FlagCombo:
    executive: bool
    reasoning: bool
    evidence_assembly: bool

    @property
    def label(self) -> str:
        return (
            f"exec={'ON' if self.executive else 'OFF'}"
            f"_rsn={'ON' if self.reasoning else 'OFF'}"
            f"_ea={'ON' if self.evidence_assembly else 'OFF'}"
        )


ALL_FLAG_COMBOS: tuple[FlagCombo, ...] = tuple(
    FlagCombo(e, r, ea)
    for e in (False, True)
    for r in (False, True)
    for ea in (False, True)
)

BASELINE_COMBO = FlagCombo(False, False, False)


@dataclass
class ExecutionCounters:
    rps_run: int = 0
    prepare_query: int = 0
    assemble_evidence: int = 0
    finalize_pipeline: int = 0
    ea_assemble: int = 0
    dfp: int = 0
    llm: int = 0
    context_build: int = 0
    answer_cache_lookup: int = 0
    answer_cache_store: int = 0
    retrieval_cache_lookup: int = 0
    retrieval_cache_store: int = 0
    response_builder: int = 0
    stream_pipeline: int = 0
    retrieval_debug_build: int = 0
    last_pipeline: dict[str, Any] = field(default_factory=dict)

    def as_metrics(self) -> dict[str, int]:
        return {
            "rps_run": self.rps_run,
            "prepare_query": self.prepare_query,
            "assemble_evidence": self.assemble_evidence,
            "finalize_pipeline": self.finalize_pipeline,
            "ea_assemble": self.ea_assemble,
            "dfp": self.dfp,
            "llm": self.llm,
            "context_build": self.context_build,
            "answer_cache_lookup": self.answer_cache_lookup,
            "answer_cache_store": self.answer_cache_store,
            "retrieval_cache_lookup": self.retrieval_cache_lookup,
            "retrieval_cache_store": self.retrieval_cache_store,
            "response_builder": self.response_builder,
            "stream_pipeline": self.stream_pipeline,
            "retrieval_debug_build": self.retrieval_debug_build,
        }

    @property
    def retrieval_executions(self) -> int:
        """One RPS.run OR one prepare+assemble+finalize chain."""
        if self.rps_run:
            return self.rps_run
        if self.prepare_query or self.assemble_evidence or self.finalize_pipeline:
            return max(self.prepare_query, self.assemble_evidence, self.finalize_pipeline)
        return 0


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


def make_dfp_result() -> DocumentRetrievalResult:
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


def pipeline_settings(*, context_builder: bool = False) -> Settings:
    return Settings(
        top_k=5,
        qdrant_collection="test_collection",
        enable_intent_aware_retrieval=False,
        enable_query_expansion=False,
        enable_broad_question_mode=False,
        enable_canonical_source_selection=False,
        enable_context_builder=context_builder,
        enable_semantic_answer_cache=False,
        enable_retrieval_cache=False,
        enable_tracing=False,
        enable_chat_logs=False,
        enable_trace_storage=False,
        enable_sources=True,
        enable_source_links=True,
        knowledge_version=3,
    )


def apply_flags(monkeypatch, combo: FlagCombo) -> None:
    monkeypatch.setattr(
        "app.api.chat.knowledge_os_executive_enabled",
        lambda: combo.executive,
    )
    monkeypatch.setattr(
        "app.api.chat.reasoning_service_enabled",
        lambda: combo.reasoning,
    )
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.evidence_assembly_enabled",
        lambda: combo.evidence_assembly,
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.evidence_assembly_enabled",
        lambda: combo.evidence_assembly,
    )
    monkeypatch.setattr(
        "app.services.executive.executive_service.reasoning_service_enabled",
        lambda: combo.reasoning,
    )


def install_instrumentation(monkeypatch, counters: ExecutionCounters) -> None:
    from app.services.retrieval_pipeline_service import RetrievalPipelineService

    dfp_result = make_dfp_result()
    fixed_context = BuiltContext(
        prompt_text="CONTEXT: About the org",
        blocks=[],
        total_chunks=1,
        page_count=1,
    )

    class _FakeDFP:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, **kwargs):
            counters.dfp += 1
            return dfp_result

    class _FakeLLM:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def generate(self, **kwargs):
            counters.llm += 1
            return {"answer": "Grounded answer", "generation_ms": 1, "diagnostics": {}}

    class _FakeCtxBuilder:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def build(self, *args, **kwargs):
            counters.context_build += 1
            report = MagicMock()
            report.to_dict.return_value = {"pages": 1}
            return fixed_context, report

    real_cache_get = None
    real_cache_store = None
    real_answer_lookup = None
    real_answer_store = None

    from app.services.answer_cache_service import AnswerCacheService
    from app.services.retrieval_cache_service import RetrievalCacheService

    real_cache_get = RetrievalCacheService.get
    real_cache_store = RetrievalCacheService.store
    real_answer_lookup = AnswerCacheService.lookup
    real_answer_store = AnswerCacheService.store

    def _cache_get(self, *args, **kwargs):
        counters.retrieval_cache_lookup += 1
        return None

    def _cache_store(self, *args, **kwargs):
        counters.retrieval_cache_store += 1

    def _answer_lookup(self, *args, **kwargs):
        counters.answer_cache_lookup += 1
        return None

    def _answer_store(self, *args, **kwargs):
        counters.answer_cache_store += 1

    real_rps_run = RetrievalPipelineService.run
    real_prepare = RetrievalPipelineService.prepare_query
    real_assemble = RetrievalPipelineService.assemble_evidence
    real_finalize = RetrievalPipelineService.finalize_pipeline

    def _run(self, *args, **kwargs):
        counters.rps_run += 1
        result = real_rps_run(self, *args, **kwargs)
        counters.last_pipeline = _pipeline_snapshot(result)
        return result

    def _prepare(self, *args, **kwargs):
        counters.prepare_query += 1
        return real_prepare(self, *args, **kwargs)

    def _assemble(self, *args, **kwargs):
        counters.assemble_evidence += 1
        return real_assemble(self, *args, **kwargs)

    def _finalize(self, *args, **kwargs):
        counters.finalize_pipeline += 1
        result = real_finalize(self, *args, **kwargs)
        counters.last_pipeline = _pipeline_snapshot(result)
        return result

    from app.services.evidence_assembly.evidence_assembly_service import (
        EvidenceAssemblyService,
    )

    real_ea_assemble = EvidenceAssemblyService.assemble

    def _ea_assemble(self, request):
        counters.ea_assemble += 1
        return real_ea_assemble(self, request)

    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.DocumentFirstRetrievalPipeline",
        _FakeDFP,
    )
    monkeypatch.setattr(
        "app.services.evidence_assembly.evidence_assembly_service.DocumentFirstRetrievalPipeline",
        _FakeDFP,
    )
    monkeypatch.setattr(RetrievalPipelineService, "run", _run)
    monkeypatch.setattr(RetrievalPipelineService, "prepare_query", _prepare)
    monkeypatch.setattr(RetrievalPipelineService, "assemble_evidence", _assemble)
    monkeypatch.setattr(RetrievalPipelineService, "finalize_pipeline", _finalize)
    monkeypatch.setattr(
        "app.services.evidence_assembly.evidence_assembly_service.EvidenceAssemblyService.assemble",
        _ea_assemble,
    )
    monkeypatch.setattr("app.services.rag_service.LlmGenerationService", _FakeLLM)
    monkeypatch.setattr(
        "app.services.retrieval_engine.context_builder.RetrievalContextBuilder",
        _FakeCtxBuilder,
    )
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.RetrievalContextBuilder",
        _FakeCtxBuilder,
    )
    monkeypatch.setattr(RetrievalCacheService, "get", _cache_get)
    monkeypatch.setattr(RetrievalCacheService, "store", _cache_store)
    monkeypatch.setattr(AnswerCacheService, "lookup", _answer_lookup)
    monkeypatch.setattr(AnswerCacheService, "store", _answer_store)
    monkeypatch.setattr(
        "app.services.embedding_service.EmbeddingService.embed_query",
        lambda self, *args, **kwargs: [0.1, 0.2, 0.3],
    )

    class _StreamChunk:
        def __init__(self, text: str = "", *, done: bool = False, stats=None) -> None:
            self.text = text
            self.done = done
            self.stats = stats

    def _fake_chat_stream(self, **kwargs):
        yield _StreamChunk(text="Grounded answer", done=True, stats=None)

    from app.services.ollama_service import OllamaService

    monkeypatch.setattr(OllamaService, "chat_stream", _fake_chat_stream)

    decision = MagicMock(enabled=False, reason="test", should_polish=False)
    monkeypatch.setattr("app.services.rag_service.evaluate_polish", lambda *a, **k: decision)

    class _Validator:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def validate(self, answer, **kwargs):
            return MagicMock(applied_fixes=[], warnings=[], cleaned_answer=answer)

    monkeypatch.setattr("app.services.rag_service.ResponseValidatorService", _Validator)
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


def _pipeline_snapshot(result) -> dict[str, Any]:
    diag = result.diagnostics
    ctx_text = result.context.prompt_text if result.context else ""
    return {
        "hit_urls": [h.url for h in result.hits],
        "hit_scores": [h.score for h in result.hits],
        "context_text": ctx_text,
        "quality_metrics": diag.quality_metrics,
        "pipeline_stages": diag.retrieval_pipeline_stages,
        "evidence_assembly_path": diag.evidence_assembly_path,
        "retrieval_coordinator": diag.retrieval_coordinator,
    }


def assert_single_execution(counters: ExecutionCounters, combo: FlagCombo) -> None:
    m = counters.as_metrics()
    assert counters.dfp == 1, f"{combo.label}: dfp={m}"
    assert counters.llm == 1, f"{combo.label}: llm={m}"
    if pipeline_settings().enable_context_builder:
        assert counters.context_build == 1, f"{combo.label}: context={m}"
    else:
        assert counters.context_build == 0, f"{combo.label}: context={m}"
    assert counters.answer_cache_lookup <= 1, f"{combo.label}: ans_cache_rd={m}"
    assert counters.answer_cache_store <= 1, f"{combo.label}: ans_cache_wr={m}"
    assert counters.retrieval_cache_lookup <= 1, f"{combo.label}: retr_cache_rd={m}"
    assert counters.retrieval_cache_store <= 1, f"{combo.label}: retr_cache_wr={m}"

    if combo.evidence_assembly:
        assert counters.ea_assemble == 1, f"{combo.label}: ea={m}"
    else:
        assert counters.ea_assemble == 0, f"{combo.label}: ea={m}"

    if combo.reasoning and combo.evidence_assembly:
        assert counters.rps_run == 0, f"{combo.label}: rps_run should be 0 when coordinated"
        assert counters.prepare_query == 1, f"{combo.label}: prepare={m}"
        assert counters.assemble_evidence == 1, f"{combo.label}: assemble={m}"
        assert counters.finalize_pipeline == 1, f"{combo.label}: finalize={m}"
    else:
        assert counters.rps_run == 1, f"{combo.label}: rps_run={m}"
        # run() composes stages internally — each stage counter may also be 1.
        assert counters.prepare_query >= 1, f"{combo.label}: prepare={m}"
        assert counters.assemble_evidence >= 1, f"{combo.label}: assemble={m}"
        assert counters.finalize_pipeline >= 1, f"{combo.label}: finalize={m}"


def run_non_stream(
    monkeypatch,
    combo: FlagCombo,
    counters: ExecutionCounters,
    *,
    message: str = "What is the org?",
    request_id: str = "mig-042",
) -> RagResult:
    from app.api.chat import _dispatch_non_stream_answer

    apply_flags(monkeypatch, combo)
    install_instrumentation(monkeypatch, counters)
    settings = pipeline_settings()
    return _dispatch_non_stream_answer(
        MagicMock(),
        settings,
        message,
        "session-042",
        request_id=request_id,
        bypass_cache=True,
    )


def run_stream(
    monkeypatch,
    combo: FlagCombo,
    counters: ExecutionCounters,
    *,
    message: str = "What is the org?",
    request_id: str = "mig-042-stream",
) -> list[tuple[str, dict]]:
    from app.api.chat import _dispatch_stream_events
    from app.services.rag_streaming import RagStreamingService

    apply_flags(monkeypatch, combo)
    install_instrumentation(monkeypatch, counters)

    original_iter = RagStreamingService.__dict__["iter_events"]

    def _count_stream(self, *args, **kwargs):
        counters.stream_pipeline += 1
        yield from original_iter(self, *args, **kwargs)

    monkeypatch.setattr(RagStreamingService, "iter_events", _count_stream)

    settings = pipeline_settings()
    return list(
        _dispatch_stream_events(
            MagicMock(),
            settings,
            message,
            "session-042",
            request_id=request_id,
            bypass_cache=True,
        )
    )


def parity_payload(result: RagResult) -> dict[str, Any]:
    response = build_chat_response(result)
    return {
        "answer": response["answer"],
        "sources": response.get("sources") or [],
        "used_context": response.get("used_context"),
        "cache_hit": response.get("cache_hit"),
        "cache_type": response.get("cache_type"),
        "error_type": response.get("error_type"),
        "response_keys": sorted(response.keys()),
    }


def assert_parity_against_baseline(baseline: dict[str, Any], current: dict[str, Any], combo: FlagCombo) -> None:
    assert current["answer"] == baseline["answer"], combo.label
    assert current["used_context"] == baseline["used_context"], combo.label
    assert current["cache_hit"] == baseline["cache_hit"], combo.label
    assert current["cache_type"] == baseline["cache_type"], combo.label
    assert current["error_type"] == baseline["error_type"], combo.label
    assert [s.get("url") for s in current["sources"]] == [
        s.get("url") for s in baseline["sources"]
    ], combo.label
    assert current["response_keys"] == baseline["response_keys"], combo.label


def run_golden_smoke_for_combo(monkeypatch, combo: FlagCombo) -> list[str]:
    """Return list of failure messages (empty = pass)."""
    golden = load_golden_smoke()
    failures: list[str] = []
    apply_flags(monkeypatch, combo)

    class _FixtureRag:
        def answer(self, message, session_id, **kwargs):
            item = next(q for q in golden["queries"] if q["query"] == message)
            return build_fixture_rag_result(golden, item)

    class _FixtureExecutive:
        def answer(self, message, session_id, **kwargs):
            item = next(q for q in golden["queries"] if q["query"] == message)
            return build_fixture_rag_result(golden, item)

    class _FixtureReasoning:
        def answer(self, message, session_id, **kwargs):
            item = next(q for q in golden["queries"] if q["query"] == message)
            result = build_fixture_rag_result(golden, item)
            result.reasoning_path = "reasoning_service"
            return result

    monkeypatch.setattr("app.api.chat.RagService", lambda db, s: _FixtureRag())
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, s: _FixtureExecutive()
    )
    monkeypatch.setattr(
        "app.api.chat.ReasoningService", lambda db, s: _FixtureReasoning()
    )

    from app.api.chat import _dispatch_non_stream_answer

    baseline_responses: dict[str, dict] = {}
    if combo != BASELINE_COMBO:
        apply_flags(monkeypatch, BASELINE_COMBO)
        for item in golden["queries"]:
            r = _dispatch_non_stream_answer(
                MagicMock(),
                MagicMock(),
                item["query"],
                "golden",
                request_id=f"base-{item['id']}",
            )
            baseline_responses[item["id"]] = build_chat_response(r)
        apply_flags(monkeypatch, combo)

    for item in golden["queries"]:
        try:
            result = _dispatch_non_stream_answer(
                MagicMock(),
                MagicMock(),
                item["query"],
                "golden",
                request_id=f"{combo.label}-{item['id']}",
            )
            response = build_chat_response(result)
            validate_golden_invariants(response, item, golden)
            if combo != BASELINE_COMBO:
                compare_structural_parity(
                    baseline_responses[item["id"]],
                    response,
                    query_id=f"{combo.label}:{item['id']}",
                )
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{combo.label}/{item['id']}: {exc}")
    return failures
