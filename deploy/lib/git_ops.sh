#!/usr/bin/env bash
# Git release policy helpers — main-only deploy, merge, push.
set -euo pipefail

# shellcheck source=deploy/lib/deploy_guard.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy_guard.sh"

md_git_repo_root() {
  local start="${1:-.}"
  deploy_guard_repo_root "$start"
}

md_git_current_branch() {
  local repo="$1"
  git -C "$repo" symbolic-ref -q HEAD 2>/dev/null | sed 's|^refs/heads/||' || echo "DETACHED"
}

md_git_print_status() {
  local repo="${1:-.}"
  deploy_guard_fetch_origin "$repo"
  local branch local_main origin_main head
  branch="$(md_git_current_branch "$repo")"
  head="$(git -C "$repo" rev-parse HEAD)"
  local_main="$(deploy_guard_local_main_hash "$repo" 2>/dev/null || echo "?")"
  origin_main="$(deploy_guard_origin_main_hash "$repo" 2>/dev/null || echo "?")"
  echo "branch:        $branch"
  echo "HEAD:          $head"
  echo "local main:    $local_main"
  echo "origin/main:   $origin_main"
  if [[ "$local_main" != "?" && "$origin_main" != "?" ]]; then
    git -C "$repo" log --oneline "$origin_main..$local_main" 2>/dev/null | sed 's/^/  ahead: /' || true
    git -C "$repo" log --oneline "$local_main..$origin_main" 2>/dev/null | sed 's/^/  behind: /' || true
  fi
  echo "working tree:"
  git -C "$repo" status --short | sed 's/^/  /' || true
}

md_git_assert_on_main_branch() {
  local repo="$1"
  deploy_guard_assert_on_main_branch "$repo"
}

md_git_assert_clean() {
  local repo="$1"
  deploy_guard_assert_clean_worktree "$repo" "repository"
}

md_git_assert_deploy_ready() {
  local repo="$1"
  deploy_guard_fetch_origin "$repo"
  md_git_assert_on_main_branch "$repo" || return 1
  md_git_assert_clean "$repo" || return 1
  local local_main origin_main
  local_main="$(deploy_guard_local_main_hash "$repo")"
  origin_main="$(deploy_guard_origin_main_hash "$repo")"
  if [[ "$local_main" != "$origin_main" ]]; then
    echo "ERROR: local main ($local_main) != origin/main ($origin_main)" >&2
    echo "ERROR: push origin/main before deploy (manage_deploy.sh release push)" >&2
    return 1
  fi
  deploy_guard_assert_commit_on_main "$repo" "$local_main"
}

md_git_branch_unique_commits() {
  local repo="$1"
  local branch="$2"
  git -C "$repo" log --oneline "main..$branch" 2>/dev/null || true
}

md_git_branch_changed_files() {
  local repo="$1"
  local branch="$2"
  git -C "$repo" diff --name-status "main...$branch" 2>/dev/null || true
}

md_git_prepare_branch_review() {
  local repo="$1"
  local branch="${2:-$(md_git_current_branch "$repo")}"
  if [[ "$branch" == "main" || "$branch" == "DETACHED" ]]; then
    echo "On main or detached — nothing to merge."
    md_git_print_status "$repo"
    return 0
  fi
  echo "=== Branch review: $branch ==="
  md_git_print_status "$repo"
  echo ""
  echo "Commits on $branch not in main:"
  md_git_branch_unique_commits "$repo" "$branch" | sed 's/^/  /'
  echo ""
  echo "Changed files (main...$branch):"
  md_git_branch_changed_files "$repo" "$branch" | sed 's/^/  /'
  echo ""
  if git -C "$repo" diff --name-only "main...$branch" | grep -q 'migrations/versions/'; then
    echo "NOTICE: branch contains Alembic migrations"
  fi
  if git -C "$repo" diff --name-only "main...$branch" | grep -qiE 'feature_flag|WIP|FIXME'; then
    echo "NOTICE: branch may contain flags or WIP markers — review diff"
  fi
}

md_git_merge_branch_to_main() {
  local repo="$1"
  local branch="$2"
  md_git_prepare_branch_review "$repo" "$branch"
  if [[ "$branch" == "main" || "$branch" == "DETACHED" ]]; then
    return 0
  fi
  if ! deploy_guard_is_clean_worktree "$repo"; then
    echo "ERROR: unclean working tree — commit or stash before merge" >&2
    return 1
  fi
  # shellcheck source=deploy/lib/confirmation.sh
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/confirmation.sh"
  md_confirm "Merge branch '$branch' into main?" "n" || { echo "Aborted."; return 1; }
  git -C "$repo" checkout main
  deploy_guard_fetch_origin "$repo"
  git -C "$repo" merge --no-ff "$branch" -m "merge($branch): operator-approved merge into main"
  echo "OK: merged $branch into main"
  echo "Next: run release-check, then: manage_deploy.sh release push"
}

md_git_push_main() {
  local repo="$1"
  # shellcheck source=deploy/lib/confirmation.sh
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/confirmation.sh"
  deploy_guard_fetch_origin "$repo"
  md_git_assert_on_main_branch "$repo" || return 1
  md_git_assert_clean "$repo" || return 1
  local local_main origin_main
  local_main="$(deploy_guard_local_main_hash "$repo")"
  origin_main="$(deploy_guard_origin_main_hash "$repo")"
  if git -C "$repo" merge-base --is-ancestor "$origin_main" "$local_main" 2>/dev/null; then
    :
  else
    echo "ERROR: origin/main has commits not in local main — fetch and merge first" >&2
    return 1
  fi
  echo "Commits to push (origin/main..main):"
  git -C "$repo" log --oneline "$origin_main..$local_main" | sed 's/^/  /'
  md_confirm "Push main to origin?" "n" || { echo "Aborted."; return 1; }
  git -C "$repo" push origin main
  deploy_guard_fetch_origin "$repo"
  origin_main="$(deploy_guard_origin_main_hash "$repo")"
  if [[ "$local_main" == "$origin_main" ]]; then
    echo "OK: origin/main == local main ($local_main)"
  else
    echo "ERROR: push verification failed" >&2
    return 1
  fi
}
