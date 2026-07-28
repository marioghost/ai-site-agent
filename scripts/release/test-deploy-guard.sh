#!/usr/bin/env bash
# Regression: release deploy must refuse dirty trees, non-main commits, and legacy bypasses.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GUARD="$ROOT/deploy/lib/deploy_guard.sh"
FROM_MAIN="$ROOT/deploy/deploy_from_main.sh"
MANAGE="$ROOT/deploy/manage_deploy.sh"
CLI="$ROOT/deploy/lib/cli.sh"
SOURCE="$ROOT/deploy/lib/deploy_source.sh"
VERIFY="$ROOT/scripts/release/verify-release.sh"

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

# Legacy bypasses must fail without emergency mode.
ALLOW_DIRTY_SYNC=1
if deploy_guard_reject_legacy_bypasses 2>/dev/null; then
  echo "FAIL: ALLOW_DIRTY_SYNC should be rejected without emergency" >&2
  exit 1
fi
unset ALLOW_DIRTY_SYNC
echo "OK: ALLOW_DIRTY_SYNC rejected without emergency"

DEPLOY_LOCAL_MAIN=1
if deploy_guard_reject_legacy_bypasses 2>/dev/null; then
  echo "FAIL: DEPLOY_LOCAL_MAIN should be rejected without emergency" >&2
  exit 1
fi
unset DEPLOY_LOCAL_MAIN
echo "OK: DEPLOY_LOCAL_MAIN rejected without emergency"

# manage_deploy must refuse operator sync without MD_RELEASE_DEPLOY.
if ! grep -q 'MD_RELEASE_DEPLOY' "$MANAGE"; then
  echo "FAIL: manage_deploy.sh must gate sync with MD_RELEASE_DEPLOY" >&2
  exit 1
fi
if ! grep -q 'EMERGENCY_DEPLOY' "$GUARD"; then
  echo "FAIL: deploy_guard must define emergency mode" >&2
  exit 1
fi
if [[ ! -f "$CLI" ]] || [[ ! -f "$SOURCE" ]] || [[ ! -f "$VERIFY" ]]; then
  echo "FAIL: missing cli/deploy_source/verify-release" >&2
  exit 1
fi
if ! grep -q 'md_cli_main' "$MANAGE"; then
  echo "FAIL: manage_deploy.sh must dispatch CLI commands" >&2
  exit 1
fi
if [[ ! -f "$FROM_MAIN" ]] || ! grep -q 'manage_deploy.sh deploy full' "$FROM_MAIN"; then
  echo "FAIL: deploy_from_main.sh must wrap manage_deploy deploy full" >&2
  exit 1
fi
if ! grep -q 'EXPECTED_COMMIT' "$ROOT/scripts/release/write-build-info.sh"; then
  echo "FAIL: write-build-info must support EXPECTED_COMMIT" >&2
  exit 1
fi

# --mode update must be hard-refused
if ! grep -q 'Deprecated: --mode update' "$MANAGE"; then
  echo "FAIL: --mode update must be deprecated/refused" >&2
  exit 1
fi

if ! grep -q 'deploy_guard_assert_release_identity' "$GUARD"; then
  echo "FAIL: deploy_guard must validate release identity" >&2
  exit 1
fi
if ! grep -q 'md_deploy_mandatory_backup\|BACKUP (mandatory)' "$SOURCE"; then
  echo "FAIL: deploy_source must run mandatory backup stage" >&2
  exit 1
fi
if ! grep -q 'backup → build → deploy → verify → restart → smoke' "$SOURCE" \
  && ! grep -q 'stages: backup' "$SOURCE"; then
  echo "FAIL: deploy_source must document mandatory stage order" >&2
  exit 1
fi
if ! grep -q 'no-backup-db is forbidden' "$MANAGE"; then
  echo "FAIL: manage_deploy must refuse --no-backup-db on release" >&2
  exit 1
fi
STATUS_SH="$ROOT/scripts/release/status-release.sh"
if [[ ! -f "$STATUS_SH" ]]; then
  echo "FAIL: missing status-release.sh" >&2
  exit 1
fi

# Release identity helper against this repo tip.
# shellcheck source=deploy/lib/deploy_guard.sh
source "$GUARD"
APP_REL="$(deploy_guard_read_app_release "$ROOT")"
if [[ -z "$APP_REL" ]]; then
  echo "FAIL: deploy_guard_read_app_release returned empty" >&2
  exit 1
fi
echo "OK: APP_RELEASE readable ($APP_REL)"

# Empty forward-args must not inject a blank argv token into manage_deploy.
if grep -q 'MD_DEPLOY_FORWARD_ARGS\[@\]:-' "$SOURCE"; then
  echo "FAIL: deploy_source must not use \${arr[@]:-} (injects empty option)" >&2
  exit 1
fi
if ! grep -q 'deploy_cmd' "$SOURCE"; then
  echo "FAIL: deploy_source should build deploy_cmd array without empty args" >&2
  exit 1
fi

echo "OK: deploy guard regression tests passed"
