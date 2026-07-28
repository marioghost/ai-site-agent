#!/usr/bin/env bash
# AI Site Agent — canonical deployment & operations manager (SSH-friendly).
#
# Stack: systemd backend + nginx frontend + local Ollama + local Qdrant + PostgreSQL.
# No Docker. Single public entry point for release engineering.
#
# Preferred release deploy (origin/main only):
#   cd /path/to/ai-site-agent && sudo bash deploy/manage_deploy.sh deploy full
#   bash deploy/manage_deploy.sh verify-release
#
# Interactive menu:
#   sudo bash deploy/manage_deploy.sh
#
# Legacy flags still accepted (deprecated):
#   bash deploy/manage_deploy.sh --mode full|backend|frontend|...
#   bash deploy/manage_deploy.sh --action start-all|status|...
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=deploy/lib/deploy_guard.sh
source "$SCRIPT_DIR/lib/deploy_guard.sh"

export PROJECT_ROOT="${PROJECT_ROOT:-$REPO_ROOT}"

# shellcheck source=deploy.conf
source "$SCRIPT_DIR/deploy.conf"

if [[ "${DEPLOY_SKIP_LOCAL_CONF:-0}" != "1" && -f "$SCRIPT_DIR/deploy.local.conf" ]]; then
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/deploy.local.conf"
fi

PROJECT_ROOT="${PROJECT_ROOT:-$REPO_ROOT}"
BACKEND_DIR="${BACKEND_DIR:-$PROJECT_ROOT/backend}"
DASHBOARD_DIR="${DASHBOARD_DIR:-$PROJECT_ROOT/dashboard}"
VENV_DIR="${VENV_DIR:-$BACKEND_DIR/.venv}"
FRONTEND_BUILD_DIR="${FRONTEND_BUILD_DIR:-$DASHBOARD_DIR/dist}"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
LOG_DIR="${LOG_DIR:-$PROJECT_ROOT/logs}"

# Source of code to rsync into PROJECT_ROOT. Prefer explicit DEV_CHECKOUT when
# manage_deploy is launched from /opt (REPO_ROOT == PROJECT_ROOT), otherwise
# use the checkout that contains this script.
DEV_CHECKOUT="${DEV_CHECKOUT:-}"
SYNC_SOURCE="$REPO_ROOT"

# PostgreSQL connection (parsed from DATABASE_URL in load_env_overrides).
PG_HOST="" PG_PORT="" PG_USER="" PG_PASSWORD="" PG_DB=""

MODE=""
ACTION=""
CLI_MODULE=""
INTERACTIVE=1
ASSUME_YES=0
DO_GIT_PULL=""
DO_BACKUP_DB=""
DO_NPM_INSTALL=""
DO_RELOAD_NGINX=""
CLEAR_DB=0
CLEAR_QDRANT=0
CLEAR_CACHES=0
CLEAR_FRONTEND_BUILD=0
RECREATE_VENV=0
USE_STAGING_FLAG=""
SYNC_FROM_DEV=""
SYNC_FROM_DEV_FLAG=""

mkdir -p "$LOG_DIR" "$BACKUP_DIR"
LOG_FILE="$LOG_DIR/deploy-$(date +%Y%m%d_%H%M%S).log"

# ---------------------------------------------------------------------------
# Output helpers (plain text works over SSH; color when TTY)
# ---------------------------------------------------------------------------
_color() {
  local code="$1"
  shift
  if [[ -t 1 ]]; then
    printf "\033[%sm%s\033[0m\n" "$code" "$*"
  else
    printf "%s\n" "$*"
  fi
}

write_log() { (echo "$*" >>"$LOG_FILE") 2>/dev/null || true; }
log_info()  { _color "0;36" "[INFO] $*"; write_log "[INFO] $*"; }
log_ok()    { _color "0;32" "[OK]   $*"; write_log "[OK]   $*"; }
log_warn()  { _color "0;33" "[WARN] $*"; write_log "[WARN] $*"; }
log_error() { _color "0;31" "[ERROR] $*"; write_log "[ERROR] $*"; }
log_section() {
  echo ""
  _color "1;37" "=== $* ==="
  write_log "=== $* ==="
}

pause_menu() {
  [[ "$INTERACTIVE" -eq 1 ]] || return 0
  echo ""
  read -r -p "Press Enter to return to the menu..." _
}

run_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo &>/dev/null; then
    sudo "$@"
  else
    log_error "Need root or sudo for: $*"
    return 1
  fi
}

has_sudo() {
  [[ "$(id -u)" -eq 0 ]] || command -v sudo &>/dev/null
}

resolve_sync_source() {
  local candidate=""
  if [[ -n "${DEV_CHECKOUT:-}" ]]; then
    candidate="$(cd "${DEV_CHECKOUT}" 2>/dev/null && pwd || true)"
  fi
  if [[ -n "$candidate" && -d "$candidate/backend" && -d "$candidate/dashboard" ]]; then
    SYNC_SOURCE="$candidate"
  else
    if [[ -n "${DEV_CHECKOUT:-}" ]]; then
      log_warn "DEV_CHECKOUT=${DEV_CHECKOUT} is missing or incomplete — falling back to script checkout"
    fi
    SYNC_SOURCE="$REPO_ROOT"
  fi
}

prepend_path_dir() {
  local dir="$1"
  [[ -n "$dir" && -d "$dir" ]] || return 0
  case ":$PATH:" in
    *":$dir:"*) ;;
    *) PATH="$dir:$PATH" ;;
  esac
}

# sudo resets PATH; nvm/fnm/asdf often live only in the invoking user's shell.
augment_path_for_node() {
  local owner home nvm_bin fnm_bin asdf_shims

  if [[ -n "${NPM_BIN:-}" ]]; then
    prepend_path_dir "$(dirname "$NPM_BIN")"
  fi
  if [[ -n "${NODE_BIN:-}" ]]; then
    prepend_path_dir "$(dirname "$NODE_BIN")"
  fi

  owner="${SUDO_USER:-${USER:-}}"
  if [[ -n "$owner" && "$owner" != "root" ]]; then
    home="$(getent passwd "$owner" 2>/dev/null | cut -d: -f6 || true)"
    if [[ -n "$home" && -d "$home/.nvm/versions/node" ]]; then
      nvm_bin="$(ls -1d "$home/.nvm/versions/node/"*/bin 2>/dev/null | sort -V | tail -1 || true)"
      prepend_path_dir "$nvm_bin"
    fi
    fnm_bin="$(ls -1d "$home/.local/share/fnm/node-versions/"*/installation/bin 2>/dev/null | sort -V | tail -1 || true)"
    prepend_path_dir "$fnm_bin"
    asdf_shims="$home/.asdf/shims"
    prepend_path_dir "$asdf_shims"
    prepend_path_dir "$home/.local/bin"
  fi

  prepend_path_dir "/usr/local/bin"
  export PATH
}

npm_cmd() {
  if [[ -n "${NPM_BIN:-}" && -x "$NPM_BIN" ]]; then
    echo "$NPM_BIN"
  elif command -v npm &>/dev/null; then
    command -v npm
  else
    return 1
  fi
}

# ---------------------------------------------------------------------------
# Config / environment
# ---------------------------------------------------------------------------
parse_database_url() {
  # Parse DATABASE_URL (postgresql+psycopg://user:pass@host:port/db) into PG_*.
  local url="${DATABASE_URL:-}"
  PG_HOST="" PG_PORT="" PG_USER="" PG_PASSWORD="" PG_DB=""
  [[ -n "$url" ]] || return 0
  local rest="${url#*://}"
  local userpass hostportdb hostport
  if [[ "$rest" == *@* ]]; then
    userpass="${rest%%@*}"
    hostportdb="${rest#*@}"
    PG_USER="${userpass%%:*}"
    [[ "$userpass" == *:* ]] && PG_PASSWORD="${userpass#*:}" || PG_PASSWORD=""
  else
    hostportdb="$rest"
    PG_USER="postgres"
  fi
  hostport="${hostportdb%%/*}"
  PG_DB="${hostportdb#*/}"; PG_DB="${PG_DB%%\?*}"
  PG_HOST="${hostport%%:*}"
  [[ "$hostport" == *:* ]] && PG_PORT="${hostport#*:}" || PG_PORT=5432
  [[ -n "$PG_HOST" ]] || PG_HOST=127.0.0.1
}

load_env_overrides() {
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # Strip CRLF — .env files edited on Windows/WSL break plain `source`.
    # shellcheck disable=SC1090
    source <(sed 's/\r$//' "$ENV_FILE")
    set +a
    HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://${APP_HOST:-127.0.0.1}:${APP_PORT:-8000}/api/health}"
  fi
  parse_database_url
  QDRANT_HOST="${QDRANT_HOST:-127.0.0.1}"
  QDRANT_PORT="${QDRANT_PORT:-6333}"
  DEFAULT_QDRANT_COLLECTION="${DEFAULT_QDRANT_COLLECTION:-site_knowledge}"
}

# Run psql as the postgres superuser (for create/drop role/db).
psql_super() {
  run_root -u postgres psql -v ON_ERROR_STOP=1 "$@"
}

# Run psql/pg tools as the application user against the app DB.
pg_env() {
  PGPASSWORD="$PG_PASSWORD" "$@" -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER"
}

detect_project_root() {
  # Production default: /opt/ai-site-agent when present and not already configured.
  if [[ "$PROJECT_ROOT" == "$REPO_ROOT" && -d /opt/ai-site-agent/backend && ! -f "$SCRIPT_DIR/deploy.local.conf" ]]; then
    if [[ "$INTERACTIVE" -eq 1 ]]; then
      echo ""
      log_info "Detected production install at /opt/ai-site-agent"
      if prompt_yn "Use /opt/ai-site-agent as PROJECT_ROOT?" "y"; then
        PROJECT_ROOT="/opt/ai-site-agent"
        BACKEND_DIR="$PROJECT_ROOT/backend"
        DASHBOARD_DIR="$PROJECT_ROOT/dashboard"
        VENV_DIR="$BACKEND_DIR/.venv"
        FRONTEND_BUILD_DIR="$DASHBOARD_DIR/dist"
        ENV_FILE="$PROJECT_ROOT/.env"
        BACKUP_DIR="$PROJECT_ROOT/backups"
        LOG_DIR="$PROJECT_ROOT/logs"
        load_env_overrides
      fi
    fi
  fi
}

