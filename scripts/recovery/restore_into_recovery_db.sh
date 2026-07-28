#!/usr/bin/env bash
# Operator-assisted recovery: create DB + restore Jul-5 dump into ai_site_agent_recovery.
# Does NOT touch ai_site_agent or Qdrant.
#
# Usage (interactive — requires postgres privileges):
#   sudo bash /home/home/projects/ai-site-agent/scripts/recovery/restore_into_recovery_db.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OPT_ROOT="${OPT_ROOT:-/opt/ai-site-agent}"
ENV_FILE="${ENV_FILE:-$OPT_ROOT/.env}"
DUMP="${DUMP:-$OPT_ROOT/backups/ai_site_agent.20260705_232825.dump}"
RECOVERY_DB="${RECOVERY_DB:-ai_site_agent_recovery}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: missing $ENV_FILE" >&2
  exit 1
fi
if [[ ! -f "$DUMP" ]]; then
  echo "ERROR: missing dump $DUMP" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

OWNER="$(
  "$OPT_ROOT/backend/.venv/bin/python" - <<'PY'
import os
from sqlalchemy.engine import make_url
print(make_url(os.environ["DATABASE_URL"]).username)
PY
)"

echo "==> Creating database $RECOVERY_DB owned by $OWNER (postgres superuser)"
echo "    This will NOT modify ai_site_agent."
read -r -p "Type CREATE to continue: " confirm
if [[ "$confirm" != "CREATE" ]]; then
  echo "Aborted."
  exit 1
fi

if ! command -v psql >/dev/null; then
  echo "ERROR: psql not found" >&2
  exit 1
fi

run_as_postgres() {
  if [[ "$(id -u)" -eq 0 ]]; then
    su -s /bin/bash postgres -c "$*"
  else
    sudo -u postgres bash -lc "$*"
  fi
}

EXISTS="$(run_as_postgres "psql -h 127.0.0.1 -p 5432 -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='$RECOVERY_DB'\"")"
EXISTS="$(echo "$EXISTS" | tr -d '[:space:]')"
if [[ "$EXISTS" == "1" ]]; then
  echo "Database $RECOVERY_DB already exists — skipping CREATE."
else
  run_as_postgres "psql -h 127.0.0.1 -p 5432 -d postgres -v ON_ERROR_STOP=1 -c \"CREATE DATABASE $RECOVERY_DB OWNER $OWNER;\""
  echo "Created $RECOVERY_DB"
fi

echo "==> Restoring $DUMP → $RECOVERY_DB"
# Prefer password from DATABASE_URL for ai_agent restore
eval "$(
  "$OPT_ROOT/backend/.venv/bin/python" - <<'PY'
import os
from sqlalchemy.engine import make_url
u = make_url(os.environ["DATABASE_URL"])
print(f"export PGHOST={u.host!r}")
print(f"export PGPORT={u.port or 5432}")
print(f"export PGUSER={u.username!r}")
print(f"export PGPASSWORD={u.password!r}")
PY
)"
export PGDATABASE="$RECOVERY_DB"
pg_restore --no-owner --role="$OWNER" -d "$RECOVERY_DB" "$DUMP" || {
  # pg_restore returns non-zero on some benign warnings; verify tables exist
  echo "pg_restore exited $? — verifying sources table..."
}
unset PGPASSWORD

echo "==> Validation"
"$OPT_ROOT/backend/.venv/bin/python" "$ROOT/scripts/recovery/validate_recovery_db.py" \
  --database "$RECOVERY_DB"

echo "DONE. Cutover is NOT performed by this script."
