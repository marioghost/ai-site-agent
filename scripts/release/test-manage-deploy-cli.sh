#!/usr/bin/env bash
# Regression: manage_deploy CLI entry points exist and route correctly.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MD="$ROOT/deploy/manage_deploy.sh"

out="$(bash "$MD" help 2>&1 || true)"
echo "$out" | grep -q 'deploy full' || { echo "FAIL: help missing deploy full" >&2; exit 1; }
echo "$out" | grep -q 'verify-release' || { echo "FAIL: help missing verify-release" >&2; exit 1; }
echo "$out" | grep -q 'release status' || { echo "FAIL: help missing release status" >&2; exit 1; }

# Unknown command fails
if bash "$MD" not-a-real-command >/dev/null 2>&1; then
  echo "FAIL: unknown command should fail" >&2
  exit 1
fi
echo "OK: manage_deploy CLI regression passed"
