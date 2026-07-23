#!/usr/bin/env bash
# Apply Alembic migrations on a disposable PostgreSQL database and verify revision.
#
# Requires POSTGRES_TEST_URL or STAGING_DATABASE_URL, e.g.:
#   POSTGRES_TEST_URL=postgresql+psycopg://ai_agent:staging_secret@127.0.0.1:5433/ai_site_agent_staging \
#     ./scripts/release/test-migration.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="$ROOT/backend"
VENV="${BACKEND}/.venv"

# shellcheck disable=SC1091
source "$ROOT/scripts/lib/test-db-env.sh"

DB_URL="${STAGING_DATABASE_URL:-${POSTGRES_TEST_URL:-}}"
if [[ -z "$DB_URL" ]]; then
  echo "ERROR: set STAGING_DATABASE_URL, POSTGRES_TEST_URL, or DATABASE_URL in repo .env" >&2
  exit 1
fi

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "ERROR: backend venv/python missing" >&2
  exit 1
fi

export BACKEND DB_URL
if ! "$VENV/bin/python" - <<'PY'; then
import os
import sys

sys.path.insert(0, os.environ["BACKEND"])
from tests._dbutil import is_usable_postgres_test_url

url = os.environ.get("DB_URL", "")
if not is_usable_postgres_test_url(url):
    sys.exit(1)
PY
  echo "ERROR: database URL is unset or looks like a documentation placeholder" >&2
  echo "  check DATABASE_URL in repo .env (host/db/credentials)" >&2
  echo "Use a real DSN, e.g.:" >&2
  echo "  POSTGRES_TEST_URL=postgresql+psycopg://ai_agent:secret@127.0.0.1:5432/ai_site_agent_migration_test" >&2
  echo "Do not export literal 'postgresql+psycopg://...' from docs." >&2
  exit 1
fi

export DATABASE_URL="$DB_URL"

cd "$BACKEND"

echo "==> Alembic upgrade head"
"$VENV/bin/alembic" upgrade head

echo "==> Current revision"
CURRENT="$("$VENV/bin/alembic" current 2>/dev/null | tail -1)"
echo "$CURRENT"

if [[ "$CURRENT" != *"0015_memory_shadow_write_enabled"* && "$CURRENT" != *"0014_epistemic_memory_tables"* && "$CURRENT" != *"(head)"* ]]; then
  echo "WARN: expected head 0015_memory_shadow_write_enabled — verify migration chain" >&2
fi

echo "==> Downgrade one step (rollback smoke) and re-upgrade"
"$VENV/bin/alembic" downgrade -1
"$VENV/bin/alembic" upgrade head

echo "OK: migration upgrade/downgrade/upgrade cycle passed on test database"
