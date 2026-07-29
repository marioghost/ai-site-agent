#!/usr/bin/env bash
# Pre-release gate — run before staging deploy or marking a release production-ready.
#
#   make release-check
#
# Optional:
#   POSTGRES_TEST_URL=postgresql+psycopg://...  — enables migration up/down/up test
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/lib/test-db-env.sh"

STEP=0
FAILURES=0

run_required() {
  local label="$1"
  shift
  STEP=$((STEP + 1))
  echo ""
  echo "========================================"
  echo "[$STEP] $label"
  echo "========================================"
  if "$@"; then
    echo "OK: $label"
  else
    echo "FAIL: $label" >&2
    FAILURES=$((FAILURES + 1))
    return 1
  fi
}

echo "==> Release check started $(date -u +%Y-%m-%dT%H:%M:%SZ)"

bash "$ROOT/scripts/release/write-build-info.sh"

run_required "Backend unit tests" bash "$ROOT/scripts/release/test-backend-unit.sh"
run_required "Deploy rsync excludes" bash "$ROOT/scripts/release/test-deploy-rsync-excludes.sh"
run_required "Deploy guard" bash "$ROOT/scripts/release/test-deploy-guard.sh"
run_required "Manage deploy CLI" bash "$ROOT/scripts/release/test-manage-deploy-cli.sh"
run_required "Migrate release CLI" bash "$ROOT/scripts/release/test-migrate-release.sh"
run_required "Migrate machine orchestrator" bash "$ROOT/scripts/release/test-migrate-machine.sh"
run_required "Schema-first docs" bash "$ROOT/scripts/release/test-schema-first-docs.sh"
run_required "Golden parity tests" bash "$ROOT/scripts/release/test-golden.sh"

cd "$ROOT/dashboard"
if [[ ! -d node_modules ]]; then
  run_required "Dashboard npm install" npm install --silent
fi
run_required "Dashboard vitest" npm test
run_required "TypeScript check" npx tsc --noEmit
run_required "Dashboard production build" npm run build

if [[ -n "${POSTGRES_TEST_URL:-}" ]]; then
  run_required "Migration test" bash "$ROOT/scripts/release/test-migration.sh"
else
  STEP=$((STEP + 1))
  echo ""
  echo "[$STEP] Migration test — SKIP (set disposable POSTGRES_TEST_URL; never uses app DATABASE_URL)"
fi

STEP=$((STEP + 1))
echo ""
echo "========================================"
echo "[$STEP] Docker build validation (optional)"
echo "========================================"
bash "$ROOT/scripts/release/test-docker.sh"

echo ""
if [[ "$FAILURES" -eq 0 ]]; then
  echo "OK: release-check passed ($STEP steps)"
  echo "Next: make deploy && make smoke  (see docs/STAGING-SEED-SMOKE.md)"
  exit 0
fi

echo "FAIL: release-check had $FAILURES failure(s)" >&2
exit 1
