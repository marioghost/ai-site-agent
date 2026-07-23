#!/usr/bin/env bash
# Local dev: backend (uvicorn --reload) + dashboard (vite).
# Loads secrets from repo .env automatically.
#
#   bash scripts/start-dev.sh          # both (backend in background)
#   bash scripts/start-dev.sh backend  # backend only
#   bash scripts/start-dev.sh dashboard
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-all}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT/.env"
  set +a
fi

start_backend() {
  cd "$ROOT/backend"
  if [[ ! -x .venv/bin/uvicorn ]]; then
    echo "ERROR: backend/.venv missing — run: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
  fi
  exec .venv/bin/uvicorn app.main:app \
    --host "${APP_HOST:-127.0.0.1}" \
    --port "${APP_PORT:-8000}" \
    --reload
}

start_dashboard() {
  cd "$ROOT/dashboard"
  if [[ ! -d node_modules ]]; then
    echo "==> npm install"
    npm install --silent
  fi
  exec npm run dev
}

case "$MODE" in
  backend)
    start_backend
    ;;
  dashboard|frontend)
    start_dashboard
    ;;
  all)
    echo "==> Backend http://${APP_HOST:-127.0.0.1}:${APP_PORT:-8000} (background)"
    echo "==> Dashboard http://localhost:5173"
    bash "$ROOT/scripts/run_backend.sh" &
    BACKEND_PID=$!
    trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT INT TERM
    sleep 2
    start_dashboard
    ;;
  *)
    echo "Usage: $0 [all|backend|dashboard]" >&2
    exit 1
    ;;
esac