show_banner() {
  resolve_sync_source
  echo ""
  _color "1;34" "╔══════════════════════════════════════════════════════════╗"
  _color "1;34" "║  AI Site Agent — Deploy & Operations Manager (Linux)      ║"
  _color "1;34" "╚══════════════════════════════════════════════════════════╝"
  echo ""
  echo "  Host:     $(hostname -f 2>/dev/null || hostname)"
  echo "  User:     $(whoami)"
  echo "  Project:  $PROJECT_ROOT"
  echo "  Script:   $REPO_ROOT"
  if paths_differ; then
    echo "  Sync from: $SYNC_SOURCE  →  $PROJECT_ROOT"
  else
    echo "  Sync from: (same as project — no rsync; rebuilds files already here)"
    if [[ -z "${DEV_CHECKOUT:-}" ]]; then
      log_warn "No DEV_CHECKOUT set. Running inside $PROJECT_ROOT will NOT pull ~/projects changes."
      log_warn "Fix: set DEV_CHECKOUT in deploy/deploy.local.conf, or run manage_deploy from the checkout."
    fi
  fi
  echo "  Backend:  $BACKEND_SERVICE_NAME (systemd)"
  echo "  Frontend: nginx → $FRONTEND_BUILD_DIR"
  echo "  Database: PostgreSQL @ ${PG_HOST:-?}:${PG_PORT:-?}/${PG_DB:-?} (user ${PG_USER:-?})"
  echo "  Vectors:  Qdrant @ ${QDRANT_HOST}:${QDRANT_PORT}"
  echo "  LLM:      Ollama (local)"
  echo "  Log file: $LOG_FILE"
  echo ""
  if ! has_sudo; then
    log_warn "sudo not available — systemd/nginx steps may fail"
  fi
}

preflight_check() {
  local ok=1
  log_section "Pre-flight checks"
  for cmd in python3 curl; do
    if command -v "$cmd" &>/dev/null; then
      log_ok "Found: $cmd"
    else
      log_error "Missing required command: $cmd"
      ok=0
    fi
  done
  if local_npm="$(npm_cmd 2>/dev/null)"; then
    log_ok "Found: npm ($("$local_npm" -v 2>/dev/null))"
  else
    log_warn "npm not found — frontend build will fail until Node.js is installed"
    if [[ -n "${SUDO_USER:-}" ]]; then
      log_info "Tip: sudo drops nvm from PATH — set NPM_BIN in deploy/deploy.local.conf or install node system-wide"
    fi
  fi
  if [[ -x "$VENV_DIR/bin/python" ]]; then
    log_ok "Python venv: $VENV_DIR"
  else
    log_warn "Python venv not found yet — will be created on backend deploy"
  fi
  if [[ -f "$ENV_FILE" ]]; then
    log_ok "Env file: $ENV_FILE"
  else
    log_warn "No .env at $ENV_FILE (using defaults)"
  fi
  if [[ -d "$PROJECT_ROOT/.git" ]]; then
    log_ok "Git repo: $(cd "$PROJECT_ROOT" && git rev-parse --short HEAD 2>/dev/null) on $(cd "$PROJECT_ROOT" && git branch --show-current 2>/dev/null)"
  fi
  [[ "$ok" -eq 1 ]]
}

check_dependency_services() {
  log_info "Checking dependency services (Ollama, Qdrant)..."
  for svc in "$QDRANT_SERVICE_NAME" "$OLLAMA_SERVICE_NAME"; do
    if run_root systemctl is-active --quiet "$svc" 2>/dev/null; then
      log_ok "$svc is running"
    else
      log_warn "$svc is not active — chat/indexing may fail until it is started"
      log_info "  Try: sudo systemctl start $svc"
    fi
  done
}

# ---------------------------------------------------------------------------
# Operations manager — module registry (start / stop / restart / status / logs)
# ---------------------------------------------------------------------------

module_service_name() {
  case "$1" in
    backend)   echo "$BACKEND_SERVICE_NAME" ;;
    nginx)     echo "$NGINX_SERVICE_NAME" ;;
    ollama)    echo "$OLLAMA_SERVICE_NAME" ;;
    qdrant)    echo "$QDRANT_SERVICE_NAME" ;;
    scheduler) echo "$SCHEDULER_SERVICE_NAME" ;;
    worker)    echo "$WORKER_SERVICE_NAME" ;;
    *)         echo "" ;;
  esac
}

module_is_runtime() {
  case "$1" in
    frontend) return 1 ;;
    *)        return 0 ;;
  esac
}

module_is_managed() {
  case "$1" in
    backend)
      [[ "${MANAGE_BACKEND}" == "true" ]]
      ;;
    nginx)
      [[ "${MANAGE_NGINX}" == "true" ]]
      ;;
    ollama)
      [[ "${MANAGE_OLLAMA}" == "true" ]]
      ;;
    qdrant)
      [[ "${MANAGE_QDRANT}" == "true" ]]
      ;;
    scheduler)
      [[ -n "${SCHEDULER_SERVICE_NAME:-}" ]]
      ;;
    worker)
      [[ -n "${WORKER_SERVICE_NAME:-}" ]]
      ;;
    *)
      return 1
      ;;
  esac
}

module_unit_exists() {
  local svc="$1"
  [[ -n "$svc" ]] || return 1
  run_root systemctl cat "${svc}.service" &>/dev/null
}

module_get_state() {
  local mod="$1"
  local svc state

  if [[ "$mod" == "frontend" ]]; then
    if [[ -f "$FRONTEND_BUILD_DIR/index.html" ]]; then
      echo "artifact"
    else
      echo "missing"
    fi
    return 0
  fi

  if ! module_is_managed "$mod"; then
    echo "not_configured"
    return 0
  fi

  svc="$(module_service_name "$mod")"
  if [[ -z "$svc" ]]; then
    echo "not_configured"
    return 0
  fi

  if ! module_unit_exists "$svc"; then
    echo "not_installed"
    return 0
  fi

  if run_root systemctl is-active --quiet "$svc" 2>/dev/null; then
    echo "running"
  elif run_root systemctl is-failed --quiet "$svc" 2>/dev/null; then
    echo "failed"
  else
    echo "stopped"
  fi
}

_state_color() {
  case "$1" in
    running)  _color "0;32" "$2" ;;
    artifact) _color "0;32" "$2" ;;
    stopped)  _color "0;90" "$2" ;;
    failed)   _color "0;31" "$2" ;;
    not_configured|not_installed|missing|unknown)
      _color "0;33" "$2"
      ;;
    *)        printf "%s\n" "$2" ;;
  esac
}

module_state_label() {
  case "$1" in
    running)        echo "running" ;;
    stopped)        echo "stopped" ;;
    failed)         echo "failed" ;;
    artifact)       echo "build OK" ;;
    missing)        echo "build missing" ;;
    not_configured) echo "not configured" ;;
    not_installed)  echo "unit missing" ;;
    *)              echo "$1" ;;
  esac
}

print_status_table() {
  local mod state detail svc
  log_section "Module status"
  printf "  %-14s %-16s %s\n" "MODULE" "STATE" "DETAIL"
  printf "  %-14s %-16s %s\n" "------" "-----" "------"

  for mod in qdrant ollama backend nginx frontend scheduler worker; do
    state="$(module_get_state "$mod")"
    detail=""

    case "$mod" in
      frontend)
        detail="$FRONTEND_BUILD_DIR"
        ;;
      scheduler|worker)
        if [[ "$state" == "not_configured" ]]; then
          detail="(set SERVICE_NAME in deploy.local.conf)"
        else
          svc="$(module_service_name "$mod")"
          detail="$svc"
        fi
        ;;
      *)
        if module_is_managed "$mod"; then
          svc="$(module_service_name "$mod")"
          detail="$svc"
        else
          detail="management disabled"
          state="not_configured"
        fi
        ;;
    esac

    _state_color "$state" "$(printf "  %-14s %-16s %s" "$mod" "$(module_state_label "$state")" "$detail")"
  done
  echo ""
}

probe_qdrant() {
  curl -sf --max-time 5 "http://${QDRANT_HOST}:${QDRANT_PORT}/" -o /dev/null 2>/dev/null
}

probe_ollama() {
  curl -sf --max-time 5 "http://127.0.0.1:11434/api/tags" -o /dev/null 2>/dev/null
}

print_health_summary() {
  local backend_ok=0 nginx_ok=0 ollama_ok=0 qdrant_ok=0

  log_section "Health probes"

  local health_json="$LOG_DIR/last-health.json"
  if wait_for_backend_http "$health_json" 5 1; then
    log_ok "Backend API: OK ($HEALTHCHECK_URL)"
    backend_ok=1
    if command -v python3 &>/dev/null && [[ -f "$health_json" ]]; then
      local ollama_st qdrant_st
      ollama_st="$(HEALTH_JSON="$health_json" python3 -c "import json,os; d=json.load(open(os.environ['HEALTH_JSON'])); print(d.get('ollama',{}).get('status','?'))" 2>/dev/null || echo "?")"
      qdrant_st="$(HEALTH_JSON="$health_json" python3 -c "import json,os; d=json.load(open(os.environ['HEALTH_JSON'])); print(d.get('qdrant',{}).get('status','?'))" 2>/dev/null || echo "?")"
      [[ "$ollama_st" == "ok" ]] && log_ok "Ollama (via API): OK" || log_warn "Ollama (via API): $ollama_st"
      [[ "$qdrant_st" == "ok" ]] && log_ok "Qdrant (via API): OK" || log_warn "Qdrant (via API): $qdrant_st"
    fi
  else
    log_error "Backend API: FAILED"
    log_info "  sudo journalctl -u $BACKEND_SERVICE_NAME -n 50 --no-pager"
  fi

  if [[ "${MANAGE_NGINX}" == "true" ]] && run_root systemctl is-active --quiet "$NGINX_SERVICE_NAME" 2>/dev/null; then
    log_ok "Nginx service: OK"
    nginx_ok=1
  else
    log_warn "Nginx service: not active"
  fi

  if [[ "${MANAGE_OLLAMA}" == "true" ]]; then
    if probe_ollama; then
      log_ok "Ollama HTTP: OK"
      ollama_ok=1
    else
      log_warn "Ollama HTTP: unreachable (sudo systemctl start $OLLAMA_SERVICE_NAME)"
    fi
  fi

  if [[ "${MANAGE_QDRANT}" == "true" ]]; then
    if probe_qdrant; then
      log_ok "Qdrant HTTP: OK"
      qdrant_ok=1
    else
      log_warn "Qdrant HTTP: unreachable (sudo systemctl start $QDRANT_SERVICE_NAME)"
    fi
  fi

  if [[ -f "$FRONTEND_BUILD_DIR/index.html" ]]; then
    log_ok "Frontend build: present"
  else
    log_warn "Frontend build: missing ($FRONTEND_BUILD_DIR)"
  fi

  echo ""
  if [[ "$backend_ok" -eq 1 ]]; then
    log_ok "Health summary: backend reachable"
  else
    log_error "Health summary: backend not reachable"
  fi
  [[ "$backend_ok" -eq 1 ]]
}

op_start_module() {
  local mod="$1"
  local svc

  if [[ "$mod" == "frontend" ]]; then
    log_warn "Frontend is a static build — use deploy/build actions, not start"
    return 1
  fi

  if ! module_is_managed "$mod"; then
    log_warn "Module '$mod' is not configured for management — skipping"
    return 0
  fi

  svc="$(module_service_name "$mod")"
  if [[ -z "$svc" ]]; then
    log_warn "Module '$mod' has no service name — skipping"
    return 0
  fi

  log_info "Starting $mod ($svc)..."
  case "$mod" in
    backend)
      start_backend
      ;;
    nginx)
      if run_root systemctl start "$svc"; then
        log_ok "$mod started"
      else
        log_error "Failed to start $mod"
        return 1
      fi
      ;;
    *)
      if ! module_unit_exists "$svc"; then
        log_warn "systemd unit ${svc}.service not found — skipping $mod"
        return 0
      fi
      if run_root systemctl start "$svc"; then
        log_ok "$mod started"
      else
        log_error "Failed to start $mod"
        run_root journalctl -u "$svc" -n 15 --no-pager 2>/dev/null | tail -15 || true
        return 1
      fi
      ;;
  esac
}

