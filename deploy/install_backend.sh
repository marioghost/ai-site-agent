#!/usr/bin/env bash
#
# Install the backend into a Python virtual environment (no Docker).
# Run from the repository root:  bash deploy/install_backend.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
VENV_DIR="$BACKEND_DIR/.venv"

echo "==> Backend dir: $BACKEND_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.11+ first." >&2
  exit 1
fi

echo "==> Creating virtual environment"
python3 -m venv "$VENV_DIR"

echo "==> Installing Python dependencies"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$BACKEND_DIR/requirements.txt"

# Create .env from the example if it does not exist.
if [ ! -f "$REPO_ROOT/.env" ]; then
  echo "==> Creating .env from .env.example"
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
fi

# Apply PostgreSQL schema via Alembic (idempotent; safe to re-run).
# Requires DATABASE_URL in .env to point at a reachable PostgreSQL instance.
echo "==> Applying database migrations (alembic upgrade head)"
cd "$BACKEND_DIR"
"$VENV_DIR/bin/python" -m app.scripts.init_db

echo ""
echo "Backend installed. To run it:"
echo "  cd $BACKEND_DIR"
echo "  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000"
