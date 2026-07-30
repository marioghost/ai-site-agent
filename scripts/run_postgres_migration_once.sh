#!/usr/bin/env bash
# One-shot production migration from legacy SQLite to PostgreSQL.
#
# Run from any directory:
#   sudo bash /home/home/projects/ai-site-agent/scripts/run_postgres_migration_once.sh
#
# What it does:
# 1. Stops the backend.
# 2. Backs up the production SQLite DB.
# 3. Installs/starts PostgreSQL.
# 4. Syncs the updated code from the dev checkout to /opt.
# 5. Writes the generated PostgreSQL DATABASE_URL into /opt/.env.
# 6. Creates the PostgreSQL role/database if needed.
# 7. Installs backend Python dependencies.
# 8. Runs Alembic migrations.
# 9. Imports all SQLite data (including logs/caches) into PostgreSQL.
# 10. Restarts the backend and prints health/status.

set -euo pipefail

DEV_ROOT="/home/home/projects/ai-site-agent"
PROD_ROOT="/opt/ai-site-agent"
SQLITE_PATH="$PROD_ROOT/backend/ai_site_agent.db"
BACKUP_DIR="$PROD_ROOT/backups"
SERVICE_NAME="ai-agent-backend"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "ERROR: run as root:"
  echo "  sudo bash $0"
  exit 1
fi

if [[ ! -f "$DEV_ROOT/.env" ]]; then
  echo "ERROR: missing $DEV_ROOT/.env"
  exit 1
fi

# shellcheck disable=SC1091
source "$DEV_ROOT/.env"

if [[ -z "${DATABASE_URL:-}" || "$DATABASE_URL" != postgresql* ]]; then
  echo "ERROR: $DEV_ROOT/.env must contain a PostgreSQL DATABASE_URL"
  exit 1
fi

if [[ ! -f "$SQLITE_PATH" ]]; then
  echo "ERROR: production SQLite DB not found: $SQLITE_PATH"
  exit 1
fi

echo "==> Stopping backend (if running)"
systemctl stop "$SERVICE_NAME" 2>/dev/null || true

echo "==> Backing up SQLite DB"
mkdir -p "$BACKUP_DIR"
stamp="$(date +%Y%m%d_%H%M%S)"
sqlite_backup="$BACKUP_DIR/ai_site_agent.sqlite.before_pg.$stamp.db"
cp -a "$SQLITE_PATH" "$sqlite_backup"
echo "SQLite backup: $sqlite_backup"

echo "==> Installing PostgreSQL"
apt update
apt install -y postgresql postgresql-contrib
systemctl enable postgresql
systemctl start postgresql

echo "==> Syncing updated code to $PROD_ROOT"
rsync -a --delete \
  --exclude 'backend/.venv' \
  --exclude 'dashboard/node_modules' \
  --exclude 'dashboard/dist' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'logs/' \
  --exclude 'backups/' \
  --exclude 'deployments/' \
  --exclude '.git' \
  --exclude 'backend/ai_site_agent.db' \
  --exclude 'backend/ai_site_agent.db-*' \
  "$DEV_ROOT/" "$PROD_ROOT/"

echo "==> Writing PostgreSQL DATABASE_URL to production .env"
python3 - <<'PY'
from pathlib import Path
import os

dev_env = Path("/home/home/projects/ai-site-agent/.env")
prod_env = Path("/opt/ai-site-agent/.env")
url = None
for line in dev_env.read_text().splitlines():
    if line.startswith("DATABASE_URL="):
        url = line.split("=", 1)[1]
        break
if not url or not url.startswith("postgresql"):
    raise SystemExit("No PostgreSQL DATABASE_URL found in dev .env")

text = prod_env.read_text() if prod_env.exists() else ""
lines = []
replaced = False
for line in text.splitlines():
    if line.startswith("DATABASE_URL="):
        lines.append(f"DATABASE_URL={url}")
        replaced = True
    elif "SQLite for the MVP" in line:
        lines.append("# ---- Database (PostgreSQL only) ----")
    else:
        lines.append(line)
if not replaced:
    lines.append("# ---- Database (PostgreSQL only) ----")
    lines.append(f"DATABASE_URL={url}")
prod_env.write_text("\n".join(lines) + "\n")
print("Updated /opt/ai-site-agent/.env")
PY

echo "==> Parsing DATABASE_URL"
eval "$(
python3 - <<'PY'
from urllib.parse import urlparse, unquote
from pathlib import Path
url = None
for line in Path("/opt/ai-site-agent/.env").read_text().splitlines():
    if line.startswith("DATABASE_URL="):
        url = line.split("=", 1)[1].strip()
        break
if not url:
    raise SystemExit("DATABASE_URL missing in /opt/ai-site-agent/.env")
p = urlparse(url)
print(f"PG_USER={p.username!r}")
print(f"PG_PASSWORD={unquote(p.password or '')!r}")
print(f"PG_HOST={p.hostname or 'localhost'!r}")
print(f"PG_PORT={p.port or 5432!r}")
print(f"PG_DB={(p.path or '/ai_site_agent').lstrip('/')!r}")
PY
)"

echo "==> Creating PostgreSQL role/database"
sudo -u postgres psql -v ON_ERROR_STOP=1 -d postgres <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${PG_USER}') THEN
    CREATE ROLE "${PG_USER}" LOGIN PASSWORD '${PG_PASSWORD}';
  ELSE
    ALTER ROLE "${PG_USER}" WITH PASSWORD '${PG_PASSWORD}';
  END IF;
END
\$\$;
SQL

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${PG_DB}'" | grep -q 1; then
  sudo -u postgres createdb -O "$PG_USER" "$PG_DB"
fi
sudo -u postgres psql -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE \"${PG_DB}\" TO \"${PG_USER}\";"

echo "==> Installing backend dependencies"
cd "$PROD_ROOT/backend"
if [[ ! -x ".venv/bin/python" ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> Running Alembic migrations"
.venv/bin/python -m app.scripts.maintenance migrate

echo "==> Importing SQLite data into PostgreSQL"
.venv/bin/python scripts/migrate_sqlite_to_postgres.py \
  --sqlite-path "$SQLITE_PATH" \
  --postgres-url "$DATABASE_URL" \
  --truncate-target \
  --include-caches

echo "==> Fixing ownership"
chown -R www-data:www-data "$PROD_ROOT" 2>/dev/null || true

echo "==> Restarting backend"
systemctl daemon-reload
systemctl restart "$SERVICE_NAME"
sleep 3
systemctl --no-pager status "$SERVICE_NAME" || true

echo "==> Health check"
curl -sf http://127.0.0.1:8000/api/health || true
echo
echo "DONE: SQLite data has been migrated to PostgreSQL."
