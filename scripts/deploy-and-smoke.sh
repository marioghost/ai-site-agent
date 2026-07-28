#!/usr/bin/env bash
# DEPRECATED wrapper — use: manage_deploy.sh deploy full && manage_deploy.sh smoke
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT/deploy/manage_deploy.sh" deploy full "$@"
exec bash "$ROOT/deploy/manage_deploy.sh" smoke
