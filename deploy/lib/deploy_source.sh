#!/usr/bin/env bash
# Canonical clean-worktree deploy from origin/main (never dirty/feature checkout).
set -euo pipefail

md_deploy_source_init() {
  MD_DEPLOY_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  MD_DEPLOY_REPO_ROOT="$(cd "$MD_DEPLOY_SCRIPT_DIR/.." && pwd)"
  # shellcheck source=deploy/lib/deploy_guard.sh
  source "$MD_DEPLOY_SCRIPT_DIR/lib/deploy_guard.sh"
  # shellcheck source=deploy/lib/node_path.sh
  source "$MD_DEPLOY_SCRIPT_DIR/lib/node_path.sh"
  # shellcheck source=deploy.conf
  source "$MD_DEPLOY_SCRIPT_DIR/deploy.conf"
  if [[ -f "$MD_DEPLOY_SCRIPT_DIR/deploy.local.conf" ]]; then
    # shellcheck source=/dev/null
    source "$MD_DEPLOY_SCRIPT_DIR/deploy.local.conf"
  fi
  MD_DEPLOY_PROJECT_ROOT="${PROJECT_ROOT:-/opt/ai-site-agent}"
  MD_DEPLOY_WORKTREE=""
}

md_deploy_source_cleanup() {
  if [[ -n "${MD_DEPLOY_WORKTREE:-}" && -d "${MD_DEPLOY_WORKTREE}" ]]; then
    git -C "${MD_DEPLOY_REPO_ROOT}" worktree remove --force "${MD_DEPLOY_WORKTREE}" 2>/dev/null \
      || rm -rf "${MD_DEPLOY_WORKTREE}"
  fi
}

md_write_frontend_identity() {
  local root="$1"
  local commit="$2"
  local short
  short="$(git -C "$root" rev-parse --short "$commit" 2>/dev/null || echo "${commit:0:7}")"
  mkdir -p "$root/dashboard/dist"
  python3 - <<PY
import json
from pathlib import Path
payload = {
    "git_commit": "$commit",
    "git_commit_short": "$short",
    "artifact": "dashboard/dist",
}
Path("$root/dashboard/dist/.deploy-identity.json").write_text(
    json.dumps(payload, indent=2) + "\n", encoding="utf-8"
)
print("OK: frontend identity → $root/dashboard/dist/.deploy-identity.json")
PY
}

