#!/usr/bin/env bash
# Build a fresh deploy tree in /tmp (no sudo). Then run install_from_staging.sh.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="/tmp/ai-site-agent-deploy"

echo "==> Staging to $STAGE"
rm -rf "$STAGE"
mkdir -p "$STAGE"

rsync -a \
  --exclude '.venv' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.git' \
  "$SRC/" "$STAGE/"

echo "==> Python venv"
cd "$STAGE/backend"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "==> Dashboard build"
cd "$STAGE/dashboard"
npm install --silent
npm run build

echo "==> Staged. Dashboard JS:"
ls -la "$STAGE/dashboard/dist/assets/"*.js
echo "Run: sudo bash $SRC/deploy/install_from_staging.sh"
