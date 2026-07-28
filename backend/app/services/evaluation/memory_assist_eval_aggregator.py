"""Pure aggregation of frozen Memory Assist / Shadow diagnostics (Step 049)."""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from app.services.evaluation.memory_assist_eval_recommendation import (
    recommend_memory_assist_staging,
)
from app.services.evaluation.memory_assist_eval_types import (
    LIMIT_CACHE_HIT_SHADOW_NOT_OBSERVED,
    LIMIT_MALFORMED_DIAGNOSTICS,
    LIMIT_MISSING_ASSIST_DIAGNOSTICS,
    LIMIT_MISSING_SHADOW_DIAGNOSTICS,
    LIMIT_NO_LIVE_HARVEST,
    LIMIT_SYNTHETIC_FIXTURE_ONLY,
    SCHEMA_VERSION,
    AssistSummary,
    CacheSummary,
    CorpusEvalSnapshot,
    EvalFlagSnapshot,
    EvalRunMetadata,
    EvalTurnRecord,
    EvalTurnRow,
    MemoryAssistEvalReportV1,
    MemoryAssistEvalThresholdsV1,
    QuerySetSummary,
    ShadowSummary,
    cap_ids,
)


class EvalInputError(ValueError):
    """Invalid evaluation input."""


_FORBIDDEN_TEXT_KEYS = frozenset(
    {
        "query",
        "query_text",
        "message",
        "answer",
        "answer_text",
        "prompt",
        "system_prompt",
        "user_prompt",
        "proposition",
        "claim_text",
        "chunk_text",
        "text",
        "excerpt",
        "url",
        "urls",
    }
)


