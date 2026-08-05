#!/usr/bin/env bash
# One Command Deployment — canonical clean-worktree deploy from origin/main.
#
# Frozen pipeline (deploy full) — amendment Part 8 FE publish after sync:
#   1 preflight → 2 backup → 3 migration decision → 4 conditional schema-first
#   → 5 build (+ provenance) → 6 sync → 6b publish/swap/stamp → 7 post-sync migrate
#   → 8 restart → 9 health → 10 verify-release → 11 smoke → 12 report → 13 SUCCESS
set -euo pipefail

md_deploy_source_init() {
  MD_DEPLOY_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  MD_DEPLOY_REPO_ROOT="$(cd "$MD_DEPLOY_SCRIPT_DIR/.." && pwd)"
  # shellcheck source=deploy/lib/deploy_guard.sh
  source "$MD_DEPLOY_SCRIPT_DIR/lib/deploy_guard.sh"
  # shellcheck source=deploy/lib/node_path.sh
  source "$MD_DEPLOY_SCRIPT_DIR/lib/node_path.sh"
  # shellcheck source=deploy/lib/migration_decision.sh
  source "$MD_DEPLOY_SCRIPT_DIR/lib/migration_decision.sh"
  # shellcheck source=deploy/lib/verify_release.sh
  source "$MD_DEPLOY_SCRIPT_DIR/lib/verify_release.sh"
  # shellcheck source=deploy/lib/manifest.sh
  source "$MD_DEPLOY_SCRIPT_DIR/lib/manifest.sh"
  # shellcheck source=deploy.conf
  source "$MD_DEPLOY_SCRIPT_DIR/deploy.conf"
  if [[ -f "$MD_DEPLOY_SCRIPT_DIR/deploy.local.conf" ]]; then
    # shellcheck source=/dev/null
    source "$MD_DEPLOY_SCRIPT_DIR/deploy.local.conf"
  fi
  MD_DEPLOY_PROJECT_ROOT="${PROJECT_ROOT:-/opt/ai-site-agent}"
  MD_DEPLOY_WORKTREE=""
  MD_DEPLOY_CONFIGURED_RELEASE="${RELEASE_VERSION:-}"
  MD_DEPLOY_RELEASE=""
  MD_DEPLOY_START_EPOCH="$(date +%s)"
  MD_DEPLOY_PARTIAL="false"
  MD_DEPLOY_SYNC_STARTED=0
  MD_REPORT_OUTCOME="failed"
  MD_REPORT_PARTIAL_DEPLOY="false"
  MD_REPORT_MIGRATION_DECISION="not_reached"
  MD_REPORT_MIGRATION_SCHEMA_FIRST="not_reached"
  MD_REPORT_MIGRATION_POST_SYNC="not_reached"
  MD_REPORT_RESTART_RESULT="not_reached"
  MD_REPORT_HEALTH_RESULT="not_reached"
  MD_REPORT_VERIFY_RESULT="not_reached"
  MD_REPORT_SMOKE_RESULT="not_reached"
  MD_REPORT_BACKUP_PATH=""
  MD_REPORT_BACKUP_ID=""
  MD_REPORT_MANIFEST_PATH=""
  MD_REPORT_FAILED_STAGE=""
  MD_REPORT_FAILED_STAGE_DETAIL=""
}

md_deploy_source_cleanup() {
  if [[ -n "${MD_DEPLOY_WORKTREE:-}" && -d "${MD_DEPLOY_WORKTREE}" ]]; then
    git -C "${MD_DEPLOY_REPO_ROOT}" worktree remove --force "${MD_DEPLOY_WORKTREE}" 2>/dev/null \
      || rm -rf "${MD_DEPLOY_WORKTREE}"
  fi
}

md_deploy_duration() {
  local now
  now="$(date +%s)"
  echo $((now - MD_DEPLOY_START_EPOCH))
}

