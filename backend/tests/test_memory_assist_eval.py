"""RFC-100 Step 049 — offline Memory Assist evaluation tests."""
from __future__ import annotations

import ast
import json
import time
from pathlib import Path

import pytest

from app.services.evaluation.memory_assist_eval_aggregator import (
    EvalInputError,
    aggregate_memory_assist_eval,
    diagnostics_from_assist_result,
    strip_forbidden_fields,
    validate_environment,
)
from app.services.evaluation.memory_assist_eval_report import (
    render_markdown_report,
    report_to_json_dict,
)
from app.services.evaluation.memory_assist_eval_types import (
    LIMIT_CACHE_HIT_SHADOW_NOT_OBSERVED,
    REASON_INSUFFICIENT_REAL_CLAIMS,
    CorpusEvalSnapshot,
    EvalRunMetadata,
    MemoryAssistEvalThresholdsV1,
    activation_statement,
)
from app.services.reasoning.memory_assist_types import MemoryAssistResult

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
EVAL_PKG = APP_ROOT / "services" / "evaluation"
FIX = Path(__file__).resolve().parent / "fixtures" / "memory_assist_eval"

FORBIDDEN_IMPORT_STEMS = frozenset(
    {
        "rag_service",
        "rag_streaming",
        "reasoning_service",
        "retrieval_pipeline_service",
        "evidence_assembly",
        "epistemic_memory_service",
        "memory_region_reader",
        "qdrant_service",
        "ollama_service",
        "prompt_builder",
        "answer_cache_service",
        "retrieval_cache_service",
        "memory_version_service",
        "knowledge_version_service",
    }
)

RUNTIME_PACKAGES_MUST_NOT_IMPORT_EVAL = (
    APP_ROOT / "api" / "chat.py",
    APP_ROOT / "services" / "rag_service.py",
    APP_ROOT / "services" / "rag_streaming.py",
    APP_ROOT / "services" / "reasoning",
    APP_ROOT / "services" / "retrieval_pipeline_service.py",
    APP_ROOT / "services" / "evidence_assembly",
    APP_ROOT / "services" / "epistemic_memory",
    APP_ROOT / "services" / "language",
)


def _meta(**kw) -> EvalRunMetadata:
    defaults = dict(
        generated_at="2026-07-28T00:00:00Z",
        environment="ci",
        fixture_name="test",
        corpus_snapshot=CorpusEvalSnapshot(corpus_scope_configured=True, real_claims=6),
    )
    defaults.update(kw)
    return EvalRunMetadata(**defaults)


def _flags_all_on() -> dict:
    return {
        "reasoning_service_enabled": True,
        "memory_evidence_assist_enabled": True,
        "cache_namespace_v2_enabled": True,
        "memory_canonical_shadow_enabled": True,
    }


def _turn(qid: str, **kw) -> dict:
    base = {
        "query_id": qid,
        "query_hash": f"h-{qid}",
        "effective_flags": _flags_all_on(),
        "cache_hit": False,
        "assist_diagnostics": {
            "memory_assist_path": "used",
            "memory_supported_claim_count": 1,
            "memory_conflicted_claim_count": 0,
            "memory_observation_hints_count": 1,
            "memory_usable_for_evidence": True,
            "memory_scope_configured": True,
            "memory_scope_complete": False,
            "memory_read_duration_ms": 4,
        },
        "shadow_diagnostics": {
            "memory_canonical_shadow_path": "compared",
            "canonical_alignment": "aligned",
            "divergence_codes": ["canonical_aligned"],
            "overlap_count": 1,
            "memory_only_count": 0,
            "retrieval_only_count": 0,
            "support_missing_from_context_count": 0,
            "topic_hint_match": True,
            "page_role_hint_match": True,
            "comparison_duration_ms": 1,
        },
    }
    base.update(kw)
    return base


@pytest.mark.unit
def test_empty_input():
    report = aggregate_memory_assist_eval([], metadata=_meta())
    assert report.query_set_summary.total_turns == 0
    assert report.recommendation == "NO_GO"


@pytest.mark.unit
def test_single_valid_record():
    report = aggregate_memory_assist_eval([_turn("q1")], metadata=_meta())
    assert report.query_set_summary.total_turns == 1
    assert report.assist_summary.assist_path_histogram.get("used") == 1


