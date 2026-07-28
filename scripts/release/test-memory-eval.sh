#!/usr/bin/env bash
# Step 049 — offline Memory Assist evaluation (fixtures only; no live services).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/backend"
echo "=== Step 049 memory-eval unit tests ==="
.venv/bin/pytest tests/test_memory_assist_eval.py -m unit -q
echo "=== Step 049 CLI dry-run (sparse NO_GO fixture) ==="
.venv/bin/python scripts/run_memory_assist_eval.py \
  --input tests/fixtures/memory_assist_eval/sample_turns.json \
  --corpus-snapshot tests/fixtures/memory_assist_eval/corpus_snapshot_sparse_nogo.json \
  --output-json /tmp/memory_assist_eval_report.v1.json \
  --output-markdown /tmp/memory_assist_eval_report.v1.md \
  --environment ci \
  --fixture-name sample-sparse-nogo \
  --dry-run
echo "OK: test-memory-eval"