md_deploy_read_previous_identity() {
  local build_json="$MD_DEPLOY_PROJECT_ROOT/.build-info.json"
  MD_REPORT_PREVIOUS_COMMIT="unknown"
  MD_REPORT_PREVIOUS_RELEASE="unknown"
  if [[ -f "$build_json" ]]; then
    MD_REPORT_PREVIOUS_COMMIT="$(python3 -c "import json; print(json.load(open('$build_json')).get('git_commit') or 'unknown')" 2>/dev/null || echo unknown)"
    MD_REPORT_PREVIOUS_RELEASE="$(python3 -c "import json; print(json.load(open('$build_json')).get('release') or 'unknown')" 2>/dev/null || echo unknown)"
  fi
}

md_deploy_capture_backup_path() {
  local newest
  newest="$(ls -1t "$MD_DEPLOY_PROJECT_ROOT/backups/"*.dump 2>/dev/null | head -1 || echo "")"
  MD_REPORT_BACKUP_PATH="$newest"
  if [[ -n "$newest" ]]; then
    MD_REPORT_BACKUP_ID="$(basename "$newest" .dump)"
  fi
}

md_deploy_mark_sync_started() {
  MD_DEPLOY_SYNC_STARTED=1
  MD_DEPLOY_PARTIAL="true"
  MD_REPORT_PARTIAL_DEPLOY="true"
}

md_deploy_fail() {
  local stage="$1"
  local detail="${2:-}"
  MD_REPORT_FAILED_STAGE="$stage"
  MD_REPORT_FAILED_STAGE_DETAIL="$detail"
  MD_REPORT_OUTCOME="failed"
  MD_REPORT_DURATION_SECONDS="$(md_deploy_duration)"
  if [[ "$MD_DEPLOY_SYNC_STARTED" -eq 1 ]]; then
    MD_REPORT_PARTIAL_DEPLOY="true"
  else
    MD_REPORT_PARTIAL_DEPLOY="false"
  fi
  echo ""
  echo "[deploy] FAILED at stage=$stage"
  [[ -n "$detail" ]] && echo "[deploy] detail: $detail"

  local wrote=0
  if md_write_deploy_report "$MD_DEPLOY_PROJECT_ROOT" 2>/dev/null; then
    wrote=1
  else
    echo "WARN: could not write deployment report" >&2
  fi

  local rollback
  rollback="$(md_rollback_recommendation "$stage" failed)"
  echo ""
  echo "VERDICT: FAILED"
  echo "  failed_stage:            $stage"
  echo "  attempted_commit:        ${MD_REPORT_DEPLOYED_COMMIT:-unknown}"
  echo "  previous_commit:         ${MD_REPORT_PREVIOUS_COMMIT:-unknown}"
  echo "  previous_release:        ${MD_REPORT_PREVIOUS_RELEASE:-unknown}"
  echo "  partial_deploy:          ${MD_REPORT_PARTIAL_DEPLOY}"
  echo "  backup_path:             ${MD_REPORT_BACKUP_PATH:-}"
  echo "  rollback_recommendation: $rollback"
  if [[ "$wrote" -eq 1 ]]; then
    echo "  manifest_path:           ${MD_REPORT_MANIFEST_PATH}"
  else
    echo "  manifest_path:           manifest_unavailable"
  fi
  return 1
}

md_deploy_success_summary() {
  local duration schema_label
  duration="$(md_deploy_duration)"
  if [[ "${MD_REPORT_MIGRATION_SCHEMA_FIRST}" == "executed" ]]; then
    schema_label="executed"
  else
    schema_label="skipped"
  fi
  echo ""
  echo "VERDICT: SUCCESS"
  echo "  deployed_commit:         ${MD_REPORT_DEPLOYED_COMMIT}"
  echo "  deployed_release:        ${MD_REPORT_DEPLOYED_RELEASE}"
  echo "  migration_decision:      ${MD_REPORT_MIGRATION_DECISION}"
  echo "  schema_first:            $schema_label"
  echo "  restart_result:          ${MD_REPORT_RESTART_RESULT}"
  echo "  health_result:           ${MD_REPORT_HEALTH_RESULT}"
  echo "  verify_release_result:   ${MD_REPORT_VERIFY_RESULT}"
  echo "  smoke_result:            ${MD_REPORT_SMOKE_RESULT}"
  echo "  backup_path:             ${MD_REPORT_BACKUP_PATH}"
  echo "  manifest_path:           ${MD_REPORT_MANIFEST_PATH}"
  echo "  duration_seconds:        $duration"
}

