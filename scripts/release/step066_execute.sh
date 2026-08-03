#!/usr/bin/env bash
# RFC-100 Step 066 — full execution orchestrator (designated /opt staging).
# Run from an authenticated operator TTY with sudo + git push credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export STAGING_BASE_URL="${STAGING_BASE_URL:-http://127.0.0.1:8000}"

echo "==> [1/4] Preflight health/build"
curl -sfS --max-time 30 "$STAGING_BASE_URL/api/health" >/dev/null
curl -sfS --max-time 30 "$STAGING_BASE_URL/api/build" | tee /tmp/step066-pre-build.json | python3 -m json.tool >/dev/null

echo "==> [2/4] Load harness (warmup + 60m sustained + cancel/overload) — long running"
"$ROOT/backend/.venv/bin/python" "$ROOT/scripts/release/step066_load_harness.py" \
  --config "$ROOT/docs/releases/1.0-step-066-load-config.json" \
  --results "$ROOT/docs/releases/1.0-step-066-load-results.json"

echo "==> [3/4] Service restart drill"
bash "$ROOT/scripts/release/step066_restart_drill.sh"

echo "==> [4/4] Tip rollback drill (requires clean tree + push)"
# Move Step 066 untracked/modified files aside so tip drill sees a clean tree
STASH_DIR="/tmp/step066-aside-$$"
mkdir -p "$STASH_DIR"
# shellcheck disable=SC2046
rsync -a --relative $(git status --porcelain | awk '{print $2}') "$STASH_DIR/" 2>/dev/null || true
git stash push -u -m "step066-aside" || true
bash "$ROOT/scripts/release/step066_tip_drill.sh"
git stash pop || true

echo "OK: Step 066 execution orchestrator finished — write/update implementation report"
