#!/usr/bin/env bash
# Regression: migrate release schema-first CLI + guards.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MD="$ROOT/deploy/manage_deploy.sh"
CLI="$ROOT/deploy/lib/cli.sh"
MR="$ROOT/deploy/lib/migrate_release.sh"
GUARD="$ROOT/deploy/lib/deploy_guard.sh"
SOURCE="$ROOT/deploy/lib/deploy_source.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }

[[ -f "$MR" ]] || fail "missing migrate_release.sh"
[[ -f "$CLI" ]] || fail "missing cli.sh"

# shellcheck source=deploy/lib/migrate_release.sh
source "$MR"
# shellcheck source=deploy/lib/deploy_guard.sh
source "$GUARD"

help_out="$(bash "$MD" help 2>&1 || true)"
echo "$help_out" | grep -q 'migrate release' || fail "help missing migrate release"
echo "$help_out" | grep -q 'live /opt install tree' || fail "help must distinguish live migrate"
echo "$help_out" | grep -qiE 'recovery|schema-first' \
  || fail "help should document migrate release as recovery/schema-first"
echo "OK: help documents migrate release"

# Ambiguous overload protection: unknown migrate subcommand fails.
if bash "$MD" migrate not-a-thing >/dev/null 2>&1; then
  fail "unknown migrate subcommand should fail"
fi
echo "OK: unknown migrate subcommand refused"

# Redaction must never leak passwords.
redacted="$(md_migrate_release_redact_url 'postgresql+psycopg://ai_agent:s3cret-pass@localhost:5432/ai_site_agent')"
echo "$redacted" | grep -q 's3cret-pass' && fail "password leaked in redaction"
echo "$redacted" | grep -q '\*\*\*' || fail "redaction missing ***"
echo "$redacted" | grep -q 'ai_site_agent' || fail "db name lost in redaction"
echo "OK: password redaction"

dbn="$(md_migrate_release_db_name 'postgresql+psycopg://ai_agent:s3cret@localhost:5432/ai_site_agent')"
[[ "$dbn" == "ai_site_agent" ]] || fail "db name parse failed ($dbn)"
echo "OK: db name parse"

# Structural: migrate release must create worktree from origin/main and not use /opt as source.
grep -q 'worktree add' "$MR" || fail "migrate_release must use git worktree"
grep -q 'md_migrate_release' "$CLI" || fail "cli must call md_migrate_release"
grep -q 'refuses emergency' "$MR" || fail "migrate release must refuse emergency"
grep -q 'qdrant_touched=no' "$MR" || fail "migrate release must declare no Qdrant touch"
grep -q 'opt_code_synced=no' "$MR" || fail "migrate release must declare no /opt sync"
grep -q 'live_opt_backend_not_used\|migration source resolved to live' "$MR" \
  || fail "must refuse using /opt backend as migration source"
# Failure must not invoke deploy/sync/restart.
if grep -E 'deploy full|sync-from-dev|restart --module|restart-all' "$MR" | grep -vq '^#'; then
  # Allow comments only
  if grep -E '^[^#]*deploy full|^[^#]*sync-from-dev|^[^#]*restart-all|^[^#]*restart --module' "$MR"; then
    fail "migrate_release must not deploy/sync/restart"
  fi
fi
echo "OK: migrate_release fail-closed structure"

# Guard refusals on a disposable git repo (no live DB).
TMP="$(mktemp -d /tmp/migrate-release-guard-XXXXXX)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

git init -q "$TMP/repo"
git -C "$TMP/repo" config user.email "test@example.com"
git -C "$TMP/repo" config user.name "Test"
echo "a" >"$TMP/repo/README"
git -C "$TMP/repo" add README
git -C "$TMP/repo" commit -q -m "init"
git -C "$TMP/repo" branch -M main
git init -q --bare "$TMP/remote.git"
git -C "$TMP/repo" remote add origin "$TMP/remote.git"
git -C "$TMP/repo" push -q origin main

# Dirty tree
echo dirty >"$TMP/repo/dirty.txt"
if deploy_guard_assert_clean_worktree "$TMP/repo" "test" 2>/dev/null; then
  fail "dirty tree should be refused"
fi
rm -f "$TMP/repo/dirty.txt"
echo "OK: dirty tree refused"

# Non-main branch
git -C "$TMP/repo" checkout -q -b feature
if deploy_guard_assert_on_main_branch "$TMP/repo" 2>/dev/null; then
  fail "feature branch should be refused"
fi
git -C "$TMP/repo" checkout -q main
echo "OK: non-main refused"

# main != origin/main (local commit not pushed)
echo more >>"$TMP/repo/README"
git -C "$TMP/repo" add README
git -C "$TMP/repo" commit -q -m "ahead"
if deploy_guard_assert_local_main_matches_origin "$TMP/repo" 2>/dev/null; then
  fail "diverged main should be refused"
fi
echo "OK: main != origin/main refused"

# Integration (optional): disposable Postgres only — never ai_site_agent.
if [[ -n "${POSTGRES_TEST_URL:-}" ]]; then
  echo "INFO: POSTGRES_TEST_URL set — running disposable migrate-release integration"
  # shellcheck disable=SC1091
  source "$ROOT/scripts/lib/test-db-env.sh" 2>/dev/null || true
  LIVE="$TMP/live"
  mkdir -p "$LIVE/backend/migrations/versions" "$LIVE/logs" "$LIVE/backend/.venv/bin"
  # Stub /opt-like tree without 0018/0019 (prove we do not use it as source).
  echo 'revision = "0017_only"' >"$LIVE/backend/migrations/versions/0017_stub.py"
  # Point env at disposable DB.
  echo "DATABASE_URL=${POSTGRES_TEST_URL}" >"$LIVE/.env"
  # Reuse project venv binaries via symlinks for alembic/python.
  ln -sf "$ROOT/backend/.venv/bin/python" "$LIVE/backend/.venv/bin/python"
  ln -sf "$ROOT/backend/.venv/bin/alembic" "$LIVE/backend/.venv/bin/alembic"
  # Operator checkout must be a clean main matching origin — use ROOT itself only if clean.
  if deploy_guard_is_clean_worktree "$ROOT" \
    && [[ "$(git -C "$ROOT" branch --show-current)" == "main" ]] \
    && [[ "$(git -C "$ROOT" rev-parse main)" == "$(git -C "$ROOT" rev-parse origin/main)" ]]; then
    PROJECT_ROOT="$LIVE" \
      MD_DEPLOY_PROJECT_ROOT="$LIVE" \
      bash "$MD" migrate release --yes \
      || fail "migrate release integration failed"
    echo "OK: disposable migrate release integration"
  else
    echo "SKIP: integration requires clean main==origin/main operator checkout"
  fi
else
  echo "SKIP: disposable migrate-release integration (set POSTGRES_TEST_URL)"
fi

# Ensure manage_deploy / deploy_source still present for guards.
grep -q 'md_deploy_from_main' "$SOURCE" || fail "deploy_source regression"
echo "OK: migrate release regression tests passed"
