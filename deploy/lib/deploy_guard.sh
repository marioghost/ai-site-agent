#!/usr/bin/env bash
# Shared deployment guard helpers — sourced by manage_deploy.sh and deploy_from_main.sh.
# Refuses release deploy from dirty trees or commits not on origin/main.
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
