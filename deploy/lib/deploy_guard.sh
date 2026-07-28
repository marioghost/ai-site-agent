#!/usr/bin/env bash
# Shared deployment guard helpers — sourced by manage_deploy.sh and deploy libs.
# Normal release deploy: origin/main only, clean trees, matching build identity.
# Emergency bypass requires explicit EMERGENCY_DEPLOY_* (never for routine deploys).
set -euo pipefail

deploy_guard_repo_root() {
  local start="${1:-$(pwd)}"
  git -C "$start" rev-parse --show-toplevel 2>/dev/null
}

deploy_guard_is_clean_worktree() {
  local repo="$1"
  if [[ -z "$(git -C "$repo" status --porcelain 2>/dev/null)" ]]; then
    return 0
  fi
  return 1
}

deploy_guard_assert_clean_worktree() {
  local repo="$1"
  local label="${2:-$repo}"
  if deploy_guard_is_clean_worktree "$repo"; then
    return 0
  fi
  echo "ERROR: dirty working tree at $label — release deploy refused" >&2
  git -C "$repo" status --short >&2 || true
  return 1
}

deploy_guard_fetch_origin() {
  local repo="$1"
  git -C "$repo" fetch origin --prune
}

deploy_guard_local_main_hash() {
  local repo="$1"
  git -C "$repo" rev-parse main 2>/dev/null
}

deploy_guard_origin_main_hash() {
  local repo="$1"
  git -C "$repo" rev-parse origin/main 2>/dev/null
}

deploy_guard_assert_local_main_matches_origin() {
  local repo="$1"
  deploy_guard_fetch_origin "$repo"
  local local_main origin_main
  local_main="$(deploy_guard_local_main_hash "$repo")"
  origin_main="$(deploy_guard_origin_main_hash "$repo")"
  if [[ "$local_main" == "$origin_main" ]]; then
    return 0
  fi
  echo "ERROR: local main ($local_main) != origin/main ($origin_main)" >&2
  echo "ERROR: push or merge before release deploy" >&2
  return 1
}

deploy_guard_assert_commit_on_main() {
  local repo="$1"
  local commit="$2"
  deploy_guard_fetch_origin "$repo"
  if git -C "$repo" merge-base --is-ancestor "$commit" origin/main 2>/dev/null; then
    return 0
  fi
  echo "ERROR: commit $commit is not an ancestor of origin/main" >&2
  return 1
}

deploy_guard_assert_on_main_branch() {
  local repo="$1"
  local branch
  branch="$(git -C "$repo" symbolic-ref -q HEAD 2>/dev/null || true)"
  if [[ "$branch" == "refs/heads/main" ]]; then
    return 0
  fi
  echo "ERROR: not on main branch (HEAD=${branch:-detached})" >&2
  return 1
}

deploy_guard_assert_not_detached() {
  local repo="$1"
  if git -C "$repo" symbolic-ref -q HEAD >/dev/null 2>&1; then
    return 0
  fi
  echo "ERROR: detached HEAD — checkout main before deploy operations" >&2
  return 1
}

deploy_guard_resolve_commit() {
  local repo="$1"
  local requested="${2:-}"
  if [[ -n "$requested" ]]; then
    git -C "$repo" rev-parse "$requested"
    return 0
  fi
  deploy_guard_fetch_origin "$repo"
  git -C "$repo" rev-parse origin/main
}

# Emergency operator mode — NEVER for routine deploys.
# Requires:
#   EMERGENCY_DEPLOY_I_UNDERSTAND=YES
#   EMERGENCY_DEPLOY_REASON="<non-empty reason>"
# Interactive: typed phrase DEPLOY-OUTSIDE-ORIGIN-MAIN
# Non-interactive: EMERGENCY_DEPLOY_CONFIRM=DEPLOY-OUTSIDE-ORIGIN-MAIN
deploy_guard_emergency_enabled() {
  [[ "${EMERGENCY_DEPLOY_I_UNDERSTAND:-}" == "YES" ]] || return 1
  [[ -n "${EMERGENCY_DEPLOY_REASON:-}" ]] || return 1
  return 0
}