# FE publication helpers (amendment Part 1 / Part 8) — single path.
md_frontend_provenance_py() {
  echo "$MD_DEPLOY_SCRIPT_DIR/lib/frontend_provenance.py"
}

md_write_frontend_provenance() {
  local dist="$1"
  local commit="$2"
  local release="$3"
  local build_time
  build_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python3 "$(md_frontend_provenance_py)" write \
    --dist "$dist" \
    --commit "$commit" \
    --release "$release" \
    --build-time "$build_time"
}

# Single identity stamp — only after provenance PASS (stamp cmd verifies first).
md_stamp_frontend_identity() {
  local dist="$1"
  local commit="$2"
  local release="$3"
  python3 "$(md_frontend_provenance_py)" stamp \
    --dist "$dist" \
    --commit "$commit" \
    --release "$release"
}

md_reload_nginx_after_publish() {
  if [[ "$(id -u)" -eq 0 ]]; then
    nginx -t && systemctl reload nginx
  else
    sudo nginx -t && sudo systemctl reload nginx
  fi
}

# Part 1 — sole legal publication path (worktree dist → dist.next → swap → live → stamp).
# Sets MD_FE_PUBLISH_FAIL_STAGE on failure for md_deploy_fail.
md_publish_frontend_artifact() {
  local worktree="$1"
  local project_root="$2"
  local commit="$3"
  local release="$4"
  local src="${worktree}/dashboard/dist"
  local dash="${project_root}/dashboard"
  local live="${dash}/dist"
  local next="${dash}/dist.next"
  local old="${dash}/dist.old"

  MD_FE_PUBLISH_FAIL_STAGE="frontend_publish"

  [[ -f "$src/index.html" ]] || {
    echo "ERROR: missing worktree dist index.html: $src/index.html" >&2
    return 1
  }
  [[ -f "$src/.frontend-provenance.json" ]] || {
    echo "ERROR: missing worktree provenance: $src/.frontend-provenance.json" >&2
    return 1
  }

  mkdir -p "$dash"
  rm -rf "$next"
  mkdir -p "$next"
  if ! rsync -a --delete "$src/" "$next/"; then
    echo "ERROR: failed to materialize dist.next from worktree dist" >&2
    rm -rf "$next"
    return 1
  fi

  MD_FE_PUBLISH_FAIL_STAGE="frontend_provenance"
  if ! deploy_guard_assert_frontend_provenance "$next" "$commit"; then
    rm -rf "$next"
    return 1
  fi

  MD_FE_PUBLISH_FAIL_STAGE="frontend_publish"
  # Atomic swap on same filesystem.
  if [[ -e "$live" ]]; then
    rm -rf "$old"
    if ! mv "$live" "$old"; then
      echo "ERROR: failed to move live dist → dist.old" >&2
      rm -rf "$next"
      return 1
    fi
  fi
  if ! mv "$next" "$live"; then
    echo "ERROR: failed to move dist.next → dist; restoring prior tree if present" >&2
    if [[ -e "$old" ]]; then
      mv "$old" "$live" || true
    fi
    rm -rf "$next"
    return 1
  fi
  rm -rf "$old"

  MD_FE_PUBLISH_FAIL_STAGE="frontend_provenance"
  if ! deploy_guard_assert_frontend_provenance "$live" "$commit"; then
    return 1
  fi

  MD_FE_PUBLISH_FAIL_STAGE="frontend_identity"
  if ! md_stamp_frontend_identity "$live" "$commit" "$release"; then
    return 1
  fi

  # Align build-info frontend_commit to tip after successful stamp (full/frontend).
  if [[ -f "$project_root/.build-info.json" ]]; then
    python3 - "$project_root/.build-info.json" "$commit" <<'PY'
import json, sys
path, commit = sys.argv[1], sys.argv[2]
data = json.load(open(path, encoding="utf-8"))
data["frontend_commit"] = commit
open(path, "w", encoding="utf-8").write(json.dumps(data, indent=2) + "\n")
print(f"OK: build-info frontend_commit → {commit}")
PY
  fi

  MD_FE_PUBLISH_FAIL_STAGE=""
  echo "OK: frontend published + stamped → $live"
  return 0
}