@pytest.mark.unit
def test_assist_and_shadow_histograms():
    turns = [
        _turn(
            "a",
            assist_diagnostics={
                "memory_assist_path": "empty",
                "memory_usable_for_evidence": False,
                "memory_supported_claim_count": 0,
                "memory_conflicted_claim_count": 0,
                "memory_observation_hints_count": 0,
                "memory_scope_configured": True,
            },
        ),
        _turn("b"),
    ]
    report = aggregate_memory_assist_eval(turns, metadata=_meta())
    assert report.assist_summary.assist_path_histogram["empty"] == 1
    assert report.assist_summary.assist_path_histogram["used"] == 1
    assert report.shadow_summary.shadow_path_histogram["compared"] >= 1


@pytest.mark.unit
def test_divergence_histogram_and_stable_ordering():
    turns = [
        _turn(
            "d1",
            shadow_diagnostics={
                "memory_canonical_shadow_path": "compared",
                "canonical_alignment": "partial",
                "divergence_codes": ["partial_overlap", "retrieval_source_not_in_memory"],
                "overlap_count": 1,
                "memory_only_count": 0,
                "retrieval_only_count": 1,
                "support_missing_from_context_count": 0,
            },
        ),
        _turn(
            "d2",
            shadow_diagnostics={
                "memory_canonical_shadow_path": "compared",
                "canonical_alignment": "divergent",
                "divergence_codes": ["retrieval_source_not_in_memory", "no_overlap"],
                "overlap_count": 0,
                "memory_only_count": 1,
                "retrieval_only_count": 2,
                "support_missing_from_context_count": 0,
            },
        ),
    ]
    report = aggregate_memory_assist_eval(turns, metadata=_meta())
    keys = list(report.divergence_code_histogram.keys())
    assert keys == sorted(keys)
    assert report.divergence_code_histogram["retrieval_source_not_in_memory"] == 2


@pytest.mark.unit
def test_rate_denominators():
    turns = [
        _turn(
            "e1",
            assist_diagnostics={
                "memory_assist_path": "empty",
                "memory_usable_for_evidence": False,
                "memory_supported_claim_count": 0,
                "memory_conflicted_claim_count": 0,
                "memory_observation_hints_count": 0,
                "memory_scope_configured": True,
            },
        ),
        _turn("e2"),
    ]
    report = aggregate_memory_assist_eval(turns, metadata=_meta())
    assert report.assist_summary.assist_attempted_count == 2
    assert report.assist_summary.empty_memory_rate_among_attempted == 0.5


@pytest.mark.unit
def test_percentile_calculation():
    turns = []
    for i, dur in enumerate([1, 2, 3, 4, 100]):
        t = _turn(f"p{i}")
        t["assist_diagnostics"] = {
            **t["assist_diagnostics"],
            "memory_read_duration_ms": dur,
        }
        turns.append(t)
    report = aggregate_memory_assist_eval(turns, metadata=_meta())
    assert report.assist_summary.memory_read_duration_ms_p50 == 3
    assert report.assist_summary.memory_read_duration_ms_p95 is not None


@pytest.mark.unit
def test_cache_hit_missing_shadow_not_failure():
    turns = [
        _turn("c1", cache_hit=True, assist_diagnostics=None, shadow_diagnostics=None),
        _turn("c2"),
    ]
    report = aggregate_memory_assist_eval(turns, metadata=_meta())
    assert report.cache_summary.missing_shadow_due_to_cache_hit_count == 1
    assert LIMIT_CACHE_HIT_SHADOW_NOT_OBSERVED in report.limitation_histogram
    assert report.assist_summary.failed_count == 0


@pytest.mark.unit
def test_invalid_input_strict_mode():
    with pytest.raises(EvalInputError):
        aggregate_memory_assist_eval([{"query_id": ""}], metadata=_meta())


@pytest.mark.unit
def test_invalid_input_lenient_mode():
    report = aggregate_memory_assist_eval(
        [{"query_id": ""}, _turn("ok")],
        metadata=_meta(),
        lenient=True,
    )
    assert report.query_set_summary.total_turns == 1
    assert report.query_set_summary.skipped_invalid_count == 1


@pytest.mark.unit
def test_duplicate_query_ids_strict():
    with pytest.raises(EvalInputError):
        aggregate_memory_assist_eval([_turn("dup"), _turn("dup")], metadata=_meta())


@pytest.mark.unit
def test_duplicate_query_ids_allowed():
    report = aggregate_memory_assist_eval(
        [_turn("dup"), _turn("dup")],
        metadata=_meta(),
        allow_duplicate_query_ids=True,
    )
    assert report.query_set_summary.duplicate_query_id_count == 1