op_stop_module() {
  local mod="$1"
  local svc

  if [[ "$mod" == "frontend" ]]; then
    log_warn "Frontend is a static build — stop does not apply"
    return 1
  fi

  if ! module_is_managed "$mod"; then
    log_warn "Module '$mod' is not configured — skipping"
    return 0
  fi

  svc="$(module_service_name "$mod")"
  if [[ -z "$svc" ]]; then
    log_warn "Module '$mod' has no service name — skipping"
    return 0
  fi

  log_info "Stopping $mod ($svc)..."
  case "$mod" in
    backend)
      stop_backend
      ;;
    *)
      if ! module_unit_exists "$svc"; then
        log_warn "systemd unit ${svc}.service not found — skipping $mod"
        return 0
      fi
      if run_root systemctl stop "$svc" 2>/dev/null; then
        log_ok "$mod stopped"
      else
        log_warn "$mod was not running or stop failed"
      fi
      ;;
  esac
}

op_restart_module() {
  local mod="$1"
  local svc

  if [[ "$mod" == "frontend" ]]; then
    log_warn "Frontend is a static build — use rebuild/reload nginx instead"
    return 1
  fi

  if ! module_is_managed "$mod"; then
    log_warn "Module '$mod' is not configured — skipping"
    return 0
  fi

  svc="$(module_service_name "$mod")"
  if [[ -z "$svc" ]]; then
    log_warn "Module '$mod' has no service name — skipping"
    return 0
  fi

  log_info "Restarting $mod ($svc)..."
  case "$mod" in
    backend)
      restart_backend
      ;;
    nginx)
      if run_root nginx -t 2>/dev/null && run_root systemctl restart "$svc"; then
        log_ok "$mod restarted"
      else
        log_error "Failed to restart $mod"
        return 1
      fi
      ;;
    *)
      if ! module_unit_exists "$svc"; then
        log_warn "systemd unit ${svc}.service not found — skipping $mod"
        return 0
      fi
      if run_root systemctl restart "$svc"; then
        log_ok "$mod restarted"
      else
        log_error "Failed to restart $mod"
        run_root journalctl -u "$svc" -n 15 --no-pager 2>/dev/null | tail -15 || true
        return 1
      fi
      ;;
  esac
}

_start_order() {
  local mods=(qdrant ollama backend)
  [[ -n "${WORKER_SERVICE_NAME:-}" ]] && mods+=(worker)
  [[ -n "${SCHEDULER_SERVICE_NAME:-}" ]] && mods+=(scheduler)
  mods+=(nginx)
  echo "${mods[@]}"
}

_stop_order() {
  local mods=(nginx backend)
  [[ -n "${WORKER_SERVICE_NAME:-}" ]] && mods+=(worker)
  [[ -n "${SCHEDULER_SERVICE_NAME:-}" ]] && mods+=(scheduler)
  mods+=(ollama qdrant)
  echo "${mods[@]}"
}

op_start_all() {
  local mod failed=0
  log_section "Start all modules"
  for mod in $(_start_order); do
    op_start_module "$mod" || failed=1
  done
  if [[ -f "$FRONTEND_BUILD_DIR/index.html" ]]; then
    log_ok "Frontend build present at $FRONTEND_BUILD_DIR"
  else
    log_warn "Frontend build missing — run frontend deploy or rebuild"
  fi
  echo ""
  print_health_summary || failed=1
  [[ "$failed" -eq 0 ]]
}

op_stop_all() {
  local mod
  log_section "Stop all modules"
  for mod in $(_stop_order); do
    op_stop_module "$mod" || true
  done
  log_ok "Stop-all complete"
}

op_restart_all() {
  local mod failed=0
  log_section "Restart all modules"
  for mod in $(_start_order); do
    op_restart_module "$mod" || failed=1
  done
  echo ""
  print_health_summary || failed=1
  [[ "$failed" -eq 0 ]]
}

pick_runtime_module() {
  local choice
  echo ""
  echo "  Select module:"
  echo "    1) backend"
  echo "    2) nginx"
  echo "    3) ollama"
  echo "    4) qdrant"
  if [[ -n "${SCHEDULER_SERVICE_NAME:-}" ]]; then
    echo "    5) scheduler"
  fi
  if [[ -n "${WORKER_SERVICE_NAME:-}" ]]; then
    echo "    6) worker"
  fi
  echo "    0) cancel"
  echo ""
  read -r -p "Enter choice: " choice
  case "$choice" in
    1) echo "backend" ;;
    2) echo "nginx" ;;
    3) echo "ollama" ;;
    4) echo "qdrant" ;;
    5) [[ -n "${SCHEDULER_SERVICE_NAME:-}" ]] && echo "scheduler" || { log_warn "Invalid"; return 1; } ;;
    6) [[ -n "${WORKER_SERVICE_NAME:-}" ]] && echo "worker" || { log_warn "Invalid"; return 1; } ;;
    0|"") return 1 ;;
    *) log_warn "Invalid choice"; return 1 ;;
  esac
}

show_module_logs() {
  local mod="${1:-}"
  local svc

  if [[ -z "$mod" ]]; then
    mod="$(pick_runtime_module)" || return 0
  fi

  if [[ "$mod" == "frontend" ]]; then
    log_warn "Frontend has no systemd logs — check nginx access/error logs"
    return 1
  fi

  svc="$(module_service_name "$mod")"
  if [[ -z "$svc" ]] || ! module_is_managed "$mod"; then
    log_warn "Module '$mod' is not configured"
    return 1
  fi

  log_section "Logs: $mod ($svc) — last 100 lines"
  run_root journalctl -u "$svc" -n 100 --no-pager 2>/dev/null || {
    log_error "Could not read logs for $svc"
    return 1
  }
}

interactive_restart_menu() {
  echo ""
  echo "  Restart:"
  echo "    1) All modules"
  echo "    2) Backend only"
  echo "    3) Nginx only"
  echo "    4) Ollama only"
  echo "    5) Qdrant only"
  echo "    0) Cancel"
  echo ""
  read -r -p "Enter choice [0-5]: " sub
  case "$sub" in
    1) op_restart_all ;;
    2) op_restart_module backend; print_health_summary ;;
    3) op_restart_module nginx ;;
    4) op_restart_module ollama; print_health_summary ;;
    5) op_restart_module qdrant; print_health_summary ;;
    0|"") log_info "Cancelled." ;;
    *) log_warn "Invalid choice" ;;
  esac
}

run_action() {
  local act="${1:-}"
  case "$act" in
    plan)        show_deploy_plan ;;
    start-all)   op_start_all ;;
    stop-all)    op_stop_all ;;
    restart-all) op_restart_all ;;
    start)
      [[ -n "${CLI_MODULE:-}" ]] || { log_error "Use --module <name> with --action start"; return 1; }
      op_start_module "$CLI_MODULE"
      ;;
    stop)
      [[ -n "${CLI_MODULE:-}" ]] || { log_error "Use --module <name> with --action stop"; return 1; }
      op_stop_module "$CLI_MODULE"
      ;;
    restart)
      [[ -n "${CLI_MODULE:-}" ]] || { log_error "Use --module <name> with --action restart"; return 1; }
      op_restart_module "$CLI_MODULE"
      print_health_summary
      ;;
    status)      service_status ;;
    clear-cache) mode_clear_caches ;;
    clear-retrieval-cache) maintenance clear-retrieval-cache ;;
    clear-answer-cache) maintenance clear-answer-cache ;;
    install-postgres)         install_postgres ;;
    setup-postgres-db)        setup_postgres_db ;;
    run-migrations)           run_migrations ;;
    migrate-sqlite-to-postgres) migrate_sqlite_to_postgres "${CLI_MODULE:-}" ;;
    backup-postgres)          backup_postgres ;;
    restore-postgres)         restore_postgres "${CLI_MODULE:-}" ;;
    check-postgres)           check_postgres ;;
    check-db)                 check_postgres ;;
    reset-postgres-db)        reset_postgres_db ;;
    vacuum-analyze)           vacuum_analyze_postgres ;;
    show-db-stats)            show_db_stats ;;
    configure-postgres)       configure_postgres ;;
    configure-ollama)         configure_ollama ;;
    logs)
      show_module_logs "${CLI_MODULE:-}"
      ;;
    *)
      log_error "Unknown action: $act"
      return 1
      ;;
  esac
}

usage() {
  cat <<EOF
AI Site Agent deployment & operations manager (systemd + nginx + PostgreSQL + Qdrant + Ollama)

Interactive over SSH (recommended):
  cd /opt/ai-site-agent && sudo bash deploy/manage_deploy.sh

Deploy (non-interactive):
  $0 --mode update     # deploy THIS checkout -> PROJECT_ROOT (sync+migrate+build+restart)
  $0 --mode plan|full|backend|frontend|clean|migrate|build-frontend|clear-caches|clear-retrieval-cache|clear-answer-cache|reindex

Operations (non-interactive):
  $0 --action plan
  $0 --action status
  $0 --action start-all|stop-all|restart-all
  $0 --action start|stop|restart --module backend|nginx|ollama|qdrant
  $0 --action logs [--module backend]
  $0 --action clear-cache|clear-retrieval-cache|clear-answer-cache

PostgreSQL (non-interactive):
  $0 --action install-postgres
  $0 --action setup-postgres-db
  $0 --action run-migrations
  $0 --action migrate-sqlite-to-postgres --module /path/to/ai_site_agent.db
  $0 --action backup-postgres
  $0 --action restore-postgres --module /path/to/backup.dump
  $0 --action check-postgres
  $0 --action reset-postgres-db

Maintenance / tuning (non-interactive):
  $0 --action vacuum-analyze
  $0 --action show-db-stats
  $0 --action configure-postgres
  $0 --action configure-ollama

Legacy shortcuts (--mode still supported):
  $0 --mode restart    # same as --action restart-all
  $0 --mode status     # same as --action status

Common flags:
  --yes              Skip destructive confirmations
  --no-git-pull      Deploy current files only (no git pull)
  --backup-db        Force PostgreSQL backup (pg_dump) before deploy
  --use-staging      Sync from \$STAGING_DIR (see deploy/prepare_staging.sh)
  --sync-from-dev    Copy code from SYNC_SOURCE (DEV_CHECKOUT or this script's checkout) → PROJECT_ROOT
  --no-sync-from-dev Do not rsync into PROJECT_ROOT

Config: deploy/deploy.conf, deploy/deploy.local.conf
Logs:   $LOG_DIR/deploy-*.log
Backups: $BACKUP_DIR/
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mode) MODE="$2"; INTERACTIVE=0; shift 2 ;;
      --action) ACTION="$2"; INTERACTIVE=0; shift 2 ;;
      --module) CLI_MODULE="$2"; shift 2 ;;
      --yes) ASSUME_YES=1; shift ;;
      --no-git-pull) DO_GIT_PULL=no; shift ;;
      --git-pull) DO_GIT_PULL=yes; shift ;;
      --backup-db) DO_BACKUP_DB=yes; shift ;;
      --no-backup-db)
        if [[ "${MD_RELEASE_DEPLOY:-0}" == "1" ]]; then
          log_error "--no-backup-db is forbidden on release deploy (backup is mandatory)"
          exit 1
        fi
        DO_BACKUP_DB=no
        shift
        ;;
      --clear-db) CLEAR_DB=1; shift ;;
      --clear-qdrant) CLEAR_QDRANT=1; shift ;;
      --clear-caches) CLEAR_CACHES=1; shift ;;
      --clear-frontend) CLEAR_FRONTEND_BUILD=1; shift ;;
      --recreate-venv) RECREATE_VENV=1; shift ;;
      --no-npm-install) DO_NPM_INSTALL=no; shift ;;
      --no-reload-nginx) DO_RELOAD_NGINX=no; shift ;;
      --use-staging)
        USE_STAGING_FLAG=yes
        if ! deploy_guard_emergency_enabled; then
          log_error "--use-staging is emergency-only (prepare_staging bypasses origin/main)."
          log_error "Use: manage_deploy.sh deploy full"
          exit 1
        fi
        deploy_guard_require_emergency "staging-tree deploy" || exit 1
        shift
        ;;
      --sync-from-dev) SYNC_FROM_DEV_FLAG=yes; shift ;;
      --no-sync-from-dev) SYNC_FROM_DEV_FLAG=no; shift ;;
      -h|--help)
        if [[ -f "$SCRIPT_DIR/lib/cli.sh" ]]; then
          # shellcheck source=deploy/lib/cli.sh
          source "$SCRIPT_DIR/lib/cli.sh"
          md_cli_usage
        else
          usage
        fi
        exit 0
        ;;
      *) log_error "Unknown option: $1"; usage; exit 1 ;;
    esac
  done
}

