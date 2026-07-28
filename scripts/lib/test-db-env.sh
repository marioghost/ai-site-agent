#!/usr/bin/env bash
# Resolve POSTGRES_TEST_URL only when explicitly set to a usable DSN.
# NEVER falls back to DATABASE_URL (incident remediation).
set -euo pipefail

TEST_DB_ENV_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_DB_ENV_VENV="${TEST_DB_ENV_VENV:-$TEST_DB_ENV_ROOT/backend/.venv/bin/python}"

if [[ -f "$TEST_DB_ENV_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$TEST_DB_ENV_ROOT/.env"
  set +a
fi

_resolve_postgres_test_url_python() {
  if [[ ! -x "$TEST_DB_ENV_VENV" ]]; then
    return 1
  fi
  TEST_DB_ENV_ROOT="$TEST_DB_ENV_ROOT" "$TEST_DB_ENV_VENV" - <<'PY'
import os
import sys

sys.path.insert(0, os.path.join(os.environ["TEST_DB_ENV_ROOT"], "backend"))
from tests._dbutil import (
    assert_isolated_from_app_database,
    is_safe_test_database_name,
    is_usable_postgres_test_url,
    resolve_postgres_test_url,
)
from sqlalchemy.engine import make_url

url = resolve_postgres_test_url()
if not url:
    sys.exit(0)
if not is_usable_postgres_test_url(url):
    sys.exit(0)
try:
    assert_isolated_from_app_database(url)
except Exception as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    sys.exit(2)
name = make_url(url).database or ""
if not is_safe_test_database_name(name):
    print(
        f"ERROR: POSTGRES_TEST_URL database {name!r} must end with "
        "_test / _integration_test / _migration_test",
        file=sys.stderr,
    )
    sys.exit(2)
print(url)
PY
}

# Only export when explicitly configured and isolation-safe.
if RESOLVED="$(_resolve_postgres_test_url_python 2>/tmp/test_db_env_err.txt || true)" \
  && [[ -n "${RESOLVED:-}" ]]; then
  export POSTGRES_TEST_URL="$RESOLVED"
elif [[ -s /tmp/test_db_env_err.txt ]]; then
  # Surface isolation errors; do not export a bad URL.
  cat /tmp/test_db_env_err.txt >&2 || true
fi

return 0 2>/dev/null || exit 0
