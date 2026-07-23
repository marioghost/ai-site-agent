#!/usr/bin/env bash
# Deploy this checkout → PROJECT_ROOT from deploy/deploy.local.conf (default /opt/ai-site-agent).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "$ROOT/scripts/deploy.sh" "$@"
