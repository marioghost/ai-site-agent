#!/usr/bin/env bash
# Regression: release deploy must refuse dirty trees and non-main commits.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GUARD="$ROOT/deploy/lib/deploy_guard.sh"
FROM_MAIN="$ROOT/deploy/deploy_from_main.sh"
MANAGE="$ROOT/deploy/manage_deploy.sh"

if [[ ! -f "$GUARD" ]]; then
  echo "FAIL: missing $GUARD" >&2
  exit 1
fi

# shellcheck source=deploy/lib/deploy_guard.sh
source "$GUARD"

TMP="$(mktemp -d /tmp/deploy-guard-test-XXXXXX)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

git init -q "$TMP/repo"
git -C "$TMP/repo" config user.email "test@example.com"
git -C "$TMP/repo" config user.name "Test"
echo "a" >"$TMP/repo/README"
git -C "$TMP/repo" add README
git -C "$TMP/repo" commit -q -m "init"
git -C "$TMP/repo" checkout -q -b main
git -C "$TMP/repo" branch -M main
echo "b" >>"$TMP/repo/README"
git -C "$TMP/repo" checkout -q -b feature
git -C "$TMP/repo" add README
git -C "$TMP/repo" commit -q -m "feature"

MAIN_HEAD="$(git -C "$TMP/repo" rev-parse main)"
FEATURE_HEAD="$(git -C "$TMP/repo" rev-parse feature)"

if deploy_guard_is_clean_worktree "$TMP/repo"; then
  echo "OK: clean tree detected as clean"
else
  echo "FAIL: clean tree should pass" >&2
  exit 1
fi

echo "dirty" >"$TMP/repo/dirty.txt"
if deploy_guard_is_clean_worktree "$TMP/repo"; then
  echo "FAIL: dirty tree should fail" >&2
  exit 1
fi
echo "OK: dirty tree detected as dirty"
rm -f "$TMP/repo/dirty.txt"

git -C "$TMP/repo" remote add origin "$TMP/repo"
git -C "$TMP/repo" push -q origin main
git -C "$TMP/repo" push -q origin feature

if deploy_guard_assert_commit_on_main "$TMP/repo" "$MAIN_HEAD"; then
  echo "OK: main commit accepted"
else
  echo "FAIL: main commit should be on origin/main" >&2
  exit 1
fi

if deploy_guard_assert_commit_on_main "$TMP/repo" "$FEATURE_HEAD"; then
  echo "FAIL: feature commit must be rejected" >&2
  exit 1
fi
echo "OK: non-main commit rejected"

# manage_deploy must source guard and refuse dirty sync by default.
if ! grep -q 'deploy_guard_assert_clean_worktree' "$MANAGE"; then
  echo "FAIL: manage_deploy.sh must call deploy_guard_assert_clean_worktree" >&2
  exit 1
fi
if ! grep -q 'ALLOW_DIRTY_SYNC' "$MANAGE"; then
  echo "FAIL: manage_deploy.sh must support ALLOW_DIRTY_SYNC override" >&2
  exit 1
fi

if [[ ! -x "$FROM_MAIN" ]] && [[ ! -f "$FROM_MAIN" ]]; then
  echo "FAIL: missing deploy_from_main.sh" >&2
  exit 1
fi
if ! grep -q 'worktree add' "$FROM_MAIN"; then
  echo "FAIL: deploy_from_main.sh must use git worktree" >&2
  exit 1
fi
if ! grep -q 'RELEASE_VERSION=0.7' "$FROM_MAIN"; then
  echo "FAIL: deploy_from_main.sh must set RELEASE_VERSION=0.7" >&2
  exit 1
fi

echo "OK: deploy guard regression tests passed"