# Phase 2 D — backend mode: preserve live FE bytes; rewrite frontend_commit from identity.
# Must not build, publish, or stamp tip onto FE identity/provenance.
md_preserve_backend_frontend_identity() {
  local project_root="$1"
  local backend_tip_commit="$2"
  local dist="$project_root/dashboard/dist"
  local ident="$dist/.deploy-identity.json"
  local prov="$dist/.frontend-provenance.json"
  local build_file="$project_root/.build-info.json"

  [[ -f "$ident" ]] || {
    echo "ERROR: missing preserved FE identity $ident" >&2
    return 1
  }
  [[ -f "$prov" ]] || {
    echo "ERROR: missing preserved FE provenance $prov" >&2
    return 1
  }

  local fe_commit
  fe_commit="$(python3 -c "import json; print(json.load(open('$ident')).get('git_commit') or '')" 2>/dev/null || echo "")"
  [[ -n "$fe_commit" ]] || {
    echo "ERROR: preserved FE identity missing git_commit" >&2
    return 1
  }

  # Self-check Part 3 against preserved identity commit (not backend tip).
  # shellcheck source=deploy/lib/deploy_guard.sh
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy_guard.sh"
  if ! deploy_guard_assert_frontend_provenance "$dist" "$fe_commit"; then
    echo "ERROR: preserved FE provenance invalid" >&2
    return 1
  fi

  local tree_id tree_prov
  tree_id="$(python3 -c "import json; print(json.load(open('$ident')).get('provenance_tree_sha256') or '')" 2>/dev/null || echo "")"
  tree_prov="$(python3 -c "import json; print(json.load(open('$prov')).get('tree_sha256') or '')" 2>/dev/null || echo "")"
  if [[ -z "$tree_id" || "$tree_id" != "$tree_prov" ]]; then
    echo "ERROR: preserved identity tree ($tree_id) != provenance tree ($tree_prov)" >&2
    return 1
  fi

  [[ -f "$build_file" ]] || {
    echo "ERROR: missing $build_file for frontend_commit rewrite" >&2
    return 1
  }

  python3 - "$build_file" "$fe_commit" "$backend_tip_commit" <<'PY'
import json, sys
path, fe_commit, tip = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(path, encoding="utf-8"))
data["frontend_commit"] = fe_commit
# Keep tip identity for backend fields; do not stamp tip onto FE identity files.
data["backend_commit"] = tip
data["git_commit"] = tip
short = tip[:7] if len(tip) >= 7 else tip
data["git_commit_short"] = short
open(path, "w", encoding="utf-8").write(json.dumps(data, indent=2) + "\n")
print(f"OK: backend mode frontend_commit preserved → {fe_commit} (backend tip {tip})")
PY
  return 0
}

md_deploy_strip_no_backup_args() {
  MD_DEPLOY_FORWARD_ARGS=()
  local a
  for a in "$@"; do
    if [[ "$a" == "--no-backup-db" ]]; then
      echo "ERROR: --no-backup-db is forbidden on release deploy (backup is mandatory)" >&2
      return 1
    fi
    [[ -n "$a" ]] || continue
    MD_DEPLOY_FORWARD_ARGS+=("$a")
  done
}

md_deploy_mandatory_backup() {
  echo "[deploy 2/13] BACKUP (mandatory)"
  PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT" \
    MD_SKIP_CLI=1 \
    bash "$MD_DEPLOY_SCRIPT_DIR/manage_deploy.sh" --action backup-postgres --yes \
    || return 1
  export MD_BACKUP_COMPLETED=1
  md_deploy_capture_backup_path
  echo "[deploy 2/13] BACKUP OK (${MD_REPORT_BACKUP_PATH:-})"
}

