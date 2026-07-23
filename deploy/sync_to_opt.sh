#!/usr/bin/env bash
#
# Convenience wrapper — deploy THIS checkout to /opt/ai-site-agent.
#
#   sudo bash deploy/sync_to_opt.sh
#
# Runs the full pipeline through the single source of truth (manage_deploy.sh):
#   stop backend -> pg_dump backup -> rsync code -> venv deps
#   -> alembic upgrade head -> build dashboard -> restart backend -> health check
#
# PostgreSQL only. The legacy SQLite backup/copy steps were removed —
# database backups are handled by manage_deploy.sh (pg_dump).
#
# Any extra flags are forwarded to manage_deploy.sh, e.g.:
#   sudo bash deploy/sync_to_opt.sh --no-backup-db
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT="${PROJECT_ROOT:-/opt/ai-site-agent}"

exec bash "$SCRIPT_DIR/manage_deploy.sh" --mode full --sync-from-dev --yes "$@"
