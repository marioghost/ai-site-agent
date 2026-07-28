"""Deterministic recommendation engine for offline Memory Assist eval (Step 049)."""
from __future__ import annotations

from app.services.evaluation.memory_assist_eval_types import (
    HARD_NO_GO_REASONS,
    REASON_ALL_HARD_GATES_PASSED,
    REASON_ASSIST_FAILURE_RATE_EXCEEDED,
    REASON_ASSIST_NEVER_EFFECTIVE,
    REASON_CORPUS_SCOPE_UNCONFIGURED,
    REASON_DOMINANT_RETRIEVAL_ONLY_DIVERGENCE,
    REASON_HIGH_CACHE_HIT_BLIND_SPOT,
    REASON_HIGH_EMPTY_MEMORY_RATE,
    REASON_HIGH_SPARSE_MEMORY_RATE,
    REASON_INSUFFICIENT_QUERY_SET,
    REASON_INSUFFICIENT_REAL_CLAIMS,
    REASON_INSUFFICIENT_REAL_SOURCE_COVERAGE,
    REASON_LIMITED_TOPIC_COVERAGE,
    REASON_LOW_SHADOW_OBSERVATION_RATE,
    REASON_LOW_USABLE_FOR_EVIDENCE_RATE,
    REASON_NO_EVALUABLE_TURNS,
    REASON_NO_SUPPORTED_REAL_CLAIMS,
    REASON_REPORT_INPUT_INVALID,
    REASON_SOFT_GATES_PASSED,
    AssistSummary,
    CacheSummary,
    CorpusEvalSnapshot,
    EvalRecommendation,
    MemoryAssistEvalThresholdsV1,
    QuerySetSummary,
    ShadowSummary,
)


def recommend_memory_assist_staging(
    *,
    corpus: CorpusEvalSnapshot,
    query_set: QuerySetSummary,
    assist: AssistSummary,
    shadow: ShadowSummary,
    cache: CacheSummary,
    thresholds: MemoryAssistEvalThresholdsV1,
    divergence_code_histogram: dict[str, int],
    input_invalid: bool = False,
) -> tuple[EvalRecommendation, tuple[str, ...]]:
    """Coverage-aware conservative recommendation. Default NO_GO."""
    reasons: list[str] = []

    if input_invalid or query_set.input_error_count > 0 and query_set.total_turns == 0:
        reasons.append(REASON_REPORT_INPUT_INVALID)

    if not corpus.corpus_scope_configured:
        reasons.append(REASON_CORPUS_SCOPE_UNCONFIGURED)

    if query_set.total_turns < thresholds.min_query_count:
        reasons.append(REASON_INSUFFICIENT_QUERY_SET)

    if corpus.real_claims < thresholds.min_real_claims:
        reasons.append(REASON_INSUFFICIENT_REAL_CLAIMS)

    if corpus.distinct_real_source_ids < thresholds.min_distinct_real_source_ids:
        reasons.append(REASON_INSUFFICIENT_REAL_SOURCE_COVERAGE)

    if corpus.supported_claims < thresholds.min_supported_real_claims:
        reasons.append(REASON_NO_SUPPORTED_REAL_CLAIMS)

    if cache.evaluable_turn_count == 0:
        reasons.append(REASON_NO_EVALUABLE_TURNS)

    assist_effective_rate = _safe_rate(
        assist.assist_effective_count, assist.total_turns
    )
    if assist.assist_effective_count == 0 or (
        assist_effective_rate is not None
        and assist_effective_rate < thresholds.min_assist_effective_rate
        and assist.total_turns > 0
    ):
        if assist.assist_effective_count == 0 and assist.total_turns > 0:
            reasons.append(REASON_ASSIST_NEVER_EFFECTIVE)

    if (
        assist.failed_rate_among_attempted is not None
        and assist.failed_rate_among_attempted > thresholds.max_failed_rate
    ):
        reasons.append(REASON_ASSIST_FAILURE_RATE_EXCEEDED)

    hard = [r for r in reasons if r in HARD_NO_GO_REASONS]
    if hard:
        return "NO_GO", tuple(_dedupe(hard + reasons))

    soft: list[str] = []
    if (
        assist.empty_memory_rate_among_attempted is not None
        and assist.empty_memory_rate_among_attempted > thresholds.max_empty_memory_rate
    ):
        soft.append(REASON_HIGH_EMPTY_MEMORY_RATE)

    if (
        assist.sparse_memory_rate_among_attempted is not None
        and assist.sparse_memory_rate_among_attempted > thresholds.max_sparse_memory_rate
    ):
        soft.append(REASON_HIGH_SPARSE_MEMORY_RATE)

    if (
        assist.usable_for_evidence_rate_among_attempted is not None
        and assist.usable_for_evidence_rate_among_attempted
        < thresholds.min_usable_for_evidence_rate
    ):
        soft.append(REASON_LOW_USABLE_FOR_EVIDENCE_RATE)

    if (
        cache.shadow_observation_rate is not None
        and cache.shadow_observation_rate < thresholds.min_shadow_observation_rate
    ):
        soft.append(REASON_LOW_SHADOW_OBSERVATION_RATE)

    if assist.total_turns > 0:
        blind = cache.non_evaluable_cache_hit_count / assist.total_turns
        if blind > thresholds.max_cache_hit_blind_spot_rate:
            soft.append(REASON_HIGH_CACHE_HIT_BLIND_SPOT)

    retrieval_only = divergence_code_histogram.get(
        "retrieval_source_not_in_memory", 0
    )
    compared = max(shadow.compared_count, 1)
    if shadow.compared_count > 0 and retrieval_only / compared >= 0.5:
        soft.append(REASON_DOMINANT_RETRIEVAL_ONLY_DIVERGENCE)

    topic_not = divergence_code_histogram.get("topic_hint_not_reflected", 0)
    if shadow.compared_count > 0 and topic_not / compared >= 0.5:
        soft.append(REASON_LIMITED_TOPIC_COVERAGE)

    if soft:
        return "CONDITIONAL", tuple(_dedupe([REASON_ALL_HARD_GATES_PASSED, *soft]))

    # Final STAGING_CANDIDATE gates on effective rates
    if assist_effective_rate is None or assist_effective_rate < thresholds.min_assist_effective_rate:
        return "NO_GO", tuple(
            _dedupe([REASON_ASSIST_NEVER_EFFECTIVE, *reasons])
        )

    return "STAGING_CANDIDATE", (
        REASON_ALL_HARD_GATES_PASSED,
        REASON_SOFT_GATES_PASSED,
    )


def _safe_rate(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return num / den


def _dedupe(codes: list[str]) -> list[str]:
    return list(dict.fromkeys(codes))