md_deploy_restart_hard() {
  echo "[deploy 8/13] RESTART"
  local attempt=1
  local max_attempts=3
  local ok=0
  while [[ "$attempt" -le "$max_attempts" ]]; do
    echo "[deploy] restart attempt $attempt/$max_attempts"
    if MD_SKIP_CLI=1 PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT" \
         bash "$MD_DEPLOY_PROJECT_ROOT/deploy/manage_deploy.sh" --action restart --module backend --yes \
      || MD_SKIP_CLI=1 PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT" \
           bash "$MD_DEPLOY_SCRIPT_DIR/manage_deploy.sh" --action restart --module backend --yes; then
      ok=1
      break
    fi
    attempt=$((attempt + 1))
    sleep 2
  done
  if [[ "$ok" -ne 1 ]]; then
    MD_REPORT_RESTART_RESULT="fail"
    return 1
  fi
  MD_REPORT_RESTART_RESULT="ok"
  echo "[deploy 8/13] RESTART OK"
  return 0
}

md_deploy_health_hard() {
  echo "[deploy 9/13] HEALTH"
  local ready=0
  local i
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if curl -sf --max-time 2 "http://127.0.0.1:8000/api/health" -o /dev/null; then
      ready=1
      break
    fi
    sleep 1
  done
  if [[ "$ready" -ne 1 ]]; then
    MD_REPORT_HEALTH_RESULT="fail"
    return 1
  fi
  if ! MD_SKIP_CLI=1 PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT" \
       bash "$MD_DEPLOY_SCRIPT_DIR/manage_deploy.sh" --action status >/dev/null 2>&1; then
    # status may print DOWN for non-critical deps; require HTTP health as gate.
    :
  fi
  MD_REPORT_HEALTH_RESULT="ok"
  echo "[deploy 9/13] HEALTH OK"
  return 0
}

