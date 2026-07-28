#!/usr/bin/env bash
# Canonical clean-worktree deploy from origin/main (never dirty/feature checkout).
#
# Mandatory release stages:
#   1. backup → 2. build → 3. deploy → 4. verify → 5. restart → 6. smoke
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
  MD_DEPLOY_RELEASE="${RELEASE_VERSION:-0.7}"
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
  local short release
  short="$(git -C "$root" rev-parse --short "$commit" 2>/dev/null || echo "${commit:0:7}")"
  release="$(deploy_guard_read_app_release "$root" || echo "${MD_DEPLOY_RELEASE}")"
  mkdir -p "$root/dashboard/dist"
  python3 - <<PY
import json
from pathlib import Path
payload = {
    "git_commit": "$commit",
    "git_commit_short": "$short",
    "release": "$release",
    "artifact": "dashboard/dist",
}
Path("$root/dashboard/dist/.deploy-identity.json").write_text(
    json.dumps(payload, indent=2) + "\n", encoding="utf-8"
)
print("OK: frontend identity → $root/dashboard/dist/.deploy-identity.json")
PY
}

md_deploy_strip_no_backup_args() {
  local out=()
  local a
  for a in "$@"; do
    if [[ "$a" == "--no-backup-db" ]]; then
      echo "ERROR: --no-backup-db is forbidden on release deploy (backup is mandatory)" >&2
      return 1
    fi
    out+=("$a")
  done
  MD_DEPLOY_FORWARD_ARGS=("${out[@]}")
}

md_deploy_mandatory_backup() {
  echo "[deploy 1/6] BACKUP (mandatory)"
  # Backup live /opt database before any code/build mutation.
  PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT" \
    MD_SKIP_CLI=1 \
    bash "$MD_DEPLOY_SCRIPT_DIR/manage_deploy.sh" --action backup-postgres --yes \
    || {
      echo "ERROR: mandatory backup failed — aborting release deploy" >&2
      return 1
    }
  export MD_BACKUP_COMPLETED=1
  echo "[deploy 1/6] BACKUP OK"
}

