#!/usr/bin/env bash
# Resolve POSTGRES_TEST_URL from repo .env when not explicitly set.
# Defaults to DATABASE_URL (same credentials/host as the running app).
# Invalid placeholders (e.g. copied from docs) are ignored — matches tests/_dbutil.py.
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
from tests._dbutil import resolve_postgres_test_url

url = resolve_postgres_test_url()
if url:
    print(url)
PY
}

# Export first usable URL (POSTGRES_TEST_URL → DATABASE_URL), ignoring doc placeholders.
if RESOLVED="$(_resolve_postgres_test_url_python 2>/dev/null || true)" && [[ -n "$RESOLVED" ]]; then
  export POSTGRES_TEST_URL="$RESOLVED"
fi

return 0 2>/dev/null || exit 0
