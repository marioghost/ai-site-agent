#!/usr/bin/env bash
# Bootstrap staging directories and .env on a Linux server.
#
#   cp deploy/deploy.staging.local.conf.example deploy/deploy.staging.local.conf
#   make init-staging
#   # edit PROJECT_ROOT/.env with real secrets
#   make deploy-staging
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

DEPLOY_CONF="${STAGING_DEPLOY_CONF:-deploy/deploy.staging.local.conf}"
ENV_TEMPLATE="${STAGING_ENV_TEMPLATE:-.env.staging.example}"

if [[ ! -f "$DEPLOY_CONF" ]]; then
  echo "ERROR: missing $DEPLOY_CONF" >&2
  echo "  cp deploy/deploy.staging.local.conf.example deploy/deploy.staging.local.conf" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$DEPLOY_CONF"
set +a

STAGING_ROOT="${PROJECT_ROOT:?PROJECT_ROOT must be set in $DEPLOY_CONF}"
TARGET_ENV="${ENV_FILE:-$STAGING_ROOT/.env}"
BACKUP="${BACKUP_DIR:-$STAGING_ROOT/backups}"
LOGS="${LOG_DIR:-$STAGING_ROOT/logs}"
APP_USER="${APP_USER:-www-data}"

run_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo &>/dev/null; then
    sudo "$@"
  else
    echo "ERROR: need root or sudo to create $STAGING_ROOT" >&2
    exit 1
  fi
}

echo "==> Create staging directories"
run_root mkdir -p "$STAGING_ROOT" "$BACKUP" "$LOGS"

if [[ ! -f "$TARGET_ENV" ]]; then
  if [[ ! -f "$ENV_TEMPLATE" ]]; then
    echo "ERROR: missing template $ENV_TEMPLATE" >&2
    exit 1
  fi
  echo "==> Install $TARGET_ENV from $ENV_TEMPLATE"
  run_root cp "$ROOT/$ENV_TEMPLATE" "$TARGET_ENV"
  run_root chmod 600 "$TARGET_ENV"
else
  echo "OK: $TARGET_ENV already exists (unchanged)"
fi

if id "$APP_USER" &>/dev/null; then
  run_root chown -R "$APP_USER:$APP_USER" "$STAGING_ROOT" 2>/dev/null || \
    run_root chown -R "$APP_USER" "$STAGING_ROOT" 2>/dev/null || true
fi

echo ""
echo "OK: staging bootstrap complete"
echo "  PROJECT_ROOT: $STAGING_ROOT"
echo "  ENV_FILE:     $TARGET_ENV"
echo ""
echo "Next:"
echo "  1. Edit $TARGET_ENV (DATABASE_URL, JWT_SECRET_KEY, passwords)"
echo "  2. make deploy-staging"
echo "  3. make smoke-staging"
