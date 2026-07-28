#!/usr/bin/env bash
#
# DEPRECATED wrapper — use: sudo bash deploy/manage_deploy.sh deploy full
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT="${PROJECT_ROOT:-/opt/ai-site-agent}"
echo "NOTE: sync_to_opt.sh is a thin wrapper → manage_deploy.sh deploy full" >&2
exec bash "$SCRIPT_DIR/manage_deploy.sh" deploy full "$@"