@pytest.mark.unit
def test_bounded_per_query_ids_and_no_text_leakage():
    big_ids = list(range(100))
    turn = _turn(
        "ids",
        assist_diagnostics={
            "memory_assist_path": "used",
            "memory_usable_for_evidence": True,
            "memory_supported_claim_count": 1,
            "memory_conflicted_claim_count": 0,
            "memory_observation_hints_count": 1,
            "memory_scope_configured": True,
            "memory_source_ids": big_ids,
            "memory_claim_ids": big_ids,
            "proposition": "SECRET",
            "answer": "SECRET",
        },
        query="SECRET QUERY",
        answer="SECRET ANSWER",
    )
    report = aggregate_memory_assist_eval([turn], metadata=_meta(), include_turns=True)
    row = report.turns[0]
    assert len(row.memory_source_ids) <= 20
    blob = json.dumps(report_to_json_dict(report))
    assert "SECRET" not in blob


@pytest.mark.unit
def test_strip_forbidden_fields():
    cleaned = strip_forbidden_fields(
        {"memory_assist_path": "used", "answer": "x", "proposition": "y"}
    )
    assert cleaned is not None
    assert "answer" not in cleaned
    assert cleaned["memory_assist_path"] == "used"


@pytest.mark.unit
def test_production_environment_rejected():
    with pytest.raises(EvalInputError):
        validate_environment("production")


@pytest.mark.unit
def test_recommendation_nogo_sparse_corpus():
    corpus = CorpusEvalSnapshot(
        corpus_scope_configured=True,
        real_claims=2,
        supported_claims=1,
        distinct_real_source_ids=1,
    )
    report = aggregate_memory_assist_eval(
        [_turn(f"q{i}") for i in range(12)],
        metadata=_meta(corpus_snapshot=corpus),
        thresholds=MemoryAssistEvalThresholdsV1(),
    )
    assert report.recommendation == "NO_GO"
    assert REASON_INSUFFICIENT_REAL_CLAIMS in report.recommendation_reasons


@pytest.mark.unit
def test_recommendation_staging_candidate_synthetic():
    turns = json.loads((FIX / "healthy_staging_candidate_turns.json").read_text())["turns"]
    corpus = CorpusEvalSnapshot(
        **json.loads((FIX / "corpus_snapshot_healthy_synthetic.json").read_text())
    )
    report = aggregate_memory_assist_eval(
        turns,
        metadata=_meta(corpus_snapshot=corpus, fixture_name="healthy"),
        thresholds=MemoryAssistEvalThresholdsV1(min_query_count=10),
    )
    assert report.recommendation == "STAGING_CANDIDATE"
    md = render_markdown_report(report)
    assert "controlled staging experiment only" in md
    assert report.recommendation in md


@pytest.mark.unit
def test_hard_gate_overrides_healthy_soft_metrics():
    turns = json.loads((FIX / "healthy_staging_candidate_turns.json").read_text())["turns"]
    corpus = CorpusEvalSnapshot(
        corpus_scope_configured=False,
        real_claims=100,
        supported_claims=50,
        distinct_real_source_ids=20,
    )
    report = aggregate_memory_assist_eval(turns, metadata=_meta(corpus_snapshot=corpus))
    assert report.recommendation == "NO_GO"


@pytest.mark.unit
def test_thresholds_included_in_report():
    report = aggregate_memory_assist_eval([_turn("t")], metadata=_meta())
    assert "min_real_claims" in report.thresholds.to_dict()
    assert report.thresholds.to_dict()["label"].startswith("engineering_gate")


@pytest.mark.unit
def test_deterministic_json_excluding_generated_at():
    turns = [_turn("a"), _turn("b")]
    r1 = aggregate_memory_assist_eval(turns, metadata=_meta(generated_at="T0"))
    r2 = aggregate_memory_assist_eval(turns, metadata=_meta(generated_at="T0"))
    d1 = report_to_json_dict(r1)
    d2 = report_to_json_dict(r2)
    d1.pop("generated_at", None)
    d2.pop("generated_at", None)
    d1["run_metadata"].pop("generated_at", None)
    d2["run_metadata"].pop("generated_at", None)
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)


@pytest.mark.unit
def test_markdown_matches_json_recommendation():
    report = aggregate_memory_assist_eval([_turn("m")], metadata=_meta())
    md = render_markdown_report(report)
    assert report.recommendation in md
    assert activation_statement(report.recommendation) in md


