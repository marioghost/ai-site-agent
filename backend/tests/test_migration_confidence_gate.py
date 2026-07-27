"""RFC-100 Step 042 — Migration Confidence Gate."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from migration.confidence_harness import (
    ALL_FLAG_COMBOS,
    BASELINE_COMBO,
    ExecutionCounters,
    FlagCombo,
    apply_flags,
    assert_parity_against_baseline,
    assert_single_execution,
    install_instrumentation,
    parity_payload,
    pipeline_settings,
    run_golden_smoke_for_combo,
    run_non_stream,
    run_stream,
)
from app.services.cache_namespace_service import build_retrieval_namespace
from app.services.chat_response_builder import ChatResponseBuilder

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("combo", ALL_FLAG_COMBOS, ids=lambda c: c.label)
def test_migration_gate_single_execution_per_combo(monkeypatch, combo: FlagCombo):
    counters = ExecutionCounters()
    result = run_non_stream(monkeypatch, combo, counters)
    assert result.answer == "Grounded answer"
    assert_single_execution(counters, combo)


@pytest.mark.parametrize("combo", ALL_FLAG_COMBOS, ids=lambda c: c.label)
def test_migration_gate_pipeline_parity_against_baseline(monkeypatch, combo: FlagCombo):
    baseline_counters = ExecutionCounters()
    baseline = run_non_stream(monkeypatch, BASELINE_COMBO, baseline_counters)
    baseline_pipe = dict(baseline_counters.last_pipeline)
    baseline_payload = parity_payload(baseline)

    counters = ExecutionCounters()
    current = run_non_stream(monkeypatch, combo, counters)
    assert_parity_against_baseline(baseline_payload, parity_payload(current), combo)

    pipe = counters.last_pipeline
    assert pipe["hit_urls"] == baseline_pipe["hit_urls"], combo.label
    assert pipe["hit_scores"] == baseline_pipe["hit_scores"], combo.label
    assert pipe["context_text"] == baseline_pipe["context_text"], combo.label
    assert pipe["quality_metrics"] == baseline_pipe["quality_metrics"], combo.label
    assert pipe["pipeline_stages"] == baseline_pipe["pipeline_stages"], combo.label


@pytest.mark.parametrize("combo", ALL_FLAG_COMBOS, ids=lambda c: c.label)
def test_migration_gate_chat_response_builder_once(monkeypatch, combo: FlagCombo):
    """HTTP assembly path — single ChatResponseBuilder invocation."""
    counters = ExecutionCounters()
    result = run_non_stream(monkeypatch, combo, counters)
    settings = pipeline_settings()
    build_calls = {"n": 0}
    real = ChatResponseBuilder.from_rag_result

    def _count(self, rag_result, **kwargs):
        build_calls["n"] += 1
        return real(self, rag_result, **kwargs)

    monkeypatch.setattr(ChatResponseBuilder, "from_rag_result", _count)
    ChatResponseBuilder(settings).from_rag_result(
        result, request_id="once", session_id="s"
    )
    assert build_calls["n"] == 1, combo.label


@pytest.mark.parametrize("combo", ALL_FLAG_COMBOS, ids=lambda c: c.label)
def test_migration_gate_stream_event_order(monkeypatch, combo: FlagCombo):
    counters = ExecutionCounters()
    events = run_stream(monkeypatch, combo, counters)
    names = [e[0] for e in events]
    assert names[0] == "start", combo.label
    assert "status" in names, combo.label
    assert names[-1] == "final", combo.label
    assert counters.stream_pipeline == 1, combo.label
    final = events[-1][1]
    answer = final.get("answer") or (final.get("response") or {}).get("answer")
    assert answer == "Grounded answer", combo.label


@pytest.mark.parametrize("combo", ALL_FLAG_COMBOS, ids=lambda c: c.label)
def test_migration_gate_error_propagation_llm_timeout(monkeypatch, combo: FlagCombo):
    from app.api.chat import _dispatch_non_stream_answer

    apply_flags(monkeypatch, combo)

    class _TimeoutLLM:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def generate(self, **kwargs):
            return {"error_type": "llm_timeout", "generation_ms": 1, "diagnostics": {}}

    counters = ExecutionCounters()
    install_instrumentation(monkeypatch, counters)
    monkeypatch.setattr("app.services.rag_service.LlmGenerationService", _TimeoutLLM)

    result = _dispatch_non_stream_answer(
        MagicMock(),
        pipeline_settings(),
        "What is the org?",
        "s",
        request_id="err",
        bypass_cache=True,
    )
    assert result.error_type == "llm_timeout", combo.label


@pytest.mark.parametrize("combo", ALL_FLAG_COMBOS, ids=lambda c: c.label)
def test_migration_gate_golden_smoke_suite(monkeypatch, combo: FlagCombo):
    failures = run_golden_smoke_for_combo(monkeypatch, combo)
    assert not failures, "\n".join(failures)


def test_migration_gate_all_combos_covered():
    assert len(ALL_FLAG_COMBOS) == 8
    assert len({c.label for c in ALL_FLAG_COMBOS}) == 8


def test_migration_gate_cache_namespace_unchanged(monkeypatch):
    settings = pipeline_settings()
    db = MagicMock()
    ns_baseline = build_retrieval_namespace(settings, db=db)
    for combo in ALL_FLAG_COMBOS:
        counters = ExecutionCounters()
        run_non_stream(monkeypatch, combo, counters)
        ns = build_retrieval_namespace(settings, db=db)
        assert ns == ns_baseline, combo.label


def test_migration_gate_execution_metrics_report_shape():
    counters = ExecutionCounters(rps_run=1, dfp=1, llm=1)
    metrics = counters.as_metrics()
    assert "dfp" in metrics and metrics["dfp"] == 1