prompt_yn() {
  local question="$1"
  local default="${2:-n}"
  local reply hint="y/N"
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    [[ "$default" == "y" || "$default" == "Y" ]]
    return
  fi
  [[ "$default" == "y" || "$default" == "Y" ]] && hint="Y/n"
  read -r -p "$question [$hint] " reply
  reply="${reply:-$default}"
  [[ "$reply" =~ ^[Yy] ]]
}

confirm_destructive() {
  echo ""
  log_warn "WARNING: destructive action — you may lose indexed knowledge,"
  log_warn "cache data, and/or the application database."
  echo ""
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    return 0
  fi
  read -r -p "Type 'yes' to continue: " reply
  [[ "$reply" == "yes" ]]
}

print_plan() {
  log_section "Plan"
  echo "  1. Stop backend ($BACKEND_SERVICE_NAME)"
  echo "  2. Update code (git pull or staging)"
  echo "  3. Install Python deps + run DB schema upgrade"
  echo "  4. Build dashboard (npm) if needed"
  echo "  5. Restart backend + reload nginx"
  echo "  6. Health check: $HEALTHCHECK_URL"
  echo ""
}

show_deploy_plan() {
  resolve_sync_source
  log_section "Resolved deploy configuration"
  echo "  Script checkout: $REPO_ROOT"
  echo "  Sync source:     $SYNC_SOURCE"
  echo "  Deploy target:   $PROJECT_ROOT"
  echo "  DEV_CHECKOUT:    ${DEV_CHECKOUT:-"(unset)"}"
  echo "  Backend dir:     $BACKEND_DIR"
  echo "  Dashboard dir:   $DASHBOARD_DIR"
  echo "  Venv:            $VENV_DIR"
  echo "  Frontend build:  $FRONTEND_BUILD_DIR"
  echo "  Env file:        $ENV_FILE"
  echo "  Backups:         $BACKUP_DIR"
  echo "  Logs:            $LOG_DIR"
  echo "  Healthcheck:     $HEALTHCHECK_URL"
  echo "  Database:        PostgreSQL @ ${PG_HOST:-?}:${PG_PORT:-?}/${PG_DB:-?} (user ${PG_USER:-?})"
  if paths_differ; then
    echo "  Code update:     rsync $SYNC_SOURCE → $PROJECT_ROOT"
  elif [[ "${DO_GIT_PULL:-$GIT_PULL_DEFAULT}" == "yes" && -d "$PROJECT_ROOT/.git" ]]; then
    echo "  Code update:     git pull --ff-only"
  else
    echo "  Code update:     files already on disk (no sync)"
  fi
  echo ""
  print_plan
  log_info "Plan only — no files changed, no migrations run, no services restarted"
}

venv_python() {
  echo "$VENV_DIR/bin/python"
}

maintenance() {
  if [[ ! -x "$(venv_python)" ]]; then
    log_error "Venv missing at $VENV_DIR — run backend deploy first"
    return 1
  fi
  if [[ ! -f "$BACKEND_DIR/app/scripts/maintenance.py" ]]; then
    log_error "maintenance.py missing under $BACKEND_DIR/app/scripts/"
    log_info "Sync latest code to $PROJECT_ROOT (re-run deploy and choose sync, or --sync-from-dev)"
    return 1
  fi
  cd "$BACKEND_DIR"
  "$(venv_python)" -m app.scripts.maintenance "$@"
}

paths_differ() {
  local a b
  resolve_sync_source
  a="$(realpath "$SYNC_SOURCE" 2>/dev/null || echo "$SYNC_SOURCE")"
  b="$(realpath "$PROJECT_ROOT" 2>/dev/null || echo "$PROJECT_ROOT")"
  [[ "$a" != "$b" ]]
}

sync_from_dev_checkout() {
  resolve_sync_source
  if ! paths_differ; then
    log_info "Sync source and project path are the same ($PROJECT_ROOT) — skip rsync"
    return 0
  fi
  # Normal path: only the clean origin/main worktree created by `deploy full`.
  if [[ "${MD_RELEASE_DEPLOY:-0}" == "1" ]]; then
    if ! deploy_guard_assert_clean_worktree "$SYNC_SOURCE" "release worktree"; then
      log_error "Release worktree is dirty — abort"
      return 1
    fi
  else
    # Direct --sync-from-dev from an operator checkout is blocked.
    if [[ "${ALLOW_DIRTY_SYNC:-0}" == "1" ]] || [[ "${DEPLOY_LOCAL_MAIN:-0}" == "1" ]]; then
      deploy_guard_reject_legacy_bypasses || return 1
    fi
    if ! deploy_guard_emergency_enabled; then
      log_error "Refusing rsync from operator checkout: $SYNC_SOURCE"
      log_error "Use: sudo bash deploy/manage_deploy.sh deploy full"
      log_error "That builds a clean worktree from origin/main (never feature/dirty trees)."
      return 1
    fi
    deploy_guard_require_emergency "sync from non-release checkout" || return 1
    if ! deploy_guard_assert_clean_worktree "$SYNC_SOURCE" "emergency sync source"; then
      log_error "Even emergency sync refuses a dirty tree"
      return 1
    fi
  fi
  log_info "Rsync release source → production (keeps DB, venv, node_modules)..."
  log_info "  from: $SYNC_SOURCE"
  log_info "  to:   $PROJECT_ROOT"
  # Never overwrite production secrets/state with the dev checkout copy.
  # (.env cutover to recovery DB was wiped by a full redeploy without this.)
  if ! rsync -a --delete \
    --exclude '.venv' \
    --exclude 'node_modules' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude 'backend/ai_site_agent.db' \
    --exclude 'backend/ai_site_agent.db-*' \
    --exclude 'logs/' \
    --exclude 'backups/' \
    --exclude '*.dump' \
    --exclude '*.sql.gz' \
    --exclude '.git' \
    --exclude 'dashboard/dist/' \
    "$SYNC_SOURCE/" "$PROJECT_ROOT/"; then
    log_error "rsync failed (often permissions on $PROJECT_ROOT)"
    log_info "Repair: sudo chown -R \"\$USER:\$USER\" $PROJECT_ROOT"
    return 1
  fi
  log_ok "Code synced to $PROJECT_ROOT"
}

resolve_sync_from_dev() {
  resolve_sync_source
  if ! paths_differ; then
    # Running inside /opt without a usable DEV_CHECKOUT — cannot invent a source.
    if [[ -z "${DEV_CHECKOUT:-}" ]]; then
      log_warn "No code sync: set DEV_CHECKOUT in deploy.local.conf to your projects checkout"
    fi
    return 0
  fi
  if [[ -n "${SYNC_FROM_DEV:-}" ]]; then
    return 0
  fi
  if [[ "${SYNC_FROM_DEV_FLAG:-}" == "yes" ]]; then
    SYNC_FROM_DEV=yes
  elif [[ "${SYNC_FROM_DEV_FLAG:-}" == "no" ]]; then
    SYNC_FROM_DEV=no
  elif [[ "$INTERACTIVE" -eq 1 ]]; then
    echo ""
    log_warn "Deploy target ($PROJECT_ROOT) differs from sync source ($SYNC_SOURCE)"
    log_warn "Dashboard / UI updates will NOT appear unless you sync."
    prompt_yn "Sync code from $SYNC_SOURCE → $PROJECT_ROOT?" "y" && SYNC_FROM_DEV=yes || SYNC_FROM_DEV=no
  else
    # Non-interactive deploy to a different path (typical dev → /opt): sync by default.
    SYNC_FROM_DEV=yes
  fi
}

require_dev_sync_for_ui() {
  resolve_sync_source
  if ! paths_differ; then
    return 0
  fi
  resolve_sync_from_dev
  if [[ "${SYNC_FROM_DEV:-}" == "yes" ]]; then
    return 0
  fi
  log_error "Cannot build dashboard UI — code was not synced to $PROJECT_ROOT"
  log_error "Your changes are in $SYNC_SOURCE but nginx serves $FRONTEND_BUILD_DIR"
  log_error "Fix: re-run deploy and answer Yes to sync, or run:"
  log_error "  sudo bash deploy/manage_deploy.sh --mode frontend --sync-from-dev --yes"
  log_error "Or set DEV_CHECKOUT in deploy.local.conf when running from /opt."
  return 1
}

# ---------------------------------------------------------------------------
# PostgreSQL management
# ---------------------------------------------------------------------------
require_database_url() {
  if [[ -z "${DATABASE_URL:-}" ]]; then
    log_error "DATABASE_URL is not set in $ENV_FILE"
    log_info  "Example: DATABASE_URL=postgresql+psycopg://ai_agent:change_me@localhost:5432/ai_site_agent"
    return 1
  fi
  if [[ "$DATABASE_URL" != postgresql* ]]; then
    log_error "DATABASE_URL must be a PostgreSQL URL (got: ${DATABASE_URL%%://*}://...)"
    return 1
  fi
  parse_database_url
}

