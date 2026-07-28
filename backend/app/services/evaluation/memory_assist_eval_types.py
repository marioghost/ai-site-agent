"""Authoritative codes and immutable DTOs for offline Memory Assist evaluation (Step 049)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Mapping

EvalEnvironment = Literal["local", "ci", "staging"]

EvalRecommendation = Literal["NO_GO", "CONDITIONAL", "STAGING_CANDIDATE"]

# Authoritative recommendation reason codes — single source of truth
REASON_CORPUS_SCOPE_UNCONFIGURED = "corpus_scope_unconfigured"
REASON_INSUFFICIENT_QUERY_SET = "insufficient_query_set"
REASON_INSUFFICIENT_REAL_CLAIMS = "insufficient_real_claims"
REASON_INSUFFICIENT_REAL_SOURCE_COVERAGE = "insufficient_real_source_coverage"
REASON_NO_SUPPORTED_REAL_CLAIMS = "no_supported_real_claims"
REASON_ASSIST_NEVER_EFFECTIVE = "assist_never_effective"
REASON_ASSIST_FAILURE_RATE_EXCEEDED = "assist_failure_rate_exceeded"
REASON_REPORT_INPUT_INVALID = "report_input_invalid"
REASON_NO_EVALUABLE_TURNS = "no_evaluable_turns"
REASON_HIGH_EMPTY_MEMORY_RATE = "high_empty_memory_rate"
REASON_HIGH_SPARSE_MEMORY_RATE = "high_sparse_memory_rate"
REASON_LOW_USABLE_FOR_EVIDENCE_RATE = "low_usable_for_evidence_rate"
REASON_LOW_SHADOW_OBSERVATION_RATE = "low_shadow_observation_rate"
REASON_HIGH_CACHE_HIT_BLIND_SPOT = "high_cache_hit_blind_spot"
REASON_DOMINANT_RETRIEVAL_ONLY_DIVERGENCE = "dominant_retrieval_only_divergence"
REASON_LIMITED_TOPIC_COVERAGE = "limited_topic_coverage"
REASON_ALL_HARD_GATES_PASSED = "all_hard_gates_passed"
REASON_SOFT_GATES_PASSED = "soft_gates_passed"

HARD_NO_GO_REASONS = frozenset(
    {
        REASON_CORPUS_SCOPE_UNCONFIGURED,
        REASON_INSUFFICIENT_QUERY_SET,
        REASON_INSUFFICIENT_REAL_CLAIMS,
        REASON_INSUFFICIENT_REAL_SOURCE_COVERAGE,
        REASON_NO_SUPPORTED_REAL_CLAIMS,
        REASON_ASSIST_NEVER_EFFECTIVE,
        REASON_ASSIST_FAILURE_RATE_EXCEEDED,
        REASON_REPORT_INPUT_INVALID,
        REASON_NO_EVALUABLE_TURNS,
    }
)

CONDITIONAL_REASONS = frozenset(
    {
        REASON_HIGH_EMPTY_MEMORY_RATE,
        REASON_HIGH_SPARSE_MEMORY_RATE,
        REASON_LOW_USABLE_FOR_EVIDENCE_RATE,
        REASON_LOW_SHADOW_OBSERVATION_RATE,
        REASON_HIGH_CACHE_HIT_BLIND_SPOT,
        REASON_DOMINANT_RETRIEVAL_ONLY_DIVERGENCE,
        REASON_LIMITED_TOPIC_COVERAGE,
    }
)

ALL_RECOMMENDATION_REASONS = HARD_NO_GO_REASONS | CONDITIONAL_REASONS | frozenset(
    {REASON_ALL_HARD_GATES_PASSED, REASON_SOFT_GATES_PASSED}
)

# Limitation codes
LIMIT_CACHE_HIT_SHADOW_NOT_OBSERVED = "cache_hit_shadow_not_observed"
LIMIT_MISSING_ASSIST_DIAGNOSTICS = "missing_assist_diagnostics"
LIMIT_MISSING_SHADOW_DIAGNOSTICS = "missing_shadow_diagnostics"
LIMIT_MALFORMED_DIAGNOSTICS = "malformed_diagnostics"
LIMIT_SPARSE_MEMORY_EXPECTED = "sparse_memory_expected"
LIMIT_SYNTHETIC_FIXTURE_ONLY = "synthetic_fixture_only"
LIMIT_NO_LIVE_HARVEST = "no_live_harvest"

ALL_LIMITATION_CODES = frozenset(
    {
        LIMIT_CACHE_HIT_SHADOW_NOT_OBSERVED,
        LIMIT_MISSING_ASSIST_DIAGNOSTICS,
        LIMIT_MISSING_SHADOW_DIAGNOSTICS,
        LIMIT_MALFORMED_DIAGNOSTICS,
        LIMIT_SPARSE_MEMORY_EXPECTED,
        LIMIT_SYNTHETIC_FIXTURE_ONLY,
        LIMIT_NO_LIVE_HARVEST,
    }
)

_ID_CAP = 20
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class EvalFlagSnapshot:
    reasoning_service_enabled: bool = False
    memory_evidence_assist_enabled: bool = False
    cache_namespace_v2_enabled: bool = False
    memory_canonical_shadow_enabled: bool = False

    def assist_effective(self) -> bool:
        return (
            self.reasoning_service_enabled
            and self.memory_evidence_assist_enabled
            and self.cache_namespace_v2_enabled
        )

    def shadow_effective(self) -> bool:
        return self.assist_effective() and self.memory_canonical_shadow_enabled

    def to_dict(self) -> dict[str, bool]:
        return {
            "reasoning_service_enabled": self.reasoning_service_enabled,
            "memory_evidence_assist_enabled": self.memory_evidence_assist_enabled,
            "cache_namespace_v2_enabled": self.cache_namespace_v2_enabled,
            "memory_canonical_shadow_enabled": self.memory_canonical_shadow_enabled,
            "assist_effective": self.assist_effective(),
            "shadow_effective": self.shadow_effective(),
        }


@dataclass(frozen=True)
class CorpusEvalSnapshot:
    """Optional read-only corpus counters — supplied by CLI, never queried by aggregator."""

    sources: int = 0
    chunks: int = 0
    claims: int = 0
    observations: int = 0
    evidence_links: int = 0
    real_claims: int = 0
    test_claims: int = 0
    active_claims: int = 0
    supported_claims: int = 0
    conflicted_claims: int = 0
    distinct_real_source_ids: int = 0
    knowledge_version: int | None = None
    memory_version: int | None = None
    memory_shadow_write_enabled: bool = False
    corpus_scope_configured: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryAssistEvalThresholdsV1:
    """Engineering gate defaults — not empirical truth about knowledge quality."""

    min_query_count: int = 10
    min_real_claims: int = 20
    min_distinct_real_source_ids: int = 5
    min_supported_real_claims: int = 5
    min_assist_effective_rate: float = 0.5
    max_empty_memory_rate: float = 0.4
    max_sparse_memory_rate: float = 0.6
    min_usable_for_evidence_rate: float = 0.3
    max_failed_rate: float = 0.1
    min_shadow_observation_rate: float = 0.5
    max_cache_hit_blind_spot_rate: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["label"] = "engineering_gate_defaults_not_empirical_truth"
        return data

    @staticmethod
    def from_mapping(data: Mapping[str, Any] | None) -> MemoryAssistEvalThresholdsV1:
        if not data:
            return MemoryAssistEvalThresholdsV1()
        known = {f.name for f in MemoryAssistEvalThresholdsV1.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in data.items() if k in known}
        return MemoryAssistEvalThresholdsV1(**kwargs)


@dataclass(frozen=True)
class EvalRunMetadata:
    schema_version: int = SCHEMA_VERSION
    generated_at: str = ""
    git_commit: str | None = None
    alembic_head: str | None = None
    app_release: str = "0.7"
    environment: EvalEnvironment = "ci"
    fixture_name: str = ""
    query_count: int = 0
    flag_snapshot: EvalFlagSnapshot = field(default_factory=EvalFlagSnapshot)
    corpus_snapshot: CorpusEvalSnapshot = field(default_factory=CorpusEvalSnapshot)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "git_commit": self.git_commit,
            "alembic_head": self.alembic_head,
            "app_release": self.app_release,
            "environment": self.environment,
            "fixture_name": self.fixture_name,
            "query_count": self.query_count,
            "flag_snapshot": self.flag_snapshot.to_dict(),
            "corpus_snapshot": self.corpus_snapshot.to_dict(),
        }


@dataclass(frozen=True)
class EvalTurnRecord:
    """Immutable normalized turn — IDs and codes only."""

    query_id: str
    query_hash: str | None = None
    assist_diagnostics: Mapping[str, Any] | None = None
    shadow_diagnostics: Mapping[str, Any] | None = None
    effective_flags: EvalFlagSnapshot = field(default_factory=EvalFlagSnapshot)
    cache_hit: bool = False
    knowledge_version: int | None = None
    memory_version: int | None = None
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssistSummary:
    total_turns: int = 0
    assist_attempted_count: int = 0
    assist_effective_count: int = 0
    assist_path_histogram: dict[str, int] = field(default_factory=dict)
    empty_memory_count: int = 0
    empty_memory_rate_among_attempted: float | None = None
    sparse_memory_count: int = 0
    sparse_memory_rate_among_attempted: float | None = None
    failed_count: int = 0
    failed_rate_among_attempted: float | None = None
    usable_for_evidence_count: int = 0
    usable_for_evidence_rate_among_attempted: float | None = None
    corpus_configured_count: int = 0
    corpus_configured_rate_among_attempted: float | None = None
    corpus_complete_count: int = 0
    corpus_complete_rate_among_attempted: float | None = None
    supported_claim_count_distribution: dict[str, int] = field(default_factory=dict)
    conflicted_claim_count_distribution: dict[str, int] = field(default_factory=dict)
    observation_hint_count_distribution: dict[str, int] = field(default_factory=dict)
    memory_read_duration_ms_p50: float | None = None
    memory_read_duration_ms_p95: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShadowSummary:
    total_shadow_records: int = 0
    shadow_path_histogram: dict[str, int] = field(default_factory=dict)
    compared_count: int = 0
    canonical_alignment_histogram: dict[str, int] = field(default_factory=dict)
    overlap_count_distribution: dict[str, int] = field(default_factory=dict)
    memory_only_count_distribution: dict[str, int] = field(default_factory=dict)
    retrieval_only_count_distribution: dict[str, int] = field(default_factory=dict)
    context_overlap_count_distribution: dict[str, int] = field(default_factory=dict)
    support_missing_from_context_count: int = 0
    support_missing_from_context_rate_among_compared: float | None = None
    topic_hint_match_histogram: dict[str, int] = field(default_factory=dict)
    page_role_hint_match_histogram: dict[str, int] = field(default_factory=dict)
    comparison_duration_ms_p50: float | None = None
    comparison_duration_ms_p95: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CacheSummary:
    cache_hit_count: int = 0
    evaluable_turn_count: int = 0
    non_evaluable_cache_hit_count: int = 0
    shadow_observation_rate: float | None = None
    missing_shadow_due_to_cache_hit_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QuerySetSummary:
    total_turns: int = 0
    unique_query_ids: int = 0
    duplicate_query_id_count: int = 0
    input_error_count: int = 0
    skipped_invalid_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvalTurnRow:
    query_id: str
    query_hash: str | None
    assist_path: str | None
    shadow_path: str | None
    canonical_alignment: str | None
    divergence_codes: tuple[str, ...]
    limitations: tuple[str, ...]
    memory_source_ids: tuple[int, ...]
    memory_claim_ids: tuple[int, ...]
    memory_observation_ref_ids: tuple[int, ...]
    cache_hit: bool
    effective_flags: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_hash": self.query_hash,
            "assist_path": self.assist_path,
            "shadow_path": self.shadow_path,
            "canonical_alignment": self.canonical_alignment,
            "divergence_codes": list(self.divergence_codes),
            "limitations": list(self.limitations),
            "memory_source_ids": list(self.memory_source_ids[:_ID_CAP]),
            "memory_claim_ids": list(self.memory_claim_ids[:_ID_CAP]),
            "memory_observation_ref_ids": list(self.memory_observation_ref_ids[:_ID_CAP]),
            "cache_hit": self.cache_hit,
            "effective_flags": self.effective_flags,
        }


@dataclass(frozen=True)
class MemoryAssistEvalReportV1:
    schema_version: int
    generated_at: str
    run_metadata: EvalRunMetadata
    corpus_snapshot: CorpusEvalSnapshot
    query_set_summary: QuerySetSummary
    assist_summary: AssistSummary
    shadow_summary: ShadowSummary
    divergence_code_histogram: dict[str, int]
    limitation_histogram: dict[str, int]
    cache_summary: CacheSummary
    thresholds: MemoryAssistEvalThresholdsV1
    recommendation: EvalRecommendation
    recommendation_reasons: tuple[str, ...]
    report_limitations: tuple[str, ...]
    turns: tuple[EvalTurnRow, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "run_metadata": self.run_metadata.to_dict(),
            "corpus_snapshot": self.corpus_snapshot.to_dict(),
            "query_set_summary": self.query_set_summary.to_dict(),
            "assist_summary": self.assist_summary.to_dict(),
            "shadow_summary": self.shadow_summary.to_dict(),
            "divergence_code_histogram": dict(sorted(self.divergence_code_histogram.items())),
            "limitation_histogram": dict(sorted(self.limitation_histogram.items())),
            "cache_summary": self.cache_summary.to_dict(),
            "thresholds": self.thresholds.to_dict(),
            "recommendation": self.recommendation,
            "recommendation_reasons": list(self.recommendation_reasons),
            "report_limitations": list(self.report_limitations),
            "turns": [t.to_dict() for t in self.turns],
            "activation_statement": activation_statement(self.recommendation),
            "metric_disclaimer": (
                "All metrics are descriptive coverage/engineering signals. "
                "They are not accuracy, correctness, answer quality, or Memory truth measures."
            ),
        }


def activation_statement(recommendation: EvalRecommendation) -> str:
    if recommendation == "NO_GO":
        return "Memory Assist must remain OFF in staging and production."
    if recommendation == "CONDITIONAL":
        return (
            "Memory Assist remains OFF by default. A limited staging experiment requires "
            "explicit operator approval and completion of listed conditions."
        )
    return (
        "This report supports a controlled staging experiment only. It does not authorize "
        "production enablement or default-ON behavior."
    )


def cap_ids(values: Any) -> tuple[int, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    out: list[int] = []
    for v in values:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
        if len(out) >= _ID_CAP:
            break
    return tuple(out)