def strip_forbidden_fields(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    if not isinstance(payload, Mapping):
        raise EvalInputError("diagnostics must be a mapping")
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if str(key).lower() in _FORBIDDEN_TEXT_KEYS:
            continue
        cleaned[str(key)] = value
    return cleaned


def diagnostics_from_assist_result(result: Any) -> dict[str, Any]:
    """Thin adapter — accepts MemoryAssistResult-like objects with to_diagnostics()."""
    if result is None:
        return {}
    if hasattr(result, "to_diagnostics"):
        return dict(result.to_diagnostics())
    if isinstance(result, Mapping):
        return dict(result)
    raise EvalInputError("assist result must provide to_diagnostics() or be a mapping")


def diagnostics_from_shadow_result(result: Any) -> dict[str, Any]:
    if result is None:
        return {}
    if hasattr(result, "to_diagnostics"):
        return dict(result.to_diagnostics())
    if isinstance(result, Mapping):
        return dict(result)
    raise EvalInputError("shadow result must provide to_diagnostics() or be a mapping")


def normalize_turn(raw: Mapping[str, Any], *, lenient: bool = False) -> EvalTurnRecord:
    """Normalize a fixture/dict turn into EvalTurnRecord. Strips forbidden text fields."""
    try:
        query_id = str(raw.get("query_id") or "").strip()
        if not query_id:
            raise EvalInputError("missing query_id")

        flags_raw = raw.get("effective_flags") or raw.get("flag_snapshot") or {}
        if not isinstance(flags_raw, Mapping):
            raise EvalInputError("effective_flags must be a mapping")
        flags = EvalFlagSnapshot(
            reasoning_service_enabled=bool(flags_raw.get("reasoning_service_enabled", False)),
            memory_evidence_assist_enabled=bool(
                flags_raw.get("memory_evidence_assist_enabled", False)
            ),
            cache_namespace_v2_enabled=bool(flags_raw.get("cache_namespace_v2_enabled", False)),
            memory_canonical_shadow_enabled=bool(
                flags_raw.get("memory_canonical_shadow_enabled", False)
            ),
        )

        assist = strip_forbidden_fields(raw.get("assist_diagnostics") or raw.get("memory_assist"))
        shadow = strip_forbidden_fields(
            raw.get("shadow_diagnostics") or raw.get("memory_canonical_shadow")
        )
        limitations = tuple(
            str(x) for x in (raw.get("limitations") or ()) if x is not None
        )
        kv = raw.get("knowledge_version")
        mv = raw.get("memory_version")
        return EvalTurnRecord(
            query_id=query_id,
            query_hash=(str(raw["query_hash"]) if raw.get("query_hash") is not None else None),
            assist_diagnostics=assist,
            shadow_diagnostics=shadow,
            effective_flags=flags,
            cache_hit=bool(raw.get("cache_hit", False)),
            knowledge_version=int(kv) if kv is not None else None,
            memory_version=int(mv) if mv is not None else None,
            limitations=limitations,
        )
    except EvalInputError:
        if lenient:
            raise
        raise
    except Exception as exc:
        raise EvalInputError(f"malformed turn: {exc}") from exc


def validate_environment(environment: str) -> str:
    if environment == "production":
        raise EvalInputError(
            "Step 049 rejects environment=production; use local|ci|staging only"
        )
    if environment not in ("local", "ci", "staging"):
        raise EvalInputError(f"unsupported environment: {environment}")
    return environment


def aggregate_memory_assist_eval(
    turns: Sequence[Mapping[str, Any] | EvalTurnRecord],
    *,
    metadata: EvalRunMetadata,
    thresholds: MemoryAssistEvalThresholdsV1 | None = None,
    include_turns: bool = False,
    allow_duplicate_query_ids: bool = False,
    lenient: bool = False,
    report_limitations: Sequence[str] = (),
) -> MemoryAssistEvalReportV1:
    """Aggregate frozen diagnostics into MemoryAssistEvalReportV1."""
    thresholds = thresholds or MemoryAssistEvalThresholdsV1()
    validate_environment(metadata.environment)

    path_hist: Counter[str] = Counter()
    shadow_path_hist: Counter[str] = Counter()
    align_hist: Counter[str] = Counter()
    divergence_hist: Counter[str] = Counter()
    limitation_hist: Counter[str] = Counter()
    supported_dist: Counter[str] = Counter()
    conflicted_dist: Counter[str] = Counter()
    observation_dist: Counter[str] = Counter()
    overlap_dist: Counter[str] = Counter()
    memory_only_dist: Counter[str] = Counter()
    retrieval_only_dist: Counter[str] = Counter()
    context_overlap_dist: Counter[str] = Counter()
    topic_match_hist: Counter[str] = Counter()
    page_role_match_hist: Counter[str] = Counter()

    durations: list[float] = []
    shadow_durations: list[float] = []

    assist_attempted = 0
    assist_effective = 0
    empty_count = 0
    sparse_count = 0
    failed_count = 0
    usable_count = 0
    corpus_configured_count = 0
    corpus_complete_count = 0
    compared_count = 0
    support_missing_count = 0

    cache_hit_count = 0
    missing_shadow_cache = 0
    evaluable = 0
    input_errors = 0
    skipped_invalid = 0
    seen_ids: set[str] = set()
    duplicate_ids = 0
    turn_rows: list[EvalTurnRow] = []
    input_invalid = False

    normalized: list[EvalTurnRecord] = []
    for raw in turns:
        try:
            if isinstance(raw, EvalTurnRecord):
                rec = raw
            else:
                rec = normalize_turn(raw, lenient=lenient)
            if rec.query_id in seen_ids:
                duplicate_ids += 1
                if not allow_duplicate_query_ids:
                    raise EvalInputError(f"duplicate query_id: {rec.query_id}")
            seen_ids.add(rec.query_id)
            normalized.append(rec)
        except EvalInputError:
            input_errors += 1
            if lenient:
                skipped_invalid += 1
                continue
            raise

    total = len(normalized)
    if input_errors and not normalized and not lenient:
        input_invalid = True

    for rec in normalized:
        for lim in rec.limitations:
            limitation_hist[lim] += 1

        if rec.cache_hit:
            cache_hit_count += 1
            if not rec.shadow_diagnostics:
                missing_shadow_cache += 1
                limitation_hist[LIMIT_CACHE_HIT_SHADOW_NOT_OBSERVED] += 1
            # Cache hits are not evaluable for shadow observation rate denominator
            # in the same sense — still count for assist if diagnostics present
        else:
            evaluable += 1

        assist = rec.assist_diagnostics
        if assist is None and not rec.cache_hit:
            limitation_hist[LIMIT_MISSING_ASSIST_DIAGNOSTICS] += 1
        if assist is not None and not isinstance(assist, Mapping):
            limitation_hist[LIMIT_MALFORMED_DIAGNOSTICS] += 1
            assist = None

        if assist:
            path = str(assist.get("memory_assist_path") or "unknown")
            path_hist[path] += 1
            if path not in ("off", "skipped"):
                assist_attempted += 1
            if rec.effective_flags.assist_effective() and path not in ("off", "skipped"):
                assist_effective += 1
            if path == "empty":
                empty_count += 1
            if path == "sparse":
                sparse_count += 1
            if path == "failed":
                failed_count += 1
            if assist.get("memory_usable_for_evidence"):
                usable_count += 1
            if assist.get("memory_scope_configured"):
                corpus_configured_count += 1
            if assist.get("memory_scope_complete"):
                corpus_complete_count += 1
            supported_dist[str(int(assist.get("memory_supported_claim_count") or 0))] += 1
            conflicted_dist[str(int(assist.get("memory_conflicted_claim_count") or 0))] += 1
            observation_dist[
                str(int(assist.get("memory_observation_hints_count") or 0))
            ] += 1
            dur = assist.get("memory_read_duration_ms")
            if isinstance(dur, (int, float)):
                durations.append(float(dur))

        shadow = rec.shadow_diagnostics
        if shadow is None and not rec.cache_hit and rec.effective_flags.shadow_effective():
            limitation_hist[LIMIT_MISSING_SHADOW_DIAGNOSTICS] += 1
        if shadow is not None and not isinstance(shadow, Mapping):
            limitation_hist[LIMIT_MALFORMED_DIAGNOSTICS] += 1
            shadow = None

        if shadow:
            spath = str(shadow.get("memory_canonical_shadow_path") or "unknown")
            shadow_path_hist[spath] += 1
            if spath == "compared":
                compared_count += 1
            align = shadow.get("canonical_alignment")
            if align is not None:
                align_hist[str(align)] += 1
            for code in shadow.get("divergence_codes") or []:
                divergence_hist[str(code)] += 1
            overlap_dist[str(int(shadow.get("overlap_count") or 0))] += 1
            memory_only_dist[str(int(shadow.get("memory_only_count") or 0))] += 1
            retrieval_only_dist[str(int(shadow.get("retrieval_only_count") or 0))] += 1
            context_overlap_dist[
                str(int(shadow.get("context_overlap_count") or shadow.get("overlap_count") or 0))
            ] += 1
            missing_support = int(shadow.get("support_missing_from_context_count") or 0)
            if missing_support > 0:
                support_missing_count += 1
            topic_match_hist[_bool_key(shadow.get("topic_hint_match"))] += 1
            page_role_match_hist[_bool_key(shadow.get("page_role_hint_match"))] += 1
            sdur = shadow.get("comparison_duration_ms")
            if isinstance(sdur, (int, float)):
                shadow_durations.append(float(sdur))

        if include_turns:
            turn_rows.append(_turn_row(rec, assist, shadow))

    attempted_den = assist_attempted
    assist_summary = AssistSummary(
        total_turns=total,
        assist_attempted_count=assist_attempted,
        assist_effective_count=assist_effective,
        assist_path_histogram=dict(sorted(path_hist.items())),
        empty_memory_count=empty_count,
        empty_memory_rate_among_attempted=_rate(empty_count, attempted_den),
        sparse_memory_count=sparse_count,
        sparse_memory_rate_among_attempted=_rate(sparse_count, attempted_den),
        failed_count=failed_count,
        failed_rate_among_attempted=_rate(failed_count, attempted_den),
        usable_for_evidence_count=usable_count,
        usable_for_evidence_rate_among_attempted=_rate(usable_count, attempted_den),
        corpus_configured_count=corpus_configured_count,
        corpus_configured_rate_among_attempted=_rate(
            corpus_configured_count, attempted_den
        ),
        corpus_complete_count=corpus_complete_count,
        corpus_complete_rate_among_attempted=_rate(corpus_complete_count, attempted_den),
        supported_claim_count_distribution=dict(sorted(supported_dist.items(), key=_int_key)),
        conflicted_claim_count_distribution=dict(
            sorted(conflicted_dist.items(), key=_int_key)
        ),
        observation_hint_count_distribution=dict(
            sorted(observation_dist.items(), key=_int_key)
        ),
        memory_read_duration_ms_p50=_percentile(durations, 50),
        memory_read_duration_ms_p95=_percentile(durations, 95),
    )

    shadow_summary = ShadowSummary(
        total_shadow_records=sum(shadow_path_hist.values()),
        shadow_path_histogram=dict(sorted(shadow_path_hist.items())),
        compared_count=compared_count,
        canonical_alignment_histogram=dict(sorted(align_hist.items())),
        overlap_count_distribution=dict(sorted(overlap_dist.items(), key=_int_key)),
        memory_only_count_distribution=dict(
            sorted(memory_only_dist.items(), key=_int_key)
        ),
        retrieval_only_count_distribution=dict(
            sorted(retrieval_only_dist.items(), key=_int_key)
        ),
        context_overlap_count_distribution=dict(
            sorted(context_overlap_dist.items(), key=_int_key)
        ),
        support_missing_from_context_count=support_missing_count,
        support_missing_from_context_rate_among_compared=_rate(
            support_missing_count, compared_count
        ),
        topic_hint_match_histogram=dict(sorted(topic_match_hist.items())),
        page_role_hint_match_histogram=dict(sorted(page_role_match_hist.items())),
        comparison_duration_ms_p50=_percentile(shadow_durations, 50),
        comparison_duration_ms_p95=_percentile(shadow_durations, 95),
    )

    shadow_observed = sum(
        1
        for r in normalized
        if r.shadow_diagnostics and not r.cache_hit
    )
    cache_summary = CacheSummary(
        cache_hit_count=cache_hit_count,
        evaluable_turn_count=evaluable,
        non_evaluable_cache_hit_count=missing_shadow_cache,
        shadow_observation_rate=_rate(shadow_observed, max(evaluable, 0)),
        missing_shadow_due_to_cache_hit_count=missing_shadow_cache,
    )

    query_set = QuerySetSummary(
        total_turns=total,
        unique_query_ids=len(seen_ids),
        duplicate_query_id_count=duplicate_ids,
        input_error_count=input_errors,
        skipped_invalid_count=skipped_invalid,
    )

    corpus = metadata.corpus_snapshot
    recommendation, reasons = recommend_memory_assist_staging(
        corpus=corpus,
        query_set=query_set,
        assist=assist_summary,
        shadow=shadow_summary,
        cache=cache_summary,
        thresholds=thresholds,
        divergence_code_histogram=dict(divergence_hist),
        input_invalid=input_invalid or (input_errors > 0 and total == 0),
    )

    lims = list(report_limitations)
    if metadata.fixture_name:
        lims.append(LIMIT_SYNTHETIC_FIXTURE_ONLY)
    lims.append(LIMIT_NO_LIVE_HARVEST)
    lims = list(dict.fromkeys(lims))

    generated_at = metadata.generated_at or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    meta = EvalRunMetadata(
        schema_version=SCHEMA_VERSION,
        generated_at=generated_at,
        git_commit=metadata.git_commit,
        alembic_head=metadata.alembic_head,
        app_release=metadata.app_release,
        environment=metadata.environment,
        fixture_name=metadata.fixture_name,
        query_count=total,
        flag_snapshot=metadata.flag_snapshot,
        corpus_snapshot=corpus,
    )

    return MemoryAssistEvalReportV1(
        schema_version=SCHEMA_VERSION,
        generated_at=generated_at,
        run_metadata=meta,
        corpus_snapshot=corpus,
        query_set_summary=query_set,
        assist_summary=assist_summary,
        shadow_summary=shadow_summary,
        divergence_code_histogram=dict(sorted(divergence_hist.items())),
        limitation_histogram=dict(sorted(limitation_hist.items())),
        cache_summary=cache_summary,
        thresholds=thresholds,
        recommendation=recommendation,
        recommendation_reasons=reasons,
        report_limitations=tuple(lims),
        turns=tuple(turn_rows),
    )


def _turn_row(
    rec: EvalTurnRecord,
    assist: Mapping[str, Any] | None,
    shadow: Mapping[str, Any] | None,
) -> EvalTurnRow:
    assist = assist or {}
    shadow = shadow or {}
    return EvalTurnRow(
        query_id=rec.query_id,
        query_hash=rec.query_hash,
        assist_path=(str(assist["memory_assist_path"]) if assist.get("memory_assist_path") else None),
        shadow_path=(
            str(shadow["memory_canonical_shadow_path"])
            if shadow.get("memory_canonical_shadow_path")
            else None
        ),
        canonical_alignment=(
            str(shadow["canonical_alignment"]) if shadow.get("canonical_alignment") else None
        ),
        divergence_codes=tuple(str(c) for c in (shadow.get("divergence_codes") or ())),
        limitations=rec.limitations,
        memory_source_ids=cap_ids(assist.get("memory_source_ids")),
        memory_claim_ids=cap_ids(assist.get("memory_claim_ids")),
        memory_observation_ref_ids=cap_ids(assist.get("memory_observation_ref_ids")),
        cache_hit=rec.cache_hit,
        effective_flags=rec.effective_flags.to_dict(),
    )


def _rate(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return round(num / den, 6)


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return ordered[int(k)]
    return ordered[f] * (c - k) + ordered[c] * (k - f)


def _bool_key(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "null"


def _int_key(item: tuple[str, int]) -> tuple[int, str]:
    key = item[0]
    try:
        return (int(key), key)
    except ValueError:
        return (10**9, key)