install_postgres() {
  log_section "Install PostgreSQL"
  if command -v psql &>/dev/null; then
    log_ok "PostgreSQL client already installed ($(psql --version 2>/dev/null))"
  fi
  run_root apt update || return 1
  run_root apt install -y postgresql postgresql-contrib || return 1
  run_root systemctl enable postgresql || true
  run_root systemctl start postgresql || true
  log_ok "PostgreSQL installed and started"
}

setup_postgres_db() {
  log_section "Create PostgreSQL role + database"
  require_database_url || return 1
  local pw="${PG_PASSWORD:-change_me}"
  log_info "Ensuring role '$PG_USER' and database '$PG_DB' exist..."
  psql_super -d postgres -c \
    "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='${PG_USER}') THEN CREATE ROLE \"${PG_USER}\" LOGIN PASSWORD '${pw}'; END IF; END \$\$;" \
    || return 1
  if ! psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='${PG_DB}'" | grep -q 1; then
    psql_super -d postgres -c "CREATE DATABASE \"${PG_DB}\" OWNER \"${PG_USER}\";" || return 1
  fi
  psql_super -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE \"${PG_DB}\" TO \"${PG_USER}\";" || true
  log_ok "Role and database ready ($PG_USER@$PG_HOST:$PG_PORT/$PG_DB)"
}

check_postgres() {
  log_section "PostgreSQL check"
  require_database_url || return 1
  if pg_env pg_isready &>/dev/null; then
    log_ok "pg_isready: accepting connections ($PG_HOST:$PG_PORT)"
  else
    log_warn "pg_isready: not reachable at $PG_HOST:$PG_PORT"
  fi
  if pg_env psql -d "$PG_DB" -tAc "SELECT 1" &>/dev/null; then
    log_ok "Connected to database '$PG_DB' as '$PG_USER'"
    local rev
    rev="$(pg_env psql -d "$PG_DB" -tAc "SELECT version_num FROM alembic_version" 2>/dev/null | tr -d '[:space:]')"
    log_info "Alembic revision: ${rev:-<not migrated>}"
  else
    log_error "Could not connect to '$PG_DB' as '$PG_USER' — check credentials/permissions"
    return 1
  fi
}

backup_postgres() {
  require_database_url || return 1
  mkdir -p "$BACKUP_DIR"
  local dest="$BACKUP_DIR/${PG_DB}.$(date +%Y%m%d_%H%M%S).dump"
  log_info "pg_dump → $dest"
  if pg_env pg_dump -d "$PG_DB" -Fc -f "$dest"; then
    log_ok "Database backed up to $dest"
  else
    log_error "pg_dump failed"
    return 1
  fi
}

restore_postgres() {
  require_database_url || return 1
  local src="${1:-}"
  if [[ -z "$src" || ! -f "$src" ]]; then
    log_error "Usage: --action restore-postgres --module <path-to-dump>"
    return 1
  fi
  log_warn "Restoring $src into '$PG_DB' (existing objects will be replaced)"
  confirm_destructive || { log_info "Cancelled."; return 0; }
  if pg_env pg_restore -d "$PG_DB" --clean --if-exists "$src"; then
    log_ok "Database restored from $src"
  else
    log_error "pg_restore reported errors (review output)"
    return 1
  fi
}

reset_postgres_db() {
  require_database_url || return 1
  log_warn "This DROPS and recreates database '$PG_DB' — all data is lost."
  confirm_destructive || { log_info "Cancelled."; return 0; }
  psql_super -d postgres -c "DROP DATABASE IF EXISTS \"${PG_DB}\";" || return 1
  psql_super -d postgres -c "CREATE DATABASE \"${PG_DB}\" OWNER \"${PG_USER}\";" || return 1
  run_migrations
}

migrate_sqlite_to_postgres() {
  require_database_url || return 1
  local sqlite_path="${1:-$BACKEND_DIR/ai_site_agent.db}"
  if [[ ! -f "$sqlite_path" ]]; then
    log_error "SQLite file not found: $sqlite_path"
    log_info  "Pass the path: --action migrate-sqlite-to-postgres --module /path/to/ai_site_agent.db"
    return 1
  fi
  if [[ ! -x "$(venv_python)" ]]; then
    log_error "Venv missing at $VENV_DIR — run backend deploy first"
    return 1
  fi
  log_info "Ensuring target schema is migrated..."
  run_migrations || return 1
  log_info "Copying data from $sqlite_path → PostgreSQL..."
  cd "$BACKEND_DIR"
  "$(venv_python)" scripts/migrate_sqlite_to_postgres.py \
    --sqlite-path "$sqlite_path" --postgres-url "$DATABASE_URL"
}

vacuum_analyze_postgres() {
  log_section "VACUUM ANALYZE"
  require_database_url || return 1
  log_info "Running VACUUM ANALYZE on application tables in '$PG_DB'..."
  if pg_env psql -d "$PG_DB" -v ON_ERROR_STOP=1 -Atc \
    "SELECT format('VACUUM (ANALYZE) %I.%I;', schemaname, relname)
     FROM pg_stat_user_tables
     ORDER BY schemaname, relname;" \
    | pg_env psql -d "$PG_DB" -v ON_ERROR_STOP=1; then
    log_ok "VACUUM ANALYZE complete"
  else
    log_error "VACUUM ANALYZE failed"
    return 1
  fi
}

show_db_stats() {
  log_section "PostgreSQL statistics"
  require_database_url || return 1
  pg_env psql -d "$PG_DB" -c "
    SELECT relname AS table, n_live_tup AS rows, n_dead_tup AS dead, last_vacuum, last_autovacuum
    FROM pg_stat_user_tables
    ORDER BY n_live_tup DESC
    LIMIT 20;
  " || return 1
  pg_env psql -d "$PG_DB" -c "
    SELECT numbackends AS connections, xact_commit, xact_rollback, blks_read, blks_hit
    FROM pg_stat_database WHERE datname = current_database();
  " || true
}

configure_postgres() {
  log_section "PostgreSQL tuning recommendations"
  cat <<'EOF'
Recommended settings for a small VPS / WSL (edit postgresql.conf, then restart PostgreSQL):

  shared_buffers = 512MB
  effective_cache_size = 2GB
  work_mem = 16MB
  maintenance_work_mem = 256MB
  wal_buffers = 16MB
  checkpoint_timeout = 10min
  max_connections = 100

Optional monitoring extension (as superuser):
  CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

Application pool (.env): DB_POOL_SIZE=10 DB_MAX_OVERFLOW=20 (use 5/10 on small dev hosts).

Routine maintenance:
  ./deploy/manage_deploy.sh --action vacuum-analyze
  ./deploy/manage_deploy.sh --action show-db-stats
EOF
}

configure_ollama() {
  log_section "Ollama tuning recommendations"
  cat <<'EOF'
Keep chat responsive while indexing / Source Intelligence run in the background.
These are set on the OLLAMA SERVER process, not in the app's .env.

Edit the Ollama service unit:
  sudo systemctl edit ollama

Add under [Service]:
  Environment="OLLAMA_NUM_PARALLEL=2"
  Environment="OLLAMA_MAX_LOADED_MODELS=2"
  Environment="OLLAMA_KEEP_ALIVE=30m"

Apply:
  sudo systemctl daemon-reload && sudo systemctl restart ollama

Notes:
  - OLLAMA_MAX_LOADED_MODELS=2 keeps the LLM + embedding model resident together,
    avoiding slow model swaps when chat and indexing interleave.
  - In the dashboard: Settings -> Limits -> "Max concurrent background embedding
    requests" controls how many indexing embeddings run in parallel (keep 1-2).
EOF
}

stop_backend() {
  log_info "Stopping backend ($BACKEND_SERVICE_NAME)..."
  if run_root systemctl is-active --quiet "$BACKEND_SERVICE_NAME" 2>/dev/null; then
    run_root systemctl stop "$BACKEND_SERVICE_NAME"
    log_ok "Backend stopped"
  else
    log_warn "Backend not running via systemd"
    pkill -f "uvicorn app.main" 2>/dev/null || true
  fi
}

# Probe backend HTTP readiness (retries). Writes body to $1 when provided.
wait_for_backend_http() {
  local out_file="${1:-}"
  local attempts="${2:-30}"
  local delay_s="${3:-1}"
  local url="${HEALTHCHECK_URL:-http://127.0.0.1:8000/api/health}"
  local i=0 rc=0 err="" dest
  dest="$(mktemp "${LOG_DIR:-/tmp}/health-XXXXXX.json" 2>/dev/null || mktemp /tmp/health-XXXXXX.json)"
  while (( i < attempts )); do
    i=$((i + 1))
    err="$(curl -sS --fail --max-time 5 --noproxy '*' "$url" -o "$dest" 2>&1)" && rc=0 || rc=$?
    if [[ "$rc" -eq 0 ]]; then
      if [[ -n "$out_file" ]]; then
        mv -f "$dest" "$out_file" 2>/dev/null || cp -f "$dest" "$out_file"
      fi
      rm -f "$dest" 2>/dev/null || true
      return 0
    fi
    sleep "$delay_s"
  done
  rm -f "$dest" 2>/dev/null || true
  if [[ -n "$err" ]]; then
    log_info "Last curl error (exit $rc): $err"
  else
    log_info "curl exit $rc after ${attempts} attempts → $url"
  fi
  return "$rc"
}

start_backend() {
  log_info "Starting backend ($BACKEND_SERVICE_NAME)..."
  ensure_service_cwd
  install_systemd_unit
  run_root systemctl enable "$BACKEND_SERVICE_NAME" 2>/dev/null || true
  if ! run_root systemctl start "$BACKEND_SERVICE_NAME"; then
    log_error "Failed to start backend"
    run_root systemctl status "$BACKEND_SERVICE_NAME" --no-pager 2>/dev/null | tail -15 || true
    log_info "Try: sudo journalctl -u $BACKEND_SERVICE_NAME -n 50 --no-pager"
    return 1
  fi
  sleep 2
  if run_root systemctl is-active --quiet "$BACKEND_SERVICE_NAME"; then
    log_ok "Backend is active"
  else
    log_error "Backend did not stay active"
    run_root systemctl status "$BACKEND_SERVICE_NAME" --no-pager 2>/dev/null | tail -20 || true
    log_info "Recent logs:"
    run_root journalctl -u "$BACKEND_SERVICE_NAME" -n 25 --no-pager 2>/dev/null | tail -25 || true
    log_info "Try: sudo journalctl -u $BACKEND_SERVICE_NAME -n 50 --no-pager"
    return 1
  fi
  # systemd "active" is not the same as accepting HTTP — wait briefly for uvicorn.
  if wait_for_backend_http "" 15 1; then
    log_ok "Backend HTTP ready ($HEALTHCHECK_URL)"
  else
    log_warn "Backend active but HTTP not ready yet — later health check will retry"
  fi
}

restart_backend() {
  stop_backend || true
  start_backend
}

