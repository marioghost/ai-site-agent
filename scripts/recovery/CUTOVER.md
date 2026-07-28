# Recovery cutover / rollback (operator-executed)

**Do not run automatically.** Requires sudo for DB create and a service restart.

## Prerequisites (completed by agent where possible)

- Forensic dump: `/opt/ai-site-agent/backups/forensic/ai_site_agent.forensic.20260727_234044.dump`
- Consistency (Jul-5 dump vs Qdrant): **SAFE TO CUT OVER**
  - All Qdrant `source_id` values exist in the Jul-5 dump (0 orphans)
  - Some Postgres sources lack vectors (expected; not a blocker)

## Phase 2 — create + restore (operator)

```bash
sudo bash /home/home/projects/ai-site-agent/scripts/recovery/restore_into_recovery_db.sh
```

Or manually:

```bash
sudo -u postgres psql -h 127.0.0.1 -p 5432 -d postgres -c \
  "CREATE DATABASE ai_site_agent_recovery OWNER ai_agent;"

# Load password from /opt/ai-site-agent/.env into libpq, then:
pg_restore --no-owner --role=ai_agent \
  -d ai_site_agent_recovery \
  /opt/ai-site-agent/backups/ai_site_agent.20260705_232825.dump

/opt/ai-site-agent/backend/.venv/bin/python \
  /home/home/projects/ai-site-agent/scripts/recovery/validate_recovery_db.py \
  --database ai_site_agent_recovery
```

Expect: ~5023 sources, ~16263 chunks, 0 `fixture.example`.

## Phase 4 — cutover (preferred: point app at recovery DB)

```bash
# 1. Stop backend
sudo systemctl stop ai-agent-backend

# 2. Edit /opt/ai-site-agent/.env — change only the database name in DATABASE_URL:
#    .../ai_site_agent  →  .../ai_site_agent_recovery
#    Keep host/user/password unchanged.
#    Optionally keep a copy: /opt/ai-site-agent/.env.pre-cutover

# 3. Start backend
sudo systemctl start ai-agent-backend

# 4. Verify
curl -sS http://127.0.0.1:8000/api/health | python3 -m json.tool
# Login + list sources via dashboard or API; confirm UKRSIBBANK URLs, no fixture.example
# Run one known chat query

# 5. Keep wiped ai_site_agent untouched for rollback
```

Do **not** reindex. Do **not** modify Qdrant.

## Rollback

```bash
sudo systemctl stop ai-agent-backend
# Restore DATABASE_URL database name to ai_site_agent in /opt/ai-site-agent/.env
sudo systemctl start ai-agent-backend
curl -sS http://127.0.0.1:8000/api/health | python3 -m json.tool
```

## After cutover — optional disposable test DB (isolation)

```bash
sudo -u postgres psql -h 127.0.0.1 -p 5432 -d postgres -c \
  "CREATE DATABASE ai_site_agent_migration_test OWNER ai_agent;"

# In repo .env / CI:
# POSTGRES_TEST_URL=postgresql+psycopg://ai_agent:…@127.0.0.1:5432/ai_site_agent_migration_test
```
