#!/usr/bin/env bash
#
# Install dashboard dependencies and produce a production build (static files).
# Run from the repository root:  bash deploy/install_dashboard.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARD_DIR="$REPO_ROOT/dashboard"

if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm not found. Install Node.js 18+ first." >&2
  exit 1
fi

echo "==> Installing npm dependencies"
cd "$DASHBOARD_DIR"
npm install

echo "==> Building production bundle"
npm run build

echo ""
echo "Dashboard built to: $DASHBOARD_DIR/dist"
echo "Point Nginx 'root' at that directory (see deploy/nginx.conf.example)."
