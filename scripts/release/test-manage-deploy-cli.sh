#!/usr/bin/env bash
# Regression: manage_deploy CLI entry points exist and route correctly.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MD="$ROOT/deploy/manage_deploy.sh"

out="$(bash "$MD" help 2>&1 || true)"
echo "$out" | grep -q 'deploy full' || { echo "FAIL: help missing deploy full" >&2; exit 1; }
echo "$out" | grep -q 'verify-release' || { echo "FAIL: help missing verify-release" >&2; exit 1; }
echo "$out" | grep -q 'release status' || { echo "FAIL: help missing release status" >&2; exit 1; }
echo "$out" | grep -q 'migrate release' || { echo "FAIL: help missing migrate release" >&2; exit 1; }
echo "$out" | grep -q 'migrate live' || { echo "FAIL: help missing migrate live" >&2; exit 1; }
echo "$out" | grep -qi 'alias of bare migrate' || { echo "FAIL: help must say migrate live is alias" >&2; exit 1; }
echo "$out" | grep -qiE 'post-sync|idempotent|ONE command|Normal release' \
  || { echo "FAIL: help must mention one-command / post-sync policy" >&2; exit 1; }
echo "$out" | grep -q '^  status' || { echo "FAIL: help missing status command" >&2; exit 1; }
echo "$out" | grep -qiE 'backup|preflight|migration decision' \
  || { echo "FAIL: help should mention deploy pipeline stages" >&2; exit 1; }

# status command should run (may exit 1 if /opt stale — still must print Overall)
status_out="$(bash "$MD" status 2>&1 || true)"
echo "$status_out" | grep -q 'Overall:' || { echo "FAIL: status missing Overall" >&2; exit 1; }
echo "$status_out" | grep -q 'Repository' || { echo "FAIL: status missing Repository" >&2; exit 1; }
echo "$status_out" | grep -q 'build-info' || { echo "FAIL: status missing build-info" >&2; exit 1; }
echo "OK: status command produces report"

# Unknown command fails
if bash "$MD" not-a-real-command >/dev/null 2>&1; then
  echo "FAIL: unknown command should fail" >&2
  exit 1
fi
echo "OK: manage_deploy CLI regression passed"
