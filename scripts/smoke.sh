#!/usr/bin/env bash
# Post-deploy smoke — health, metrics, settings (admin creds from deploy-env defaults).
#
#   bash scripts/smoke.sh
#   SMOKE_CHAT=1 bash scripts/smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/lib/deploy-env.sh"

echo "==> Smoke: $STAGING_BASE_URL"
exec bash scripts/release/smoke-staging.sh
