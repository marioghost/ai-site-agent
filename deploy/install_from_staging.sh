#!/usr/bin/env bash
#
# Convenience wrapper — install a prebuilt staging tree into /opt/ai-site-agent.
#
#   bash deploy/prepare_staging.sh          # build venv + dashboard in /tmp (no sudo)
#   sudo bash deploy/install_from_staging.sh
#
# Delegates to the single source of truth (manage_deploy.sh) with --use-staging,
# which rsyncs $STAGING_DIR -> /opt, runs alembic migrations, rebuilds as needed,
# and restarts the backend. PostgreSQL only (legacy SQLite copy steps removed).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGE="${STAGING_DIR:-/tmp/ai-site-agent-deploy}"

if [ ! -d "$STAGE/backend" ]; then
  echo "ERROR: staging missing at $STAGE. Run: bash deploy/prepare_staging.sh" >&2
  exit 1
fi

export PROJECT_ROOT="${PROJECT_ROOT:-/opt/ai-site-agent}"
export STAGING_DIR="$STAGE"

exec bash "$SCRIPT_DIR/manage_deploy.sh" --mode full --use-staging --yes "$@"