install_systemd_unit() {
  local unit_src="$PROJECT_ROOT/deploy/systemd/ai-agent-backend.service"
  local unit_dst="/etc/systemd/system/${BACKEND_SERVICE_NAME}.service"
  local tmp
  [[ -f "$unit_src" ]] || return 0
  tmp="$(mktemp)"
  # Keep unit User/Group aligned with APP_USER from deploy.local.conf (WSL uses home).
  sed -e "s/^User=.*/User=${APP_USER}/" -e "s/^Group=.*/Group=${APP_GROUP}/" \
    "$unit_src" >"$tmp"
  run_root install -m 644 "$tmp" "$unit_dst"
  rm -f "$tmp"
  run_root systemctl daemon-reload
}

venv_is_broken() {
  [[ ! -x "$VENV_DIR/bin/python" ]] && return 0
  if [[ -f "$VENV_DIR/pyvenv.cfg" ]] && grep -qE '(^command = .*/tmp/|/tmp/ai-site-agent)' "$VENV_DIR/pyvenv.cfg" 2>/dev/null; then
    return 0
  fi
  if [[ -f "$VENV_DIR/bin/pip" ]]; then
    local shebang
    shebang="$(head -1 "$VENV_DIR/bin/pip" 2>/dev/null || true)"
    if [[ "$shebang" == *"/tmp/"* ]]; then
      return 0
    fi
  fi
  if [[ -f "$BACKEND_DIR/requirements.txt" ]] && grep -q 'python-jose' "$BACKEND_DIR/requirements.txt" 2>/dev/null; then
    if ! "$VENV_DIR/bin/python" -c "import jose, passlib" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

ensure_venv() {
  cd "$BACKEND_DIR"
  if [[ "$RECREATE_VENV" -eq 1 && -d "$VENV_DIR" ]]; then
    log_warn "Recreating venv: $VENV_DIR"
    rm -rf "$VENV_DIR"
  fi
  if venv_is_broken; then
    log_warn "Broken or stale venv at $VENV_DIR (paths still point at /tmp?) — recreating..."
    rm -rf "$VENV_DIR"
  fi
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    log_info "Creating venv at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
  fi
  log_info "pip install -r requirements.txt ..."
  if ! "$VENV_DIR/bin/pip" install --upgrade pip; then
    log_error "pip upgrade failed"
    return 1
  fi
  if ! "$VENV_DIR/bin/pip" install -r requirements.txt; then
    log_error "pip install -r requirements.txt failed"
    return 1
  fi
  if grep -q 'python-jose' requirements.txt 2>/dev/null; then
    if ! "$VENV_DIR/bin/python" -c "import jose, passlib" 2>/dev/null; then
      log_error "Auth packages (python-jose, passlib) not importable after pip install"
      log_info "Try: RECREATE_VENV=1 sudo bash deploy/manage_deploy.sh --mode backend"
      return 1
    fi
  fi
  log_ok "Python dependencies ready"
}

run_migrations() {
  require_database_url || return 1
  log_info "Applying Alembic migrations (alembic upgrade head)..."
  if [[ ! -x "$(venv_python)" ]]; then
    log_error "Venv missing at $VENV_DIR — run backend deploy first"
    return 1
  fi
  cd "$BACKEND_DIR"
  if "$(venv_python)" -m app.scripts.maintenance migrate; then
    log_ok "Database schema is up to date"
    return 0
  fi
  # Fallback: run alembic directly from the backend dir with the venv binary.
  # This is the command operators often try by hand — here it always runs from
  # the right directory ($BACKEND_DIR with alembic.ini) using the project venv.
  log_warn "maintenance migrate failed — retrying with 'alembic upgrade head'"
  if [[ -x "$VENV_DIR/bin/alembic" && -f "$BACKEND_DIR/alembic.ini" ]]; then
    if "$VENV_DIR/bin/alembic" upgrade head; then
      log_ok "Database schema is up to date (direct alembic)"
      return 0
    fi
  else
    log_error "alembic binary or alembic.ini missing under $BACKEND_DIR"
  fi
  log_error "Database migration failed — backend will refuse to start until fixed"
  log_info  "Inspect: cd $BACKEND_DIR && $VENV_DIR/bin/alembic current && $VENV_DIR/bin/alembic history"
  return 1
}

update_source_code() {
  if [[ "${USE_STAGING_FLAG:-$USE_STAGING}" == "yes" ]]; then
    if [[ ! -d "$STAGING_DIR/backend" ]]; then
      log_error "Staging missing: $STAGING_DIR"
      log_info "On dev machine run: bash deploy/prepare_staging.sh"
      log_info "Then copy to server and run with --use-staging"
      return 1
    fi
    log_info "Rsync staging → $PROJECT_ROOT (keeps DB + venv)"
    # Never overwrite production secrets/state (same rules as dev-checkout sync).
    rsync -a --delete \
      --exclude '.env' \
      --exclude '.env.*' \
      --exclude 'backend/ai_site_agent.db' \
      --exclude 'backend/ai_site_agent.db-*' \
      --exclude 'backend/.venv' \
      --exclude 'logs/' \
      --exclude 'backups/' \
      --exclude '*.dump' \
      --exclude '*.sql.gz' \
      "$STAGING_DIR/" "$PROJECT_ROOT/"
    log_ok "Staging sync done"
    return 0
  fi

  resolve_sync_from_dev
  if [[ "${SYNC_FROM_DEV:-}" == "yes" ]]; then
    sync_from_dev_checkout || return 1
    return 0
  fi

  if paths_differ; then
    log_warn "Deploy target ($PROJECT_ROOT) differs from sync source ($SYNC_SOURCE)"
    log_warn "Without sync, new files in $SYNC_SOURCE will NOT reach $PROJECT_ROOT"
    log_info "Re-run and choose sync, or pass --sync-from-dev"
  fi

  local pull="${DO_GIT_PULL:-$GIT_PULL_DEFAULT}"
  if [[ "$pull" != "yes" ]]; then
    log_info "Skipping git pull (deploying files already on disk)"
    return 0
  fi
  if [[ -d "$PROJECT_ROOT/.git" ]]; then
    log_info "git pull in $PROJECT_ROOT ..."
    (cd "$PROJECT_ROOT" && git pull --ff-only) || {
      log_error "git pull failed"
      return 1
    }
    log_ok "Code updated from git"
  else
    log_warn "Not a git repo — using files as-is ($PROJECT_ROOT)"
  fi
}

fix_ownership() {
  if ! id "$APP_USER" &>/dev/null; then
    return 0
  fi
  # Never lock out the human who is running the deploy (common WSL footgun when
  # APP_USER=www-data but the interactive shell is a normal user).
  local invoke="${SUDO_USER:-${USER:-}}"
  if [[ "$(id -u)" -ne 0 && -n "$invoke" && "$invoke" != "root" && "$invoke" != "$APP_USER" ]]; then
    log_warn "Skipping chown to ${APP_USER}:${APP_GROUP} (deploy user is ${invoke}; would break backup/rsync/npm)."
    log_info "Set APP_USER=${invoke} in deploy/deploy.local.conf for local WSL deploys."
    return 0
  fi
  run_root chown -R "$APP_USER:$APP_GROUP" "$PROJECT_ROOT" 2>/dev/null || \
    log_warn "Could not chown to $APP_USER (may need sudo)"
  # Avoid 700/nobody trees that break systemd User=APP_USER (status=200/CHDIR).
  run_root chmod u+rwx,g+rx,o+rx "$PROJECT_ROOT" 2>/dev/null || true
  if [[ -d "$PROJECT_ROOT/backend" ]]; then
    run_root chmod u+rwx,g+rx,o+rx "$PROJECT_ROOT/backend" 2>/dev/null || true
  fi
  run_root chmod 600 "$PROJECT_ROOT/.env" 2>/dev/null || true
}

# Lightweight: ensure systemd WorkingDirectory is traversable by APP_USER.
# Must run before systemctl start even when SKIP_FIX_OWNERSHIP=yes (mode_full
# defers full recursive chown until after npm).
ensure_service_cwd() {
  if ! id "$APP_USER" &>/dev/null; then
    return 0
  fi
  local wd="${PROJECT_ROOT}/backend"
  [[ -d "$PROJECT_ROOT" ]] || return 0
  run_root chown "$APP_USER:$APP_GROUP" "$PROJECT_ROOT" 2>/dev/null || true
  run_root chmod u+rwx,g+rx,o+rx "$PROJECT_ROOT" 2>/dev/null || true
  if [[ -d "$wd" ]]; then
    run_root chown -R "$APP_USER:$APP_GROUP" "$wd" 2>/dev/null || \
      run_root chown "$APP_USER:$APP_GROUP" "$wd" 2>/dev/null || true
    run_root chmod u+rwx,g+rx,o+rx "$wd" 2>/dev/null || true
  fi
  if ! run_root su -s /bin/sh "$APP_USER" -c "test -x '$PROJECT_ROOT' && test -x '$wd'" 2>/dev/null; then
    log_warn "APP_USER=${APP_USER} cannot traverse $wd — running full fix_ownership"
    fix_ownership
  fi
}

ensure_project_writable() {
  local probe="$BACKUP_DIR"
  mkdir -p "$probe" 2>/dev/null || true
  if [[ -w "$PROJECT_ROOT" && -w "$probe" ]]; then
    return 0
  fi
  local me
  me="$(id -un)"
  log_warn "$PROJECT_ROOT is not writable by ${me}; repairing ownership..."
  if run_root chown -R "${me}:$(id -gn)" "$PROJECT_ROOT"; then
    log_ok "Ownership repaired → ${me}"
    return 0
  fi
  log_error "Cannot write to $PROJECT_ROOT (needed for backup/rsync/npm)."
  log_info "Run once: sudo chown -R ${me}:${me} $PROJECT_ROOT"
  return 1
}

# Stamp dashboard/dist so verify-release / deploy stage 4 can match origin/main.
# Vite rebuild wipes this file unless rewritten after build.
write_frontend_deploy_identity() {
  local commit="${MD_DEPLOY_COMMIT:-}"
  local release short
  if [[ -z "$commit" && -f "$PROJECT_ROOT/.build-info.json" ]]; then
    commit="$(python3 -c "import json; print(json.load(open('$PROJECT_ROOT/.build-info.json')).get('git_commit',''))" 2>/dev/null || true)"
  fi
  [[ -n "$commit" ]] || return 0
  [[ -d "$FRONTEND_BUILD_DIR" ]] || return 0
  release="$(python3 -c "import json; print(json.load(open('$PROJECT_ROOT/.build-info.json')).get('release',''))" 2>/dev/null || true)"
  [[ -n "$release" ]] || release="${RELEASE_VERSION:-0.7}"
  short="${commit:0:7}"
  mkdir -p "$FRONTEND_BUILD_DIR"
  python3 - <<PY
import json
from pathlib import Path
payload = {
    "git_commit": "$commit",
    "git_commit_short": "$short",
    "release": "$release",
    "artifact": "dashboard/dist",
}
Path("$FRONTEND_BUILD_DIR/.deploy-identity.json").write_text(
    json.dumps(payload, indent=2) + "\n", encoding="utf-8"
)
print("OK: frontend identity → $FRONTEND_BUILD_DIR/.deploy-identity.json")
PY
}

build_frontend() {
  require_dev_sync_for_ui || return 1
  local npm_bin
  if ! npm_bin="$(npm_cmd)"; then
    log_error "npm not installed (needed for dashboard build)"
    log_info "Install Node.js 18+ system-wide, or set NPM_BIN in deploy/deploy.local.conf"
    return 1
  fi
  cd "$DASHBOARD_DIR"
  if [[ "$CLEAR_FRONTEND_BUILD" -eq 1 && -d "$FRONTEND_BUILD_DIR" ]]; then
    log_info "Removing old build: $FRONTEND_BUILD_DIR"
    rm -rf "$FRONTEND_BUILD_DIR"
  fi
  if [[ "${DO_NPM_INSTALL:-$NPM_INSTALL_DEFAULT}" == "yes" ]]; then
    log_info "npm install ..."
    "$npm_bin" install --silent
  fi
  log_info "npm run build ..."
  if ! "$npm_bin" run build; then
    log_error "Frontend build failed"
    return 1
  fi
  if [[ ! -f "$FRONTEND_BUILD_DIR/index.html" ]]; then
    log_error "Build output missing: $FRONTEND_BUILD_DIR/index.html"
    return 1
  fi
  write_frontend_deploy_identity
  log_ok "Frontend built → $FRONTEND_BUILD_DIR"
}

reload_nginx() {
  if [[ "${DO_RELOAD_NGINX:-$RELOAD_NGINX_DEFAULT}" != "yes" ]]; then
    log_info "Skipping nginx reload"
    return 0
  fi
  log_info "nginx -t ..."
  if run_root nginx -t; then
    run_root systemctl reload "$NGINX_SERVICE_NAME"
    log_ok "Nginx reloaded"
  else
    log_error "nginx config test failed — not reloading"
    return 1
  fi
}

health_checks() {
  log_section "Health checks"
  local backend_ok=0
  local health_json="$LOG_DIR/last-health.json"

  # Retry: uvicorn can lag systemd "active", and a single curl -o /tmp/... can
  # false-fail (permissions / race) even when the API already returned 200.
  if wait_for_backend_http "$health_json" 20 1; then
    log_ok "Backend: OK ($HEALTHCHECK_URL)"
    backend_ok=1
    if command -v python3 &>/dev/null && [[ -f "$health_json" ]]; then
      local ollama_st qdrant_st
      ollama_st="$(HEALTH_JSON="$health_json" python3 -c "import json,os; d=json.load(open(os.environ['HEALTH_JSON'])); print(d.get('ollama',{}).get('status','?'))" 2>/dev/null || echo "?")"
      qdrant_st="$(HEALTH_JSON="$health_json" python3 -c "import json,os; d=json.load(open(os.environ['HEALTH_JSON'])); print(d.get('qdrant',{}).get('status','?'))" 2>/dev/null || echo "?")"
      [[ "$ollama_st" == "ok" ]] && log_ok "Ollama: OK" || log_warn "Ollama: $ollama_st (sudo systemctl start $OLLAMA_SERVICE_NAME)"
      [[ "$qdrant_st" == "ok" ]] && log_ok "Qdrant: OK" || log_warn "Qdrant: $qdrant_st (sudo systemctl start $QDRANT_SERVICE_NAME)"
    fi
  else
    log_error "Backend: FAILED ($HEALTHCHECK_URL)"
    if run_root systemctl is-active --quiet "$BACKEND_SERVICE_NAME" 2>/dev/null; then
      log_warn "systemd says $BACKEND_SERVICE_NAME is active — HTTP probe still failing"
    fi
    log_info "  sudo systemctl status $BACKEND_SERVICE_NAME"
    log_info "  sudo journalctl -u $BACKEND_SERVICE_NAME -n 50 --no-pager"
  fi

  if [[ -f "$FRONTEND_BUILD_DIR/index.html" ]]; then
    log_ok "Frontend static files: OK"
  else
    log_warn "Frontend build not found at $FRONTEND_BUILD_DIR"
  fi

  echo ""
  if [[ "$backend_ok" -eq 1 ]]; then
    log_ok "Deploy health check passed"
  else
    log_error "Deploy health check failed — see messages above"
  fi
  [[ "$backend_ok" -eq 1 ]]
}

service_status() {
  print_status_table
  print_health_summary || true
  echo ""
  maintenance status 2>/dev/null || log_warn "Maintenance status unavailable (is venv ready?)"
}

run_cleanup_tasks() {
  if [[ "$CLEAR_DB" -eq 1 || "$CLEAR_CACHES" -eq 1 || "$CLEAR_QDRANT" -eq 1 ]]; then
    stop_backend || true
  fi

  if [[ "${DO_BACKUP_DB:-$BACKUP_DB_DEFAULT}" == "yes" && "$CLEAR_DB" -eq 1 ]]; then
    backup_postgres
  fi

  if [[ "$CLEAR_CACHES" -eq 1 ]]; then
    log_info "Clearing retrieval + answer caches (sources/index kept)..."
    maintenance clear-caches
  fi

  if [[ "$CLEAR_QDRANT" -eq 1 ]]; then
    log_info "Clearing Qdrant collections..."
    maintenance clear-qdrant --main --answer-cache
  fi

  if [[ "$CLEAR_DB" -eq 1 ]]; then
    log_warn "Resetting PostgreSQL database (drop + migrate)..."
    reset_postgres_db
  fi
}

deploy_backend() {
  log_section "Backend deploy"
  ensure_project_writable || return 1
  stop_backend || true
  if [[ "${MD_RELEASE_DEPLOY:-0}" == "1" ]]; then
    if [[ "${MD_BACKUP_COMPLETED:-0}" == "1" ]]; then
      log_info "Backup already completed in release stage 1 — skipping duplicate pg_dump"
    elif [[ "${DO_BACKUP_DB:-yes}" == "yes" ]]; then
      backup_postgres || return 1
      MD_BACKUP_COMPLETED=1
    else
      log_error "Release deploy requires backup — refused"
      return 1
    fi
  elif [[ "${DO_BACKUP_DB:-$BACKUP_DB_DEFAULT}" == "yes" ]]; then
    backup_postgres || return 1
  fi
  update_source_code || return 1
  ensure_venv || return 1
  run_migrations || return 1
  # Ownership is applied after frontend build in mode_full so npm is not locked out.
  if [[ "${SKIP_FIX_OWNERSHIP:-}" != "yes" ]]; then
    fix_ownership
  fi
  start_backend || return 1
  check_dependency_services
}

deploy_frontend() {
  log_section "Frontend deploy"
  ensure_project_writable || return 1
  update_source_code || return 1
  # Release stage 2 already built+rsynced dist (incl. .deploy-identity.json);
  # a second vite build would wipe the identity stamp.
  if [[ "${MD_RELEASE_DEPLOY:-0}" == "1" && -f "$FRONTEND_BUILD_DIR/index.html" ]]; then
    log_info "Release deploy: frontend artifact already present — skip duplicate npm build"
    write_frontend_deploy_identity
  else
    build_frontend || return 1
  fi
  fix_ownership
  reload_nginx || return 1
}

mode_full() {
  if [[ "${MD_RELEASE_DEPLOY:-0}" != "1" ]]; then
    if deploy_guard_emergency_enabled; then
      deploy_guard_require_emergency "legacy --mode full" || return 1
    else
      log_error "Refusing --mode full from operator checkout."
      log_error "Use: sudo bash deploy/manage_deploy.sh deploy full"
      return 1
    fi
  fi
  print_plan
  # Build UI before final chown so APP_USER!=deploy-user cannot break npm mid-run.
  SKIP_FIX_OWNERSHIP=yes deploy_backend || return 1
  ensure_project_writable || return 1
  # Release stage 2 already built+rsynced dist; duplicate vite build wipes identity.
  if [[ "${MD_RELEASE_DEPLOY:-0}" == "1" && -f "$FRONTEND_BUILD_DIR/index.html" ]]; then
    log_info "Release deploy: frontend artifact already present — skip duplicate npm build"
    write_frontend_deploy_identity
  else
    build_frontend || return 1
  fi
  fix_ownership
  reload_nginx || return 1
  health_checks
}

mode_backend() {
  if [[ "${MD_RELEASE_DEPLOY:-0}" != "1" ]]; then
    if deploy_guard_emergency_enabled; then
      deploy_guard_require_emergency "legacy --mode backend" || return 1
    else
      log_error "Refusing --mode backend from operator checkout."
      log_error "Use: sudo bash deploy/manage_deploy.sh deploy backend"
      return 1
    fi
  fi
  print_plan
  deploy_backend || return 1
  health_checks
}

mode_frontend() {
  if [[ "${MD_RELEASE_DEPLOY:-0}" != "1" ]]; then
    if deploy_guard_emergency_enabled; then
      deploy_guard_require_emergency "legacy --mode frontend" || return 1
    else
      log_error "Refusing --mode frontend from operator checkout."
      log_error "Use: sudo bash deploy/manage_deploy.sh deploy frontend"
      return 1
    fi
  fi
  log_section "Frontend-only deploy"
  deploy_frontend || return 1
  log_ok "Dashboard updated — hard-refresh browser (Ctrl+Shift+R) if UI looks stale"
}

mode_clean() {
  if ! confirm_destructive; then
    log_info "Cancelled."
    return 0
  fi

  if [[ "$INTERACTIVE" -eq 1 && "$ASSUME_YES" -eq 0 ]]; then
    echo ""
    log_info "Choose what to clean (safe default = No for each):"
    prompt_yn "  Back up PostgreSQL before changes?" "y" && DO_BACKUP_DB=yes || DO_BACKUP_DB=no
    prompt_yn "  Drop and recreate PostgreSQL database?" "n" && CLEAR_DB=1 || true
    prompt_yn "  Clear Qdrant vector collections?" "n" && CLEAR_QDRANT=1 || true
    prompt_yn "  Clear retrieval/answer caches only?" "n" && CLEAR_CACHES=1 || true
    prompt_yn "  Remove old dashboard dist/ before rebuild?" "n" && CLEAR_FRONTEND_BUILD=1 || true
    prompt_yn "  Recreate Python virtualenv?" "n" && RECREATE_VENV=1 || true
    echo ""
  fi

  stop_backend || true
  run_cleanup_tasks
  update_source_code || return 1
  ensure_venv || return 1
  run_migrations || return 1
  build_frontend || return 1
  fix_ownership
  start_backend || return 1
  reload_nginx || return 1
  health_checks
}

mode_clear_caches() {
  log_info "Clearing caches (indexed sources and Qdrant vectors are kept)..."
  stop_backend || true
  maintenance clear-caches || return 1
  start_backend || true
  log_ok "Caches cleared"
}

mode_reindex() {
  log_info "Starting full reindex (clears sources + vectors, then re-crawls)..."
  local api_base="${HEALTHCHECK_URL%/api/health}"
  if curl -sf --max-time 5 -X POST "${api_base}/api/index/reindex-all" -o /tmp/reindex.json 2>/dev/null; then
    cat /tmp/reindex.json
    echo ""
    log_ok "Reindex started via API — monitor in dashboard → Indexing"
    return 0
  fi
  log_warn "Backend API not reachable — using maintenance CLI"
  stop_backend || true
  maintenance trigger-reindex || return 1
  start_backend || return 1
  log_ok "Reindex job started"
}

# Wrap menu actions: do not exit the menu on failure (SSH-friendly).
run_menu_action() {
  local label="$1"
  shift
  log_section "$label"
  if "$@"; then
    log_ok "$label — finished successfully"
  else
    log_error "$label — finished with errors (see $LOG_FILE)"
  fi
  pause_menu
}

# Wrap CLI menu actions (release/deploy helpers).
run_menu_cli() {
  local label="$1"
  shift
  log_section "$label"
  # shellcheck source=deploy/lib/cli.sh
  source "$SCRIPT_DIR/lib/cli.sh"
  if "$@"; then
    log_ok "$label — finished successfully"
  else
    log_error "$label — finished with errors"
  fi
  pause_menu
}

interactive_menu() {
  show_banner
  preflight_check || log_warn "Some pre-flight checks failed — continue with care"
  pause_menu

  while true; do
    echo ""
    _color "1;37" "What do you want to do?"
    echo ""
    echo "  Deploy   (always from origin/main clean worktree)"
    echo "    1) Full deploy from origin/main   recommended"
    echo "    2) Backend from origin/main"
    echo "    3) Frontend from origin/main"
    echo ""
    echo "  Maintenance"
    echo "    4) Clean reinstall        destructive — asks what to wipe"
    echo "    5) Restart services       submenu: all or single module"
    echo "    6) Show status            modules + health probes"
    echo "    7) DB migrations          safe schema upgrade only"
    echo "    8) Rebuild frontend       npm build, no backend restart"
    echo "    9) Clear caches           keeps indexed sources"
    echo "   10) Reindex knowledge      full crawl from site settings"
    echo ""
    echo "  Operations"
    echo "   11) Start all modules     Запустити всі модулі"
    echo "   12) Stop all modules      Зупинити всі модулі"
    echo "   13) Restart all modules    Перезапустити всі модулі"
    echo "   14) Start selected module"
    echo "   15) Stop selected module"
    echo "   16) Restart selected module"
    echo "   17) Show logs             journalctl for selected module"
    echo ""
    echo "  Database (PostgreSQL)"
    echo "   18) Install PostgreSQL    apt install + enable service"
    echo "   19) Create role + DB      from DATABASE_URL in .env"
    echo "   20) Run migrations        alembic upgrade head"
    echo "   21) Check database        connection + migration revision"
    echo "   22) Back up database      pg_dump → backups/"
    echo "   23) Restore database      pg_restore from a dump file"
    echo "   24) Import SQLite → PG    one-time data migration"
    echo "   25) Reset database        destructive — drop + recreate + migrate"
    echo "   26) VACUUM ANALYZE        reclaim space + refresh planner stats"
    echo "   27) Show DB stats         table sizes + connection counters"
    echo "   28) Configure PostgreSQL  print tuning recommendations"
    echo "   29) Configure Ollama      print concurrency tuning for chat+indexing"
    echo ""
    echo "  Release engineering (origin/main only)"
    echo "   30) Release status         git + deploy readiness"
    echo "   31) Release check          make release-check gate"
    echo "   32) Prepare branch review  commits/files vs main"
    echo "   33) Merge branch → main    interactive confirm"
    echo "   34) Push origin/main       interactive confirm"
    echo "   35) Deploy from origin/main  clean worktree → /opt"
    echo "   36) Smoke verify           health / build / metrics"
    echo "   37) Verify release         full identity chain report"
    echo "   38) Show build-info API    GET /api/build"
    echo ""
    echo "    0) Exit"
    echo ""
    read -r -p "Enter choice [0-38]: " choice

    # Reset per-run flags to safe defaults.
    DO_BACKUP_DB=""
    DO_GIT_PULL=""
    DO_NPM_INSTALL=""
    DO_RELOAD_NGINX=""
    SYNC_FROM_DEV=""
    CLEAR_DB=0 CLEAR_QDRANT=0 CLEAR_CACHES=0 CLEAR_FRONTEND_BUILD=0 RECREATE_VENV=0

    case "$choice" in
      1)
        run_menu_cli "Deploy full from origin/main" md_cli_deploy full
        ;;
      2)
        run_menu_cli "Deploy backend from origin/main" md_cli_deploy backend
        ;;
      3)
        run_menu_cli "Deploy frontend from origin/main" md_cli_deploy frontend
        ;;
      4) run_menu_action "Clean reinstall" mode_clean ;;
      5) run_menu_action "Restart services" interactive_restart_menu ;;
      6) run_menu_action "Status" service_status ;;
      7) run_menu_action "DB migrations" run_migrations ;;
      8)
        prompt_yn "Remove old dist/ first?" "n" && CLEAR_FRONTEND_BUILD=1 || true
        run_menu_action "Frontend rebuild" build_frontend
        ;;
      9) run_menu_action "Clear caches" mode_clear_caches ;;
      10) run_menu_action "Reindex" mode_reindex ;;
      11) run_menu_action "Start all modules" op_start_all ;;
      12) run_menu_action "Stop all modules" op_stop_all ;;
      13) run_menu_action "Restart all modules" op_restart_all ;;
      14)
        if mod="$(pick_runtime_module)"; then
          run_menu_action "Start $mod" op_start_module "$mod"
        fi
        ;;
      15)
        if mod="$(pick_runtime_module)"; then
          run_menu_action "Stop $mod" op_stop_module "$mod"
        fi
        ;;
      16)
        if mod="$(pick_runtime_module)"; then
          run_menu_action "Restart $mod" bash -c "op_restart_module \"\$1\" && print_health_summary" _ "$mod"
        fi
        ;;
      17) run_menu_action "Module logs" show_module_logs ;;
      18) run_menu_action "Install PostgreSQL" install_postgres ;;
      19) run_menu_action "Create role + DB" setup_postgres_db ;;
      20) run_menu_action "Run migrations" run_migrations ;;
      21) run_menu_action "Check database" check_postgres ;;
      22) run_menu_action "Back up database" backup_postgres ;;
      23)
        read -r -p "Path to dump file: " _dump
        run_menu_action "Restore database" restore_postgres "$_dump"
        ;;
      24)
        read -r -p "Path to SQLite file [$BACKEND_DIR/ai_site_agent.db]: " _sqlite
        run_menu_action "Import SQLite → PostgreSQL" migrate_sqlite_to_postgres "${_sqlite:-$BACKEND_DIR/ai_site_agent.db}"
        ;;
      25) run_menu_action "Reset database" reset_postgres_db ;;
      26) run_menu_action "VACUUM ANALYZE" vacuum_analyze_postgres ;;
      27) run_menu_action "Show DB stats" show_db_stats ;;
      28) run_menu_action "Configure PostgreSQL" configure_postgres ;;
      29) run_menu_action "Configure Ollama" configure_ollama ;;
      30) run_menu_cli "Release status" md_cli_release status ;;
      31) run_menu_cli "Release check" md_cli_release check ;;
      32)
        read -r -p "Branch to review [$(git -C "$REPO_ROOT" symbolic-ref -q --short HEAD 2>/dev/null || echo feature)]: " _prep
        _prep="${_prep:-$(git -C "$REPO_ROOT" symbolic-ref -q --short HEAD 2>/dev/null || true)}"
        run_menu_cli "Prepare branch $_prep" md_cli_release prepare --branch "$_prep"
        ;;
      33)
        read -r -p "Branch to merge into main: " _merge
        if [[ -n "$_merge" ]]; then
          run_menu_cli "Merge $_merge into main" md_cli_release merge --branch "$_merge"
        fi
        ;;
      34) run_menu_cli "Push origin/main" md_cli_release push ;;
      35) run_menu_cli "Deploy from origin/main" md_cli_deploy full ;;
      36) run_menu_cli "Smoke verify" bash "$REPO_ROOT/scripts/release/smoke-staging.sh" ;;
      37) run_menu_cli "Verify release" bash "$REPO_ROOT/scripts/release/verify-release.sh" ;;
      38) run_menu_cli "Build info" bash -c 'curl -sf http://127.0.0.1:8000/api/build | python3 -m json.tool' ;;
      0|q|Q) log_info "Goodbye."; exit 0 ;;
      *)
        log_error "Invalid choice: $choice"
        pause_menu
        ;;
    esac
  done
}

