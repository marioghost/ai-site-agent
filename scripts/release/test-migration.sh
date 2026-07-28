#!/usr/bin/env bash
# Apply Alembic migrations on a disposable PostgreSQL database and verify revision.
#
# Requires POSTGRES_TEST_URL pointing at a disposable DB (*_test / *_migration_test /
# *_integration_test). Never uses the application DATABASE_URL.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="$ROOT/backend"
VENV="${BACKEND}/.venv"

# shellcheck disable=SC1091
source "$ROOT/scripts/lib/test-db-env.sh"

DB_URL="${STAGING_DATABASE_URL:-${POSTGRES_TEST_URL:-}}"
if [[ -z "$DB_URL" ]]; then
  echo "ERROR: set POSTGRES_TEST_URL (or STAGING_DATABASE_URL) to a disposable test DB" >&2
  echo "  e.g. POSTGRES_TEST_URL=postgresql+psycopg://ai_agent:secret@127.0.0.1:5432/ai_site_agent_migration_test" >&2
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
from sqlalchemy.engine import make_url
from tests._dbutil import (
    assert_destructive_database_allowed,
    assert_isolated_from_app_database,
    is_usable_postgres_test_url,
)

url = os.environ.get("DB_URL", "")
if not is_usable_postgres_test_url(url):
    print("ERROR: URL unusable / placeholder", file=sys.stderr)
    sys.exit(1)
try:
    assert_isolated_from_app_database(url)
    assert_destructive_database_allowed(url)
except Exception as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    sys.exit(2)
print(make_url(url).database)
PY
  echo "ERROR: migration test refused non-isolated database" >&2
  exit 1
fi

export DATABASE_URL="$DB_URL"
export POSTGRES_TEST_URL="$DB_URL"

cd "$BACKEND"

echo "==> Alembic upgrade head (isolated DB)"
"$VENV/bin/alembic" upgrade head

echo "==> Current revision"
CURRENT="$("$VENV/bin/alembic" current 2>/dev/null | tail -1)"
echo "$CURRENT"

echo "==> Alembic downgrade -1 then upgrade head"
"$VENV/bin/alembic" downgrade -1
"$VENV/bin/alembic" upgrade head

echo "OK: migration test on isolated database"
