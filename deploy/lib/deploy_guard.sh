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

# Single provenance verifier entrypoint (amendment Part 3).
deploy_guard_assert_frontend_provenance() {
  local dist_root="$1"
  local expected_commit="${2:-}"
  local script
  script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/frontend_provenance.py"
  if [[ ! -f "$script" ]]; then
    echo "ERROR: missing $script" >&2
    return 1
  fi
  if [[ -n "$expected_commit" ]]; then
    python3 "$script" verify --dist "$dist_root" --expected-commit "$expected_commit"
  else
    python3 "$script" verify --dist "$dist_root"
  fi
}

deploy_guard_assert_frontend_identity() {
  local root="$1"
  local expected="$2"
  local dist="$root/dashboard/dist"
  local path="$dist/.deploy-identity.json"
  if [[ ! -f "$path" ]]; then
    echo "ERROR: missing frontend identity $path" >&2
    return 1
  fi
  # Identity is only valid with matching live provenance (I1/I11).
  deploy_guard_assert_frontend_provenance "$dist" "$expected" || return 1
  local fe tree_id tree_prov
  fe="$(python3 -c "import json; print(json.load(open('$path')).get('git_commit',''))" 2>/dev/null || echo "")"
  if [[ "$fe" != "$expected" ]]; then
    echo "ERROR: frontend identity ($fe) != expected ($expected)" >&2
    return 1
  fi
  tree_id="$(python3 -c "import json; print(json.load(open('$path')).get('provenance_tree_sha256',''))" 2>/dev/null || echo "")"
  tree_prov="$(python3 -c "import json; print(json.load(open('$dist/.frontend-provenance.json')).get('tree_sha256',''))" 2>/dev/null || echo "")"
  if [[ -z "$tree_id" || "$tree_id" != "$tree_prov" ]]; then
    echo "ERROR: identity provenance_tree_sha256 ($tree_id) != provenance tree_sha256 ($tree_prov)" >&2
    return 1
  fi
  return 0
}

deploy_guard_read_app_release() {
  local root="$1"
  local py="$root/backend/app/services/build_info_service.py"
  if [[ ! -f "$py" ]]; then
    echo ""
    return 1
  fi
  python3 - "$root" <<'PY'
import re
import sys
from pathlib import Path
root = sys.argv[1]
text = Path(root, "backend/app/services/build_info_service.py").read_text(encoding="utf-8")
m = re.search(r'APP_RELEASE\s*=\s*["\']([^"\']+)["\']', text)
print(m.group(1) if m else "")
PY
}

deploy_guard_read_build_release() {
  local root="$1"
  local path="$root/.build-info.json"
  if [[ ! -f "$path" ]]; then
    echo ""
    return 1
  fi
  python3 -c "import json; print(json.load(open('$path')).get('release',''))" 2>/dev/null || echo ""
}

# Validate release identity: APP_RELEASE == build-info.release == RELEASE_VERSION.
# If an exact annotated/lightweight tag exists on the commit (vX.Y or release-X.Y), it must match.
deploy_guard_assert_release_identity() {
  local root="$1"
  local commit="$2"
  local expected_release="${3:-}"
  local app_rel build_rel tag_rel
  app_rel="$(deploy_guard_read_app_release "$root" || true)"
  build_rel="$(deploy_guard_read_build_release "$root" || true)"
  if [[ -z "$app_rel" ]]; then
    echo "ERROR: cannot read APP_RELEASE from $root" >&2
    return 1
  fi
  if [[ -z "$build_rel" ]]; then
    echo "ERROR: cannot read release from .build-info.json under $root" >&2
    return 1
  fi
  if [[ -n "$expected_release" && "$app_rel" != "$expected_release" ]]; then
    echo "ERROR: APP_RELEASE ($app_rel) != RELEASE_VERSION ($expected_release)" >&2
    return 1
  fi
  if [[ "$app_rel" != "$build_rel" ]]; then
    echo "ERROR: APP_RELEASE ($app_rel) != build-info.release ($build_rel)" >&2
    return 1
  fi
  tag_rel=""
  if git -C "$root" describe --tags --exact-match "$commit" >/dev/null 2>&1; then
    local raw
    raw="$(git -C "$root" describe --tags --exact-match "$commit" 2>/dev/null || true)"
    # Accept v0.7 / release-0.7 / 0.7
    tag_rel="$(echo "$raw" | sed -E 's/^(v|release-)//')"
    if [[ -n "$tag_rel" && "$tag_rel" != "$app_rel" ]]; then
      echo "ERROR: git tag '$raw' (normalized $tag_rel) != APP_RELEASE ($app_rel)" >&2
      return 1
    fi
    echo "OK: release identity tag=$raw APP_RELEASE=$app_rel build-info=$build_rel"
  else
    echo "OK: release identity APP_RELEASE=$app_rel build-info=$build_rel (no exact tag on commit)"
  fi
  return 0
}
