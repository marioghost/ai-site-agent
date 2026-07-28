#!/usr/bin/env bash
# Shared deploy/runtime paths — sourced by deploy/smoke scripts.
# Reads deploy/deploy.local.conf (paths) and optional admin overrides from repo .env.
set -euo pipefail

DEPLOY_ENV_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_LOCAL_CONF="${DEPLOY_LOCAL_CONF:-$DEPLOY_ENV_ROOT/deploy/deploy.local.conf}"

PROJECT_ROOT="${PROJECT_ROOT:-/opt/ai-site-agent}"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8000/api/health}"
BACKEND_SERVICE_NAME="${BACKEND_SERVICE_NAME:-ai-agent-backend}"

if [[ -f "$DEPLOY_LOCAL_CONF" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$DEPLOY_LOCAL_CONF"
  set +a
fi

# Repo .env — dev secrets and optional SMOKE_* overrides (never committed if gitignored).
if [[ -f "$DEPLOY_ENV_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$DEPLOY_ENV_ROOT/.env"
  set +a
fi

# Live install .env may carry STAGING_ADMIN_* for release smoke (gitignored).
if [[ -n "${PROJECT_ROOT:-}" && -f "$PROJECT_ROOT/.env" && "$PROJECT_ROOT/.env" != "$DEPLOY_ENV_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$PROJECT_ROOT/.env"
  set +a
fi

STAGING_BASE_URL="${STAGING_BASE_URL:-${HEALTHCHECK_URL%/api/health}}"
STAGING_ADMIN_USER="${STAGING_ADMIN_USER:-admin}"
STAGING_ADMIN_PASSWORD="${STAGING_ADMIN_PASSWORD:-фвьшт}"

export PROJECT_ROOT ENV_FILE HEALTHCHECK_URL BACKEND_SERVICE_NAME
export STAGING_BASE_URL STAGING_ADMIN_USER STAGING_ADMIN_PASSWORD
