#!/usr/bin/env bash
# Optional backend benchmarks — NOT part of make release-check.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="$ROOT/backend"
VENV="${BACKEND}/.venv"

if [[ ! -x "$VENV/bin/pytest" ]]; then
  echo "ERROR: backend venv missing." >&2
  exit 1
fi

cd "$BACKEND"

echo "==> Backend benchmarks (optional, wall-clock)"
"$VENV/bin/pytest" tests/test_chat_stream_dispatch_benchmark.py -m benchmark -v "$@"

echo "OK: backend benchmarks passed"