# md_deploy_from_main [mode] — mode: full|backend|frontend (default full)
md_deploy_from_main() {
  local mode="${1:-full}"
  shift || true
  md_deploy_source_init
  trap md_deploy_source_cleanup EXIT

  local repo="$MD_DEPLOY_REPO_ROOT"
  local commit

  # --- 1/13 PREFLIGHT ---
  echo "[deploy 1/13] PREFLIGHT"
  if [[ "$(id -u)" -ne 0 && "${DEPLOY_SKIP_ROOT_CHECK:-0}" != "1" ]]; then
    md_deploy_fail preflight "run with sudo for systemd/nginx deploy to $MD_DEPLOY_PROJECT_ROOT" || return 1
  fi

  deploy_guard_reject_legacy_bypasses || { md_deploy_fail preflight "legacy bypass refused" || return 1; }
  md_deploy_strip_no_backup_args "$@" || { md_deploy_fail preflight "--no-backup-db refused" || return 1; }

  deploy_guard_assert_not_detached "$repo" || { md_deploy_fail preflight "detached HEAD" || return 1; }
  deploy_guard_assert_on_main_branch "$repo" || { md_deploy_fail preflight "not on main" || return 1; }
  deploy_guard_assert_clean_worktree "$repo" "operator checkout" || { md_deploy_fail preflight "dirty working tree" || return 1; }
  deploy_guard_fetch_origin "$repo"

  if deploy_guard_emergency_enabled; then
    deploy_guard_require_emergency "emergency deploy commit selection" || { md_deploy_fail preflight "emergency not confirmed" || return 1; }
    commit="$(deploy_guard_resolve_commit "$repo" "${DEPLOY_COMMIT:-}")"
    echo "WARN: emergency — deploying commit $commit (may not equal origin/main tip)" >&2
  else
    commit="$(deploy_guard_resolve_commit "$repo" "${DEPLOY_COMMIT:-}")"
    deploy_guard_assert_commit_on_main "$repo" "$commit" || { md_deploy_fail preflight "commit not on main" || return 1; }
    if [[ -z "${DEPLOY_COMMIT:-}" ]]; then
      deploy_guard_assert_local_main_matches_origin "$repo" || { md_deploy_fail preflight "local main != origin/main" || return 1; }
    fi
  fi

  # Release identity from tip APP_RELEASE (resolved during build from worktree).
  local tip_release=""

  MD_REPORT_DEPLOYED_COMMIT="$commit"
  MD_REPORT_DEPLOYED_COMMIT_SHORT="$(git -C "$repo" rev-parse --short "$commit" 2>/dev/null || echo "${commit:0:7}")"
  MD_REPORT_ORIGIN_MAIN_COMMIT="$commit"
  md_deploy_read_previous_identity
  echo "[deploy 1/13] PREFLIGHT OK (commit=$commit)"

  # --- 2/13 BACKUP ---
  md_deploy_mandatory_backup || { md_deploy_fail backup "mandatory backup failed" || return 1; }

  # --- 3/13 MIGRATION DECISION ---
  echo "[deploy 3/13] MIGRATION DECISION"
  if ! md_migration_decision "$repo" "$commit" "$MD_DEPLOY_PROJECT_ROOT"; then
    md_deploy_fail migration_decision "${MD_MIGRATION_DECISION_DETAIL:-ambiguous or unreachable}" || return 1
  fi
  MD_REPORT_MIGRATION_DECISION="$MD_MIGRATION_DECISION"
  echo "[deploy 3/13] MIGRATION DECISION OK ($MD_MIGRATION_DECISION)"

  # --- 4/13 CONDITIONAL SCHEMA-FIRST ---
  echo "[deploy 4/13] SCHEMA-FIRST"
  if [[ "$MD_MIGRATION_DECISION" == "schema_first" ]]; then
    echo "[deploy] schema-first required — running migrate release --yes (non-interactive)"
    # Must use the canonical CLI path (positional "migrate release").
    # MD_SKIP_CLI=1 forces legacy --mode/--action parsing, which rejects "migrate"
    # as an unknown option and breaks schema-first (see deploy report 20260801_175059).
    if ! MD_SKIP_CLI=0 PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT" \
         bash "$MD_DEPLOY_SCRIPT_DIR/manage_deploy.sh" migrate release --yes; then
      MD_REPORT_MIGRATION_SCHEMA_FIRST="failed"
      md_deploy_fail schema_first "migrate release failed" || return 1
    fi
    MD_REPORT_MIGRATION_SCHEMA_FIRST="executed"
    echo "[deploy 4/13] SCHEMA-FIRST OK (executed)"
  else
    MD_REPORT_MIGRATION_SCHEMA_FIRST="skipped"
    echo "[deploy 4/13] SCHEMA-FIRST skipped (post_sync_only)"
  fi

  # --- 5/13 BUILD ---
  echo "[deploy 5/13] BUILD (worktree + provenance)"
  MD_DEPLOY_WORKTREE="$(mktemp -d /tmp/ai-site-agent-deploy-XXXXXX)"
  echo "[deploy] clean worktree: $MD_DEPLOY_WORKTREE"
  git -C "$repo" worktree add --detach "$MD_DEPLOY_WORKTREE" "$commit" >/dev/null
  deploy_guard_assert_clean_worktree "$MD_DEPLOY_WORKTREE" "deploy worktree" \
    || { md_deploy_fail build "dirty deploy worktree" || return 1; }

  if [[ -z "$tip_release" ]]; then
    tip_release="$(deploy_guard_read_app_release "$MD_DEPLOY_WORKTREE" || true)"
  fi
  if [[ -z "$tip_release" ]]; then
    md_deploy_fail build "cannot read tip APP_RELEASE" || return 1
  fi
  MD_DEPLOY_RELEASE="$tip_release"
  MD_REPORT_DEPLOYED_RELEASE="$tip_release"
  export MD_DEPLOY_RELEASE
  if [[ -n "${MD_DEPLOY_CONFIGURED_RELEASE}" && "$MD_DEPLOY_CONFIGURED_RELEASE" != "$tip_release" ]]; then
    echo "WARN: configured RELEASE_VERSION=$MD_DEPLOY_CONFIGURED_RELEASE differs from tip APP_RELEASE=$tip_release — ignoring configured value for release identity" >&2
  fi

  RELEASE_VERSION="$MD_DEPLOY_RELEASE" ROOT="$MD_DEPLOY_WORKTREE" \
    EXPECTED_COMMIT="$commit" \
    bash "$MD_DEPLOY_WORKTREE/scripts/release/write-build-info.sh" \
    || { md_deploy_fail build "write-build-info failed" || return 1; }
  deploy_guard_assert_build_info_matches_commit "$MD_DEPLOY_WORKTREE" "$commit" \
    || { md_deploy_fail build "build-info commit mismatch" || return 1; }
  deploy_guard_assert_release_identity "$MD_DEPLOY_WORKTREE" "$commit" "$MD_DEPLOY_RELEASE" \
    || { md_deploy_fail build "release identity mismatch" || return 1; }

  if [[ "$mode" == "full" || "$mode" == "frontend" ]]; then
    echo "[deploy] building dashboard"
    md_augment_path_for_node
    local npm
    npm="$(md_npm_cmd)" || { md_deploy_fail build "npm not found" || return 1; }
    command -v node &>/dev/null || { md_deploy_fail build "node not on PATH" || return 1; }
    cd "$MD_DEPLOY_WORKTREE/dashboard"
    if [[ ! -d node_modules ]]; then "$npm" ci --silent; else "$npm" install --silent; fi
    "$npm" run build || { md_deploy_fail build "frontend build failed" || return 1; }
    [[ -f "$MD_DEPLOY_WORKTREE/dashboard/dist/index.html" ]] \
      || { md_deploy_fail build "frontend build missing index.html" || return 1; }
    # Identity is stamped only after live provenance PASS (amendment Part 8).
    md_write_frontend_provenance \
      "$MD_DEPLOY_WORKTREE/dashboard/dist" "$commit" "$MD_DEPLOY_RELEASE" \
      || { md_deploy_fail build "frontend provenance write failed" || return 1; }
  fi
  echo "[deploy 5/13] BUILD OK"

  # --- 6/13 SYNC (no post-sync migrate — separate stage below) ---
  echo "[deploy 6/13] SYNC to $MD_DEPLOY_PROJECT_ROOT"
  md_deploy_mark_sync_started
  export PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT"
  export DEV_CHECKOUT="$MD_DEPLOY_WORKTREE"
  unset ALLOW_DIRTY_SYNC || true
  export NPM_BIN NODE_BIN APP_USER APP_GROUP PATH
  export MD_SKIP_CLI=1
  export MD_DEPLOY_COMMIT="$commit"
  export MD_RELEASE_DEPLOY=1
  export MD_BACKUP_COMPLETED=1
  export DO_BACKUP_DB=yes
  export MD_SKIP_RUN_MIGRATIONS=1

  local legacy_mode="full"
  [[ "$mode" == "backend" ]] && legacy_mode="backend"
  [[ "$mode" == "frontend" ]] && legacy_mode="frontend"

  local -a deploy_cmd=(
    bash "$MD_DEPLOY_SCRIPT_DIR/manage_deploy.sh"
    --mode "$legacy_mode"
    --sync-from-dev
    --no-git-pull
    --backup-db
    --yes
  )
  if ((${#MD_DEPLOY_FORWARD_ARGS[@]})); then
    deploy_cmd+=("${MD_DEPLOY_FORWARD_ARGS[@]}")
  fi

  if ! "${deploy_cmd[@]}"; then
    unset MD_SKIP_RUN_MIGRATIONS || true
    md_deploy_fail sync "sync to /opt failed" || return 1
  fi
  unset MD_SKIP_RUN_MIGRATIONS || true
  echo "[deploy 6/13] SYNC OK"

  deploy_guard_assert_build_info_matches_commit "$MD_DEPLOY_PROJECT_ROOT" "$commit" \
    || { md_deploy_fail sync "synced build-info mismatch" || return 1; }
  deploy_guard_assert_release_identity "$MD_DEPLOY_PROJECT_ROOT" "$commit" "$MD_DEPLOY_RELEASE" \
    || { md_deploy_fail sync "synced release identity mismatch" || return 1; }

  # --- 6b FE PUBLISH (amendment Part 1 / Part 8) — after source sync, before migrate ---
  if [[ "$mode" == "full" || "$mode" == "frontend" ]]; then
    echo "[deploy 6b] FRONTEND PUBLISH (dist.next → atomic swap → stamp)"
    if ! md_publish_frontend_artifact \
         "$MD_DEPLOY_WORKTREE" "$MD_DEPLOY_PROJECT_ROOT" "$commit" "$MD_DEPLOY_RELEASE"; then
      md_deploy_fail "${MD_FE_PUBLISH_FAIL_STAGE:-frontend_publish}" \
        "frontend publication failed" || return 1
    fi
    deploy_guard_assert_frontend_identity "$MD_DEPLOY_PROJECT_ROOT" "$commit" \
      || { md_deploy_fail frontend_identity "live frontend identity mismatch" || return 1; }
    md_reload_nginx_after_publish \
      || { md_deploy_fail frontend_publish "nginx reload after FE publish failed" || return 1; }
    echo "[deploy 6b] FRONTEND PUBLISH OK"
  elif [[ "$mode" == "backend" ]]; then
    echo "[deploy 6b] BACKEND MODE — preserve live FE identity (no publish)"
    if ! md_preserve_backend_frontend_identity "$MD_DEPLOY_PROJECT_ROOT" "$commit"; then
      md_deploy_fail frontend_identity \
        "backend mode FE identity preservation failed" || return 1
    fi
    echo "[deploy 6b] BACKEND FE PRESERVE OK"
  fi

  # --- 7/13 POST-SYNC MIGRATE (mandatory; distinct failed_stage) ---
  echo "[deploy 7/13] POST-SYNC MIGRATE"
  local migrate_script="$MD_DEPLOY_PROJECT_ROOT/deploy/manage_deploy.sh"
  [[ -f "$migrate_script" ]] || migrate_script="$MD_DEPLOY_SCRIPT_DIR/manage_deploy.sh"
  if ! MD_SKIP_CLI=1 PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT" \
       bash "$migrate_script" --action run-migrations; then
    MD_REPORT_MIGRATION_POST_SYNC="failed"
    md_deploy_fail post_sync_migrate "post-sync alembic upgrade failed" || return 1
  fi
  MD_REPORT_MIGRATION_POST_SYNC="ok"
  echo "[deploy 7/13] POST-SYNC MIGRATE OK"

  # --- 8/13 RESTART ---
  md_deploy_restart_hard || { md_deploy_fail restart "backend restart failed after retries" || return 1; }

  # --- 9/13 HEALTH ---
  md_deploy_health_hard || { md_deploy_fail health "health check failed" || return 1; }

  # --- 10/13 VERIFY RELEASE ---
  echo "[deploy 10/13] VERIFY RELEASE"
  if ! md_verify_release_run "$repo" "$MD_DEPLOY_PROJECT_ROOT" "$commit" "$MD_DEPLOY_RELEASE" "$mode"; then
    MD_REPORT_VERIFY_RESULT="fail"
    md_deploy_fail verify_release "verify-release critical failures" || return 1
  fi
  MD_REPORT_VERIFY_RESULT="pass"
  echo "[deploy 10/13] VERIFY RELEASE OK"

  # --- 11/13 SMOKE ---
  echo "[deploy 11/13] SMOKE"
  if ! bash "$MD_DEPLOY_REPO_ROOT/scripts/release/smoke-staging.sh"; then
    MD_REPORT_SMOKE_RESULT="fail"
    md_deploy_fail smoke "smoke suite failed" || return 1
  fi
  MD_REPORT_SMOKE_RESULT="pass"
  echo "[deploy 11/13] SMOKE OK"

  # --- 12/13 REPORT ---
  echo "[deploy 12/13] WRITE FINAL REPORT"
  MD_REPORT_OUTCOME="success"
  MD_REPORT_PARTIAL_DEPLOY="false"
  MD_REPORT_DURATION_SECONDS="$(md_deploy_duration)"
  MD_REPORT_FAILED_STAGE=""
  MD_REPORT_FAILED_STAGE_DETAIL=""
  if ! md_write_deploy_report "$MD_DEPLOY_PROJECT_ROOT"; then
    md_deploy_fail report "cannot write deployment report to deployments/" || return 1
  fi
  echo "[deploy 12/13] REPORT OK (${MD_REPORT_MANIFEST_PATH})"

  # --- 13/13 SUCCESS ---
  echo "[deploy 13/13] SUCCESS"
  md_deploy_success_summary
  return 0
}
