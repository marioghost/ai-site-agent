#!/usr/bin/env bash
# DEPRECATED wrapper — use: sudo bash deploy/manage_deploy.sh deploy full
#
#   bash scripts/deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "NOTE: scripts/deploy.sh → manage_deploy.sh deploy full (origin/main only)" >&2

if [[ "$(id -u)" -eq 0 ]]; then
  exec bash deploy/manage_deploy.sh deploy full "$@"
elif command -v sudo &>/dev/null; then
  exec sudo bash deploy/manage_deploy.sh deploy full "$@"
else
  echo "ERROR: deploy needs sudo for systemd/nginx" >&2
  exit 1
fi
