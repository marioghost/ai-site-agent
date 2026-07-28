#!/usr/bin/env bash
#
# DEPRECATED wrapper — use: sudo bash deploy/manage_deploy.sh deploy full
#
# Release deploy: clean origin/main worktree only.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "NOTE: deploy_from_main.sh is a thin wrapper → manage_deploy.sh deploy full" >&2
exec bash "$SCRIPT_DIR/manage_deploy.sh" deploy full "$@"
