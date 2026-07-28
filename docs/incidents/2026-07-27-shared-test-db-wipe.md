# Incident postmortem — PostgreSQL wiped by shared test DB (2026-07-27)

**Status:** **CLOSED — cutback complete (2026-07-28)**  
**Canonical database:** `ai_site_agent` (single live development/demo database)  
**Temporary rollback:** `ai_site_agent_recovery` (retained; not for normal use)

---

## What happened

On 2026-07-27, integration/unit test helpers resolved `POSTGRES_TEST_URL` by falling back to `DATABASE_URL` (`ai_site_agent`). `make_engine(fresh=True)` called `Base.metadata.drop_all` on that database. Fixture helpers then inserted `fixture.example` rows. Qdrant vectors were **not** deleted.

During a subsequent full redeploy (2026-07-28), rsync from the dev checkout **overwrote `/opt/.env`**, pointing runtime back at the wiped `ai_site_agent` instead of the recovery cutover — making the corpus appear to “disappear” again in the dashboard even though recovery data still existed.

## Root cause

1. **Primary:** Test harness treated the application database as disposable when `POSTGRES_TEST_URL` was unset (silent fallback to `DATABASE_URL`).
2. **Secondary:** Deploy rsync did not exclude `.env`, allowing production cutover configuration to be clobbered by the repo checkout default.

## Affected data

| Store | Before incident | After wipe | After cutback (2026-07-28) |
|-------|-----------------|------------|---------------------------|
| `ai_site_agent` (live) | ~5023 sources, ~16k+ chunks | 18 fixtures, 0 chunks | **5023 sources, 17958 chunks** (restored) |
| Qdrant `site_knowledge` | ~17k+ points | Unchanged | **18780 points** (unchanged through recovery) |
| Epistemic rows | Mixed real/test | Test residue on wiped DB | 39 claims (6 SI, 33 test) — cleanup **not** executed |

## Recovery source

- **Gate B dump (authoritative for cutback):** `/opt/ai-site-agent/backups/cutback/ai_site_agent_recovery.20260728_093817.dump`
- **Earlier backup:** `/opt/ai-site-agent/backups/ai_site_agent.20260705_232825.dump` (superseded by Gate B recovery snapshot)
- **Forensic:** `/opt/ai-site-agent/backups/forensic/ai_site_agent.forensic.20260727_234044.dump`

Recovery DB was populated from Jul-5 backup + operator restore; Gate B snapshot reflected growth to **17958 chunks**.

## Qdrant consistency

At Gate D validation (pre–Gate E cutover):

- **18780** points in `site_knowledge`
- **3041** distinct `source_id` values in payloads
- **100% overlap** with PostgreSQL `sources.id` in recovery (then restored primary)
- **0 orphan** Qdrant IDs

No reindex or Qdrant collection recreate was required for cutback.

## Gate results (A–E)

| Gate | Result | Summary |
|------|--------|---------|
| **A** | SAFE TO PREPARE CUTBACK | Recovery held full corpus; primary was fixture-only |
| **B** | PASS | Timestamped dumps + checksums under `backups/cutback/` |
| **C** | Plan approved | Restore recovery dump → `ai_site_agent` (Option A; `--clean` used when sudo unavailable) |
| **D** | PASS | All row counts matched Gate B; Qdrant unchanged; recovery untouched |
| **E** | PASS | Runtime `DATABASE_URL` → `ai_site_agent`; smoke OK; recovery retained |

## Current architecture (post-cutback)

```
Runtime DATABASE_URL  →  ai_site_agent          (canonical, full corpus)
Rollback (temporary)  →  ai_site_agent_recovery (5023 sources; DO NOT USE for dev/tests/deploy)
Qdrant                →  site_knowledge         (unchanged)
```

**`ai_site_agent_recovery` is not a permanent environment.** It must not be used by:

- normal runtime / `.env` defaults
- automated tests or `release-check`
- deployment scripts
- development workflows

It exists only as **rollback infrastructure** until explicitly approved for removal after observation period and backup verification.

## Protections introduced (code)

- No `POSTGRES_TEST_URL` → `DATABASE_URL` fallback (`backend/tests/_dbutil.py`, `scripts/lib/test-db-env.sh`)
- `make_engine(fresh=True)` refuses non-`*_test` database names
- `assert_isolated_from_app_database()` rejects identical app/test DSN identity
- `release-check` skips DB integration + migration tests without disposable `POSTGRES_TEST_URL`
- `maintenance reset-db` / `trigger-reindex` require `--i-understand-destructive` + `--confirm=<db_name>`
- Deploy rsync excludes `.env` in **repository** `manage_deploy.sh` (sync to `/opt` still pending operator copy)

## Remaining operational risks (controlled debt)

These paths **can** wipe `ai_site_agent` but require **explicit operator action** — they are **not** triggered by `release-check` or normal unit tests:

| Path | Risk | Mitigation today |
|------|------|------------------|
| `POST /api/index/reindex-all` | Deletes all sources + Qdrant collection | Operator JWT only; no extra confirm |
| `maintenance reset-db` | `drop_all` on configured DB | Requires flags + exact DB name |
| `manage_deploy --clear-db` / menu reset | `DROP DATABASE` | Destructive confirm; `--yes` bypass exists |
| `manage_deploy` reindex API probe | Can trigger reindex-all | Interactive menu only |
| Alembic downgrade (manual) | Schema rollback | Not run by release-check |
| `migrate_sqlite_to_postgres.py` | DELETE FROM target tables | Deploy action only |
| Qdrant `clear-qdrant` / reindex | Vector wipe | Maintenance CLI / reindex paths |

**Classification:** Not blocking RFC resume — tests and release-check are safe. Operational hardening of one-click wipe paths remains recommended (future work).

## Operator references

- Cutback backups: `/opt/ai-site-agent/backups/cutback/`
- Gate reports: `gate_d_validation.json`, `gate_e_validation.json`
- Recovery runbook (historical): `scripts/recovery/CUTOVER.md`