@pytest.mark.unit
def test_sample_fixture_nogo():
    turns = json.loads((FIX / "sample_turns.json").read_text())["turns"]
    corpus = CorpusEvalSnapshot(
        **json.loads((FIX / "corpus_snapshot_sparse_nogo.json").read_text())
    )
    report = aggregate_memory_assist_eval(
        turns, metadata=_meta(corpus_snapshot=corpus, fixture_name="sample")
    )
    assert report.recommendation == "NO_GO"


@pytest.mark.unit
def test_adapter_from_memory_assist_result():
    result = MemoryAssistResult.off()
    diag = diagnostics_from_assist_result(result)
    assert diag["memory_assist_path"] == "off"


@pytest.mark.unit
def test_evaluation_core_boundary_imports():
    violations: list[str] = []
    for path in EVAL_PKG.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parts = set(alias.name.split("."))
                    hit = FORBIDDEN_IMPORT_STEMS.intersection(parts)
                    if hit:
                        violations.append(f"{path.name}: {hit}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                parts = set(node.module.split("."))
                if node.module.startswith("app.services.evaluation"):
                    continue
                if node.module.startswith("app.services.reasoning.memory_assist_types"):
                    continue
                if node.module.startswith(
                    "app.services.reasoning.memory_canonical_shadow_types"
                ):
                    continue
                hit = FORBIDDEN_IMPORT_STEMS.intersection(parts)
                if hit:
                    violations.append(f"{path.name}: {node.module}")
                if "reasoning_service" in parts:
                    violations.append(f"{path.name}: reasoning_service")
    assert violations == []


@pytest.mark.unit
def test_runtime_packages_do_not_import_evaluation():
    violations: list[str] = []
    for target in RUNTIME_PACKAGES_MUST_NOT_IMPORT_EVAL:
        paths = [target] if target.is_file() else list(target.rglob("*.py"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if "evaluation" in node.module.split("."):
                        violations.append(str(path))
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "evaluation" in alias.name.split("."):
                            violations.append(str(path))
    assert violations == []


@pytest.mark.unit
def test_synthetic_1000_turn_performance():
    turns = [_turn(f"perf-{i}") for i in range(1000)]
    started = time.perf_counter()
    report = aggregate_memory_assist_eval(turns, metadata=_meta())
    elapsed = time.perf_counter() - started
    assert report.query_set_summary.total_turns == 1000
    assert elapsed < 5.0


@pytest.mark.unit
def test_cli_script_exists_and_is_offline():
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_memory_assist_eval.py"
    text = script.read_text(encoding="utf-8")
    assert "Fixture ingestion" in text or "fixtures only" in text
    assert "RagService" not in text
    assert "EpistemicMemoryService" not in text


@pytest.mark.unit
def test_conditional_recommendation_high_empty_rate():
    corpus = CorpusEvalSnapshot(
        corpus_scope_configured=True,
        real_claims=40,
        supported_claims=20,
        distinct_real_source_ids=10,
    )
    turns = []
    for i in range(12):
        if i < 8:
            turns.append(
                _turn(
                    f"empty-{i}",
                    assist_diagnostics={
                        "memory_assist_path": "empty",
                        "memory_usable_for_evidence": False,
                        "memory_supported_claim_count": 0,
                        "memory_conflicted_claim_count": 0,
                        "memory_observation_hints_count": 0,
                        "memory_scope_configured": True,
                    },
                    shadow_diagnostics={
                        "memory_canonical_shadow_path": "empty_memory",
                        "canonical_alignment": "not_evaluable",
                        "divergence_codes": ["memory_empty"],
                        "overlap_count": 0,
                        "memory_only_count": 0,
                        "retrieval_only_count": 1,
                        "support_missing_from_context_count": 0,
                    },
                )
            )
        else:
            turns.append(_turn(f"used-{i}"))
    thresholds = MemoryAssistEvalThresholdsV1(
        min_query_count=10,
        min_real_claims=20,
        min_distinct_real_source_ids=5,
        min_supported_real_claims=5,
        min_assist_effective_rate=0.2,
        max_empty_memory_rate=0.3,
        max_sparse_memory_rate=0.9,
        min_usable_for_evidence_rate=0.1,
        max_failed_rate=0.5,
        min_shadow_observation_rate=0.1,
        max_cache_hit_blind_spot_rate=0.9,
    )
    report = aggregate_memory_assist_eval(
        turns, metadata=_meta(corpus_snapshot=corpus), thresholds=thresholds
    )
    assert report.recommendation == "CONDITIONAL"