deploy_guard_require_emergency() {
  local purpose="${1:-unsafe deploy}"
  if ! deploy_guard_emergency_enabled; then
    echo "ERROR: $purpose refused." >&2
    echo "ERROR: Normal deploys must use: manage_deploy.sh deploy full (origin/main only)." >&2
    echo "ERROR: Emergency mode requires:" >&2
    echo "  EMERGENCY_DEPLOY_I_UNDERSTAND=YES" >&2
    echo "  EMERGENCY_DEPLOY_REASON='…'" >&2
    echo "  and typed/env confirm: DEPLOY-OUTSIDE-ORIGIN-MAIN" >&2
    return 1
  fi
  local expected="DEPLOY-OUTSIDE-ORIGIN-MAIN"
  local typed="${EMERGENCY_DEPLOY_CONFIRM:-}"
  if [[ -z "$typed" ]]; then
    if [[ -t 0 ]]; then
      read -r -p "Type $expected to confirm emergency $purpose: " typed
    else
      echo "ERROR: set EMERGENCY_DEPLOY_CONFIRM=$expected for non-interactive emergency" >&2
      return 1
    fi
  fi
  if [[ "$typed" != "$expected" ]]; then
    echo "ERROR: emergency confirmation mismatch" >&2
    return 1
  fi
  echo "WARN: EMERGENCY DEPLOY ACTIVE — $purpose" >&2
  echo "WARN: reason: ${EMERGENCY_DEPLOY_REASON}" >&2
  echo "WARN: This bypasses origin/main safety. Audit required after." >&2
  return 0
}

# Reject legacy bypass env vars unless emergency mode is active.
deploy_guard_reject_legacy_bypasses() {
  if [[ "${ALLOW_DIRTY_SYNC:-0}" == "1" ]]; then
    if deploy_guard_emergency_enabled; then
      deploy_guard_require_emergency "ALLOW_DIRTY_SYNC" || return 1
      return 0
    fi
    echo "ERROR: ALLOW_DIRTY_SYNC is removed for normal deploys." >&2
    echo "ERROR: Use: manage_deploy.sh deploy full" >&2
    echo "ERROR: Emergency only: EMERGENCY_DEPLOY_I_UNDERSTAND=YES + reason + confirm." >&2
    return 1
  fi
  if [[ "${DEPLOY_LOCAL_MAIN:-0}" == "1" ]]; then
    if deploy_guard_emergency_enabled; then
      deploy_guard_require_emergency "DEPLOY_LOCAL_MAIN" || return 1
      return 0
    fi
    echo "ERROR: DEPLOY_LOCAL_MAIN is removed for normal deploys." >&2
    echo "ERROR: Push origin/main, then: manage_deploy.sh deploy full" >&2
    return 1
  fi
  return 0
}

deploy_guard_read_build_commit() {
  local root="$1"
  local path="$root/.build-info.json"
  if [[ ! -f "$path" ]]; then
    echo ""
    return 1
  fi
  python3 -c "import json; print(json.load(open('$path')).get('git_commit',''))" 2>/dev/null || echo ""
}

deploy_guard_assert_build_info_matches_commit() {
  local root="$1"
  local expected="$2"
  local actual
  actual="$(deploy_guard_read_build_commit "$root" || true)"
  if [[ -z "$actual" ]]; then
    echo "ERROR: missing or unreadable .build-info.json under $root" >&2
    return 1
  fi
  if [[ "$actual" != "$expected" ]]; then
    echo "ERROR: build-info commit ($actual) != expected ($expected)" >&2
    return 1
  fi
  return 0
}

deploy_guard_assert_frontend_identity() {
  local root="$1"
  local expected="$2"
  local path="$root/dashboard/dist/.deploy-identity.json"
  if [[ ! -f "$path" ]]; then
    echo "ERROR: missing frontend identity $path" >&2
    return 1
  fi
  local fe
  fe="$(python3 -c "import json; print(json.load(open('$path')).get('git_commit',''))" 2>/dev/null || echo "")"
  if [[ "$fe" != "$expected" ]]; then
    echo "ERROR: frontend identity ($fe) != expected ($expected)" >&2
    return 1
  fi
  return 0
}
