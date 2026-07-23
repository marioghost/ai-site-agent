#!/usr/bin/env bash
# Deploy this checkout → /opt/ai-site-agent (uses deploy/deploy.local.conf + /opt/.env).
#
#   bash scripts/deploy.sh
#   bash scripts/deploy.sh --no-backup-db
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/lib/deploy-env.sh"

echo "==> Deploy to $PROJECT_ROOT"
echo "    Env:    $ENV_FILE"
echo "    Health: $HEALTHCHECK_URL"

bash "$ROOT/scripts/release/write-build-info.sh"

if [[ "$(id -u)" -eq 0 ]]; then
  exec bash deploy/sync_to_opt.sh "$@"
elif command -v sudo &>/dev/null; then
  exec sudo bash deploy/sync_to_opt.sh "$@"
else
  echo "ERROR: deploy needs sudo for systemd/nginx" >&2
  exit 1
fi