# md_deploy_from_main [mode] — mode: full|backend|frontend (default full)
md_deploy_from_main() {
  local mode="${1:-full}"
  shift || true
  md_deploy_source_init
  trap md_deploy_source_cleanup EXIT

  local repo="$MD_DEPLOY_REPO_ROOT"
  local commit

  if [[ "$(id -u)" -ne 0 && "${DEPLOY_SKIP_ROOT_CHECK:-0}" != "1" ]]; then
    echo "ERROR: run with sudo for systemd/nginx deploy to $MD_DEPLOY_PROJECT_ROOT" >&2
    return 1
  fi

  deploy_guard_reject_legacy_bypasses || return 1
  md_deploy_strip_no_backup_args "$@" || return 1

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
      deploy_guard_assert_commit_on_main "$repo" "$commit" || return 1
    fi
  fi

  echo "[deploy] target commit: $commit  release: $MD_DEPLOY_RELEASE"

  # --- 1/6 BACKUP ---
  md_deploy_mandatory_backup || return 1

  # --- 2/6 BUILD ---
  echo "[deploy 2/6] BUILD (worktree + identity)"
  MD_DEPLOY_WORKTREE="$(mktemp -d /tmp/ai-site-agent-deploy-XXXXXX)"
  echo "[deploy] clean worktree: $MD_DEPLOY_WORKTREE"
  git -C "$repo" worktree add --detach "$MD_DEPLOY_WORKTREE" "$commit" >/dev/null
  deploy_guard_assert_clean_worktree "$MD_DEPLOY_WORKTREE" "deploy worktree" || return 1

  RELEASE_VERSION="$MD_DEPLOY_RELEASE" ROOT="$MD_DEPLOY_WORKTREE" \
    EXPECTED_COMMIT="$commit" \
    bash "$MD_DEPLOY_WORKTREE/scripts/release/write-build-info.sh"
  deploy_guard_assert_build_info_matches_commit "$MD_DEPLOY_WORKTREE" "$commit" || return 1
  deploy_guard_assert_release_identity "$MD_DEPLOY_WORKTREE" "$commit" "$MD_DEPLOY_RELEASE" || return 1

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
  echo "[deploy 2/6] BUILD OK"

  # --- 3/6 DEPLOY (sync + migrate; backup already done) ---
  echo "[deploy 3/6] DEPLOY (sync + migrate)"
  export PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT"
  export DEV_CHECKOUT="$MD_DEPLOY_WORKTREE"
  unset ALLOW_DIRTY_SYNC || true
  export NPM_BIN NODE_BIN APP_USER APP_GROUP PATH
  export MD_SKIP_CLI=1
  export MD_DEPLOY_COMMIT="$commit"
  export MD_RELEASE_DEPLOY=1
  export MD_BACKUP_COMPLETED=1
  # Still force backup flag yes so inner path cannot opt out; deploy_backend
  # skips duplicate dump when MD_BACKUP_COMPLETED=1.
  export DO_BACKUP_DB=yes

  local legacy_mode="full"
  [[ "$mode" == "backend" ]] && legacy_mode="backend"
  [[ "$mode" == "frontend" ]] && legacy_mode="frontend"

  bash "$MD_DEPLOY_WORKTREE/deploy/manage_deploy.sh" \
    --mode "$legacy_mode" \
    --sync-from-dev \
    --no-git-pull \
    --backup-db \
    --yes \
    "${MD_DEPLOY_FORWARD_ARGS[@]:-}"
  echo "[deploy 3/6] DEPLOY OK"

  # --- 4/6 VERIFY ---
  echo "[deploy 4/6] VERIFY (identity)"
  deploy_guard_assert_build_info_matches_commit "$MD_DEPLOY_PROJECT_ROOT" "$commit" || return 1
  deploy_guard_assert_release_identity "$MD_DEPLOY_PROJECT_ROOT" "$commit" "$MD_DEPLOY_RELEASE" || return 1
  if [[ "$mode" == "full" || "$mode" == "frontend" ]]; then
    deploy_guard_assert_frontend_identity "$MD_DEPLOY_PROJECT_ROOT" "$commit" || return 1
  fi
  echo "[deploy 4/6] VERIFY OK"

  # --- 5/6 RESTART (ensure services up after deploy) ---
  echo "[deploy 5/6] RESTART"
  MD_SKIP_CLI=1 PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT" \
    bash "$MD_DEPLOY_PROJECT_ROOT/deploy/manage_deploy.sh" --action restart-all --yes \
    || MD_SKIP_CLI=1 PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT" \
         bash "$MD_DEPLOY_SCRIPT_DIR/manage_deploy.sh" --action restart-all --yes \
    || true
  # Prefer project copy; fall back to repo script. Soft-warn if systemd unavailable.
  echo "[deploy 5/6] RESTART attempted"

  # --- 6/6 SMOKE ---
  echo "[deploy 6/6] SMOKE"
  local smoke_result="pass"
  if ! bash "$MD_DEPLOY_REPO_ROOT/scripts/release/smoke-staging.sh"; then
    smoke_result="fail"
    echo "ERROR: smoke failed after deploy" >&2
    # shellcheck source=deploy/lib/manifest.sh
    source "$MD_DEPLOY_SCRIPT_DIR/lib/manifest.sh"
    md_write_deploy_manifest "$MD_DEPLOY_PROJECT_ROOT" "$commit" "$smoke_result"
    return 1
  fi
  echo "[deploy 6/6] SMOKE OK"

  # shellcheck source=deploy/lib/manifest.sh
  source "$MD_DEPLOY_SCRIPT_DIR/lib/manifest.sh"
  md_write_deploy_manifest "$MD_DEPLOY_PROJECT_ROOT" "$commit" "$smoke_result"
  echo "[deploy] OK — origin/main $commit (release $MD_DEPLOY_RELEASE) → $MD_DEPLOY_PROJECT_ROOT"
  echo "[deploy] stages: backup → build → deploy → verify → restart → smoke"
}
