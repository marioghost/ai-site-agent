#!/usr/bin/env python3
"""CLI: offline Memory Assist / Canonical Shadow evaluation (RFC-100 Step 049).

Fixture ingestion + aggregation + reporting only.
Does not enable flags, call chat/Qdrant/DB, or mutate application state.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend package root is importable when run as a script.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.evaluation.memory_assist_eval_aggregator import (  # noqa: E402
    EvalInputError,
    aggregate_memory_assist_eval,
    validate_environment,
)
from app.services.evaluation.memory_assist_eval_report import (  # noqa: E402
    write_json_report,
    write_markdown_report,
)
from app.services.evaluation.memory_assist_eval_types import (  # noqa: E402
    CorpusEvalSnapshot,
    EvalFlagSnapshot,
    EvalRunMetadata,
    MemoryAssistEvalThresholdsV1,
)


def _load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_turns(path: Path) -> list:
    data = _load_json(path)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "turns" in data:
        return list(data["turns"])
    raise SystemExit(f"input must be a list or {{'turns': [...]}}: {path}")


def _load_corpus(path: Path | None) -> CorpusEvalSnapshot:
    if path is None:
        return CorpusEvalSnapshot()
    data = _load_json(path)
    if not isinstance(data, dict):
        raise SystemExit("corpus snapshot must be a JSON object")
    known = {f.name for f in CorpusEvalSnapshot.__dataclass_fields__.values()}
    return CorpusEvalSnapshot(**{k: v for k, v in data.items() if k in known})


def _load_thresholds(path: Path | None) -> MemoryAssistEvalThresholdsV1:
    if path is None:
        return MemoryAssistEvalThresholdsV1()
    data = _load_json(path)
    if not isinstance(data, dict):
        raise SystemExit("thresholds must be a JSON object")
    return MemoryAssistEvalThresholdsV1.from_mapping(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline Memory Assist evaluation (Step 049) — fixtures only"
    )
    parser.add_argument("--input", required=True, help="Path to turns JSON fixture")
    parser.add_argument("--corpus-snapshot", default=None, help="Optional corpus snapshot JSON")
    parser.add_argument("--output-json", required=True, help="Output JSON report path")
    parser.add_argument("--output-markdown", required=True, help="Output Markdown report path")
    parser.add_argument(
        "--environment",
        required=True,
        choices=["local", "ci", "staging"],
        help="Evaluation environment (production rejected)",
    )
    parser.add_argument("--fixture-name", default="", help="Fixture label for the report")
    parser.add_argument("--thresholds", default=None, help="Optional thresholds JSON")
    parser.add_argument("--include-turns", action="store_true", help="Include per-query rows")
    parser.add_argument("--lenient", action="store_true", help="Skip invalid records")
    parser.add_argument("--allow-duplicate-query-ids", action="store_true")
    parser.add_argument("--git-commit", default=None)
    parser.add_argument("--alembic-head", default=None)
    parser.add_argument("--app-release", default="0.7")
    parser.add_argument("--dry-run", action="store_true", help="Aggregate and print recommendation only")
    args = parser.parse_args(argv)

    try:
        validate_environment(args.environment)
    except EvalInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    turns = _load_turns(Path(args.input))
    corpus = _load_corpus(Path(args.corpus_snapshot) if args.corpus_snapshot else None)
    thresholds = _load_thresholds(Path(args.thresholds) if args.thresholds else None)

    metadata = EvalRunMetadata(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        git_commit=args.git_commit,
        alembic_head=args.alembic_head,
        app_release=args.app_release,
        environment=args.environment,
        fixture_name=args.fixture_name or Path(args.input).stem,
        query_count=len(turns),
        flag_snapshot=EvalFlagSnapshot(),
        corpus_snapshot=corpus,
    )

    try:
        report = aggregate_memory_assist_eval(
            turns,
            metadata=metadata,
            thresholds=thresholds,
            include_turns=args.include_turns,
            allow_duplicate_query_ids=args.allow_duplicate_query_ids,
            lenient=args.lenient,
        )
    except EvalInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"recommendation={report.recommendation}")
    print(f"reasons={list(report.recommendation_reasons)}")
    print(f"turns={report.query_set_summary.total_turns}")

    if args.dry_run:
        return 0

    write_json_report(report, args.output_json)
    write_markdown_report(report, args.output_markdown)
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
