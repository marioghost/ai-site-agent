#!/usr/bin/env bash
# Golden chat parity tests (release-check step 2).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="$ROOT/backend"
VENV="${BACKEND}/.venv"

if [[ ! -x "$VENV/bin/pytest" ]]; then
  echo "ERROR: backend venv missing" >&2
  exit 1
fi

cd "$BACKEND"

echo "==> Golden parity tests"
"$VENV/bin/pytest" \
  tests/test_golden_chat_parity.py \
  tests/test_golden_queries_schema.py \
  -m unit -q "$@"

echo "OK: golden parity tests passed"
