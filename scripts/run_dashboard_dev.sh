#!/usr/bin/env bash
# Run the dashboard Vite dev server (proxies /api to the backend).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/dashboard"
exec npm run dev
