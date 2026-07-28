#!/usr/bin/env bash
#
# Release deploy: build from an explicit origin/main commit via a clean detached worktree.
# Never rsyncs from a dirty development checkout.
#
#   sudo bash deploy/deploy_from_main.sh
#   sudo DEPLOY_COMMIT=<sha> bash deploy/deploy_from_main.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=deploy/lib/deploy_guard.sh
source "$SCRIPT_DIR/lib/deploy_guard.sh"

# shellcheck source=deploy.conf
source "$SCRIPT_DIR/deploy.conf"
if [[ -f "$SCRIPT_DIR/deploy.local.conf" ]]; then
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/deploy.local.conf"
fi

npm_cmd() {
  if [[ -n "${NPM_BIN:-}" && -x "$NPM_BIN" ]]; then
    echo "$NPM_BIN"
  elif command -v npm &>/dev/null; then
    command -v npm
  else
    local owner home nvm_bin
    owner="${SUDO_USER:-${USER:-}}"
    if [[ -n "$owner" && "$owner" != "root" ]]; then
      home="$(getent passwd "$owner" 2>/dev/null | cut -d: -f6 || true)"
      if [[ -n "$home" && -d "$home/.nvm/versions/node" ]]; then
        nvm_bin="$(ls -1d "$home/.nvm/versions/node/"*/bin/npm 2>/dev/null | sort -V | tail -1 || true)"
        if [[ -x "$nvm_bin" ]]; then
          echo "$nvm_bin"
          return 0
        fi
      fi
    fi
    return 1
  fi
}

PROJECT_ROOT="${PROJECT_ROOT:-/opt/ai-site-agent}"
DEPLOY_COMMIT="${DEPLOY_COMMIT:-}"
ALLOW_DIRTY_SYNC="${ALLOW_DIRTY_SYNC:-0}"
WORKTREE=""
LOG_PREFIX="[deploy_from_main]"

log() { echo "$LOG_PREFIX $*"; }
die() { echo "$LOG_PREFIX ERROR: $*" >&2; exit 1; }

cleanup_worktree() {
  if [[ -n "$WORKTREE" && -d "$WORKTREE" ]]; then
    git -C "$REPO_ROOT" worktree remove --force "$WORKTREE" 2>/dev/null || rm -rf "$WORKTREE"
  fi
}
trap cleanup_worktree EXIT

if [[ "$(id -u)" -ne 0 && ! "${DEPLOY_SKIP_ROOT_CHECK:-0}" == "1" ]]; then
  die "run with sudo so manage_deploy can restart services and rsync to $PROJECT_ROOT"
fi

if [[ "${DEPLOY_LOCAL_MAIN:-0}" == "1" ]]; then
  COMMIT="$(deploy_guard_local_main_hash "$REPO_ROOT")"
  [[ -n "$COMMIT" ]] || die "local main branch not found"
else
  COMMIT="$(deploy_guard_resolve_commit "$REPO_ROOT" "$DEPLOY_COMMIT")"
fi
log "target commit: $COMMIT"

if [[ "${DEPLOY_LOCAL_MAIN:-0}" == "1" ]]; then
  LOCAL_MAIN="$(deploy_guard_local_main_hash "$REPO_ROOT")"
  if [[ "$COMMIT" != "$LOCAL_MAIN" ]]; then
    die "DEPLOY_LOCAL_MAIN=1 requires DEPLOY_COMMIT unset and main at $LOCAL_MAIN (got $COMMIT)"
  fi
  log "WARN: DEPLOY_LOCAL_MAIN=1 — deploying local main without origin/main verification"
  log "WARN: push origin/main before production operators rely on remote baseline"
else
  deploy_guard_assert_commit_on_main "$REPO_ROOT" "$COMMIT" || die "commit not on origin/main"
  if [[ -z "$DEPLOY_COMMIT" ]]; then
    deploy_guard_assert_local_main_matches_origin "$REPO_ROOT" || die "local main out of sync with origin/main"
  fi
fi

WORKTREE="$(mktemp -d /tmp/ai-site-agent-deploy-XXXXXX)"
log "creating clean worktree at $WORKTREE"
git -C "$REPO_ROOT" worktree add --detach "$WORKTREE" "$COMMIT" >/dev/null

deploy_guard_assert_clean_worktree "$WORKTREE" "deploy worktree" || die "worktree not clean"

log "writing .build-info.json (release 0.7 @ $COMMIT)"
RELEASE_VERSION=0.7 ROOT="$WORKTREE" bash "$WORKTREE/scripts/release/write-build-info.sh"

log "building dashboard from commit $COMMIT"
NPM="$(npm_cmd)" || die "npm not found — set NPM_BIN in deploy/deploy.local.conf (sudo drops nvm from PATH)"
cd "$WORKTREE/dashboard"
if [[ ! -d node_modules ]]; then
  "$NPM" ci --silent
else
  "$NPM" install --silent
fi
"$NPM" run build

if [[ ! -f "$WORKTREE/dashboard/dist/index.html" ]]; then
  die "frontend build missing at $WORKTREE/dashboard/dist/index.html"
fi

log "staging frontend dist → $PROJECT_ROOT/dashboard/dist"
mkdir -p "$PROJECT_ROOT/dashboard/dist"
rsync -a --delete "$WORKTREE/dashboard/dist/" "$PROJECT_ROOT/dashboard/dist/"

log "deploying worktree → $PROJECT_ROOT (preserves .env, backups, logs)"
export PROJECT_ROOT
export DEV_CHECKOUT="$WORKTREE"
export ALLOW_DIRTY_SYNC="$ALLOW_DIRTY_SYNC"
# Propagate machine overrides — worktree lacks gitignored deploy.local.conf.
export NPM_BIN NODE_BIN APP_USER APP_GROUP
exec bash "$WORKTREE/deploy/manage_deploy.sh" \
  --mode full \
  --sync-from-dev \
  --no-git-pull \
  --yes \
  "$@"
