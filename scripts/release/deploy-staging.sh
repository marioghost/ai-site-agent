#!/usr/bin/env bash
# DEPRECATED alias — use: bash deploy/manage_deploy.sh deploy full
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "$ROOT/deploy/manage_deploy.sh" deploy full "$@"