# md_deploy_from_main [mode] — mode: full|backend|frontend (default full)
md_deploy_from_main() {
  local mode="${1:-full}"
  md_deploy_source_init
  trap md_deploy_source_cleanup EXIT

  local repo="$MD_DEPLOY_REPO_ROOT"
  local commit

  if [[ "$(id -u)" -ne 0 && "${DEPLOY_SKIP_ROOT_CHECK:-0}" != "1" ]]; then
    echo "ERROR: run with sudo for systemd/nginx deploy to $MD_DEPLOY_PROJECT_ROOT" >&2
    return 1
  fi

  deploy_guard_reject_legacy_bypasses || return 1

  # Operator checkout must be on main, clean, and synced — even though we build
  # from a detached worktree of origin/main.
  deploy_guard_assert_not_detached "$repo" || return 1
  deploy_guard_assert_on_main_branch "$repo" || return 1
  deploy_guard_assert_clean_worktree "$repo" "operator checkout" || return 1
  deploy_guard_fetch_origin "$repo"

  if deploy_guard_emergency_enabled; then
    deploy_guard_require_emergency "emergency deploy commit selection" || return 1
    commit="$(deploy_guard_resolve_commit "$repo" "${DEPLOY_COMMIT:-}")"
    echo "WARN: emergency — deploying commit $commit (may not equal origin/main tip)" >&2
  else
    commit="$(deploy_guard_resolve_commit "$repo" "${DEPLOY_COMMIT:-}")"
    deploy_guard_assert_commit_on_main "$repo" "$commit" || return 1
    if [[ -z "${DEPLOY_COMMIT:-}" ]]; then
      deploy_guard_assert_local_main_matches_origin "$repo" || return 1
    else
      # Explicit DEPLOY_COMMIT must still be on origin/main ancestry.
      deploy_guard_assert_commit_on_main "$repo" "$commit" || return 1
    fi
  fi

  echo "[deploy] target commit: $commit"
  MD_DEPLOY_WORKTREE="$(mktemp -d /tmp/ai-site-agent-deploy-XXXXXX)"
  echo "[deploy] clean worktree: $MD_DEPLOY_WORKTREE"
  git -C "$repo" worktree add --detach "$MD_DEPLOY_WORKTREE" "$commit" >/dev/null
  deploy_guard_assert_clean_worktree "$MD_DEPLOY_WORKTREE" "deploy worktree" || return 1

  echo "[deploy] build-info @ $commit"
  RELEASE_VERSION="${RELEASE_VERSION:-0.7}" ROOT="$MD_DEPLOY_WORKTREE" \
    EXPECTED_COMMIT="$commit" \
    bash "$MD_DEPLOY_WORKTREE/scripts/release/write-build-info.sh"
  deploy_guard_assert_build_info_matches_commit "$MD_DEPLOY_WORKTREE" "$commit" || return 1

  if [[ "$mode" == "full" || "$mode" == "frontend" ]]; then
    echo "[deploy] building dashboard"
    md_augment_path_for_node
    local npm
    npm="$(md_npm_cmd)" || { echo "ERROR: npm not found — set NPM_BIN in deploy.local.conf" >&2; return 1; }
    command -v node &>/dev/null || { echo "ERROR: node not on PATH — set NODE_BIN" >&2; return 1; }
    cd "$MD_DEPLOY_WORKTREE/dashboard"
    if [[ ! -d node_modules ]]; then "$npm" ci --silent; else "$npm" install --silent; fi
    "$npm" run build
    [[ -f "$MD_DEPLOY_WORKTREE/dashboard/dist/index.html" ]] \
      || { echo "ERROR: frontend build missing" >&2; return 1; }
    md_write_frontend_identity "$MD_DEPLOY_WORKTREE" "$commit"
    mkdir -p "$MD_DEPLOY_PROJECT_ROOT/dashboard/dist"
    rsync -a --delete "$MD_DEPLOY_WORKTREE/dashboard/dist/" "$MD_DEPLOY_PROJECT_ROOT/dashboard/dist/"
    deploy_guard_assert_frontend_identity "$MD_DEPLOY_PROJECT_ROOT" "$commit" || return 1
  fi

  export PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT"
  export DEV_CHECKOUT="$MD_DEPLOY_WORKTREE"
  unset ALLOW_DIRTY_SYNC || true
  export NPM_BIN NODE_BIN APP_USER APP_GROUP PATH
  export MD_SKIP_CLI=1
  export MD_DEPLOY_COMMIT="$commit"
  export MD_RELEASE_DEPLOY=1

  local legacy_mode="full"
  [[ "$mode" == "backend" ]] && legacy_mode="backend"
  [[ "$mode" == "frontend" ]] && legacy_mode="frontend"

  bash "$MD_DEPLOY_WORKTREE/deploy/manage_deploy.sh" \
    --mode "$legacy_mode" \
    --sync-from-dev \
    --no-git-pull \
    --yes \
    "${@:2}"

  # Post-sync identity must still match (rsync preserves .build-info.json).
  deploy_guard_assert_build_info_matches_commit "$MD_DEPLOY_PROJECT_ROOT" "$commit" || return 1
  if [[ "$mode" == "full" || "$mode" == "frontend" ]]; then
    deploy_guard_assert_frontend_identity "$MD_DEPLOY_PROJECT_ROOT" "$commit" || return 1
  fi

  # shellcheck source=deploy/lib/manifest.sh
  source "$MD_DEPLOY_SCRIPT_DIR/lib/manifest.sh"
  md_write_deploy_manifest "$MD_DEPLOY_PROJECT_ROOT" "$commit" "${MD_DEPLOY_MANIFEST_SMOKE:-skipped}"
  echo "[deploy] OK — origin/main worktree $commit → $MD_DEPLOY_PROJECT_ROOT"
}