main() {
  # Canonical CLI: manage_deploy.sh <command> … (not --mode/--action)
  if [[ "${MD_SKIP_CLI:-0}" != "1" && $# -gt 0 && "$1" != --* ]]; then
    # shellcheck source=deploy/lib/cli.sh
    source "$SCRIPT_DIR/lib/cli.sh"
    md_cli_main "$@"
    exit $?
  fi

  parse_args "$@"
  load_env_overrides
  detect_project_root
  load_env_overrides
  augment_path_for_node

  log_info "Log: $LOG_FILE"

  if [[ "$INTERACTIVE" -eq 1 && -z "$MODE" && -z "$ACTION" ]]; then
    interactive_menu
    exit 0
  fi

  # Non-interactive: fail fast on errors.
  set -e

  if [[ -n "${ACTION:-}" ]]; then
    run_action "$ACTION"
    exit $?
  fi

  case "${MODE:-}" in
    full)
      if [[ "${MD_RELEASE_DEPLOY:-0}" != "1" ]]; then
        log_warn "Deprecated: --mode full from arbitrary checkout"
        log_warn "Use: manage_deploy.sh deploy full  (origin/main clean worktree)"
      fi
      mode_full
      ;;
    update)
      log_error "Deprecated: --mode update (deployed dirty/feature trees)."
      log_error "Use: sudo bash deploy/manage_deploy.sh deploy full"
      exit 1
      ;;
    backend)
      if [[ "${MD_RELEASE_DEPLOY:-0}" != "1" ]]; then
        log_warn "Deprecated: --mode backend — prefer: manage_deploy.sh deploy backend"
      fi
      mode_backend
      ;;
    frontend)
      if [[ "${MD_RELEASE_DEPLOY:-0}" != "1" ]]; then
        log_warn "Deprecated: --mode frontend — prefer: manage_deploy.sh deploy frontend"
      fi
      mode_frontend
      ;;
    clean) mode_clean ;;
    restart) op_restart_all ;;
    plan) show_deploy_plan ;;
    status) service_status ;;
    migrate) run_migrations ;;
    build-frontend) build_frontend ;;
    clear-caches) mode_clear_caches ;;
    clear-retrieval-cache)
      log_info "Clearing retrieval cache..."
      stop_backend || true
      maintenance clear-retrieval-cache || return 1
      start_backend || true
      ;;
    clear-answer-cache)
      log_info "Clearing answer cache..."
      stop_backend || true
      maintenance clear-answer-cache || return 1
      start_backend || true
      ;;
    reindex) mode_reindex ;;
    "")
      usage
      exit 1
      ;;
    *)
      log_error "Unknown mode: $MODE"
      usage
      exit 1
      ;;
  esac
}

main "$@"
