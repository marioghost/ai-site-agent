#!/usr/bin/env bash
# Release verification — thin wrapper over shared core.
# Usage: bash scripts/release/verify-release.sh
#        bash deploy/manage_deploy.sh verify-release
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib/verify_release.sh
source "$ROOT/deploy/lib/verify_release.sh"
# shellcheck source=scripts/lib/deploy-env.sh
source "$ROOT/scripts/lib/deploy-env.sh" 2>/dev/null || true

md_verify_release_run "$ROOT" "${PROJECT_ROOT:-/opt/ai-site-agent}" "" ""
