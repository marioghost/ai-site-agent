#!/usr/bin/env bash
# Deploy + smoke in one step.
#
#   bash scripts/deploy-and-smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash "$ROOT/scripts/deploy.sh" "$@"
bash "$ROOT/scripts/smoke.sh"
