"""JSON and Markdown report writers for Step 049 offline evaluation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.evaluation.memory_assist_eval_types import (
    MemoryAssistEvalReportV1,
    activation_statement,
)


def report_to_json_dict(report: MemoryAssistEvalReportV1) -> dict[str, Any]:
    return report.to_dict()


def write_json_report(report: MemoryAssistEvalReportV1, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = report_to_json_dict(report)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def render_markdown_report(report: MemoryAssistEvalReportV1) -> str:
    data = report.to_dict()
    meta = data["run_metadata"]
    corpus = data["corpus_snapshot"]
    assist = data["assist_summary"]
    shadow = data["shadow_summary"]
    cache = data["cache_summary"]
    thresholds = data["thresholds"]
    qs = data["query_set_summary"]

    lines: list[str] = [
        "# Memory Assist Offline Evaluation Report (v1)",
        "",
        "## Warning",
        "",
        "This is an **offline descriptive evaluation** of Memory Assist / Canonical Shadow "
        "diagnostics. Metrics are engineering coverage signals — **not** accuracy, "
        "correctness, answer quality, or Memory truth.",
        "",
        "These thresholds are operational engineering gates, not measures of knowledge accuracy.",
        "",
        "## Run metadata",
        "",
        f"- **Environment:** `{meta['environment']}`",
        f"- **Fixture:** `{meta['fixture_name']}`",
        f"- **App release:** `{meta['app_release']}`",
        f"- **Generated at:** `{data['generated_at']}`",
        f"- **Git commit:** `{meta.get('git_commit') or 'n/a'}`",
        f"- **Alembic head:** `{meta.get('alembic_head') or 'n/a'}`",
        f"- **Query count:** {meta['query_count']}",
        "",
        "## Corpus snapshot",
        "",
        f"- sources: {corpus['sources']}",
        f"- chunks: {corpus['chunks']}",
        f"- claims: {corpus['claims']} (real={corpus['real_claims']}, test={corpus['test_claims']})",
        f"- observations: {corpus['observations']}",
        f"- evidence_links: {corpus['evidence_links']}",
        f"- supported_claims: {corpus['supported_claims']}",
        f"- distinct_real_source_ids: {corpus['distinct_real_source_ids']}",
        f"- knowledge_version: {corpus.get('knowledge_version')}",
        f"- memory_version: {corpus.get('memory_version')}",
        f"- corpus_scope_configured: {corpus['corpus_scope_configured']}",
        f"- memory_shadow_write_enabled: {corpus['memory_shadow_write_enabled']}",
        "",
        "## Query-set coverage",
        "",
        f"- total_turns: {qs['total_turns']}",
        f"- unique_query_ids: {qs['unique_query_ids']}",
        f"- duplicate_query_id_count: {qs['duplicate_query_id_count']}",
        f"- input_error_count: {qs['input_error_count']}",
        f"- skipped_invalid_count: {qs['skipped_invalid_count']}",
        "",
        "## Assist summary",
        "",
        f"- assist_attempted_count: {assist['assist_attempted_count']}",
        f"- assist_effective_count: {assist['assist_effective_count']}",
        f"- empty_memory_rate_among_attempted: {assist['empty_memory_rate_among_attempted']}",
        f"- sparse_memory_rate_among_attempted: {assist['sparse_memory_rate_among_attempted']}",
        f"- failed_rate_among_attempted: {assist['failed_rate_among_attempted']}",
        f"- usable_for_evidence_rate_among_attempted: {assist['usable_for_evidence_rate_among_attempted']}",
        f"- path histogram: `{json.dumps(assist['assist_path_histogram'], ensure_ascii=False)}`",
        "",
        "## Shadow summary",
        "",
        f"- compared_count: {shadow['compared_count']}",
        f"- path histogram: `{json.dumps(shadow['shadow_path_histogram'], ensure_ascii=False)}`",
        f"- alignment histogram: `{json.dumps(shadow['canonical_alignment_histogram'], ensure_ascii=False)}`",
        f"- support_missing_from_context_rate_among_compared: "
        f"{shadow['support_missing_from_context_rate_among_compared']}",
        "",
        "## Divergence histogram",
        "",
        f"`{json.dumps(data['divergence_code_histogram'], ensure_ascii=False)}`",
        "",
        "## Cache-hit limitations",
        "",
        f"- cache_hit_count: {cache['cache_hit_count']}",
        f"- evaluable_turn_count: {cache['evaluable_turn_count']}",
        f"- missing_shadow_due_to_cache_hit_count: {cache['missing_shadow_due_to_cache_hit_count']}",
        f"- shadow_observation_rate: {cache['shadow_observation_rate']}",
        "",
        "## Thresholds used",
        "",
        f"`{json.dumps(thresholds, ensure_ascii=False)}`",
        "",
        "## Recommendation",
        "",
        f"**{data['recommendation']}**",
        "",
        "### Recommendation reasons",
        "",
    ]
    for reason in data["recommendation_reasons"]:
        lines.append(f"- `{reason}`")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
        ]
    )
    for lim in data["report_limitations"]:
        lines.append(f"- `{lim}`")
    for lim, count in data["limitation_histogram"].items():
        lines.append(f"- `{lim}` × {count}")
    lines.extend(
        [
            "",
            "## Activation statement",
            "",
            activation_statement(data["recommendation"]),
            "",
            "## Explicit non-claims",
            "",
            "- Does **not** authorize production enablement.",
            "- Does **not** set flags default ON.",
            "- Does **not** claim answer quality improvement.",
            "- Does **not** claim Memory or canonical correctness.",
            "- Step 050 (Release 0.7 closure) remains separate.",
            "",
        ]
    )
    return "\n".join(lines)


def write_markdown_report(report: MemoryAssistEvalReportV1, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_markdown_report(report), encoding="utf-8")
