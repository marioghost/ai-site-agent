#!/usr/bin/env bash
# DEPRECATED wrapper — use: bash deploy/manage_deploy.sh smoke
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$ROOT/deploy/manage_deploy.sh" smoke "$@"
