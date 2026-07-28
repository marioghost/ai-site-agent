# Release 0.8 — Pre-Deploy Plan (read-only / approval gate)

**Status:** Planning only for **execution** of migrate/deploy — this document does **not** by itself authorize running them.  
**Date:** 2026-07-28 (updated 2026-07-29: schema-first + recommendation B)  
**Operator entry point (only):** `bash deploy/manage_deploy.sh <command>`  
**Syntax:** `bash deploy/manage_deploy.sh help`  
**Governance:** After approved schema-first deploy + runtime validation, next program is [POST-0.8-MACHINE-MIGRATION.md](POST-0.8-MACHINE-MIGRATION.md). Release **0.9** remains blocked.

---

## 0. Identity / safety state (last measured)

| Check | Value |
|-------|--------|
| Engineering tip / plan tip | `4de1e3813a810b864bba94b14b0c1dbf1ea90c1b` on `origin/main` (plus later migrate-release CLI commit when merged) |
| `/opt` (must stay until deploy) | `d3cf472` · release **0.7** |
| Live Alembic (must stay until migrate release) | **0017_memory_canonical_shadow_enabled** |
| Verified backup | `/opt/ai-site-agent/backups/ai_site_agent.20260728_233243.dump` |
| Backup SHA256 | `d7f779753244431011403b7b2229280cf028cdb71ac08a462a8687d3892a4ef0` |

**Do not** use ad-hoc `DEV_CHECKOUT`-backed migrate. **Do not** partial-sync `/opt`. Use **`migrate release`** only for schema-first.

---

## HARD SAFETY — do not deploy until migrate release proves 0019

For this Release **0.8** cutover, **do not** run `deploy full` until `migrate release` has:

- exited successfully;
- reported the target **origin/main** commit;
- reported repository head **`0019_legacy_doc_type_canonical_enabled`**;
- verified live DB post revision is **0019**;
- verified both new Settings columns exist.

If these checks do **not** pass: **STOP. Do not deploy.**

---

## Why bare `migrate` is insufficient for Release 0.8

| Command | Alembic source | Role |
|---------|----------------|------|
| `migrate` | Live `/opt` install tree | Upgrade using currently deployed migration files only |
| `migrate live` | Same as bare `migrate` | Explicit alias |
| `migrate release` | Clean **origin/main** worktree | **Only** supported schema-first command |

Bare `migrate` / `migrate live` run Alembic from **`BACKEND_DIR` under live `/opt`**. While `/opt` is Release **0.7**, that tree only contains migrations through **0017**, so they **cannot** apply **0018/0019**. They are **not** a substitute for `migrate release` before sync.

`migrate release`: Alembic scripts from a **clean origin/main worktree**; `DATABASE_URL` from **`/opt/.../.env`**; **no** `/opt` code sync; **no** service restart.

---

## Approved operator sequence (identical everywhere)

```text
status
→ backup db
→ migrate release
→ verify schema head
→ deploy full
→ health
→ build-info
→ smoke
→ verify-release
```

```bash
bash deploy/manage_deploy.sh status
bash deploy/manage_deploy.sh backup db
bash deploy/manage_deploy.sh migrate release
# STOP unless report shows origin/main tip, head 0019, post revision 0019, columns OK
sudo bash deploy/manage_deploy.sh deploy full
bash deploy/manage_deploy.sh health
bash deploy/manage_deploy.sh build-info
bash deploy/manage_deploy.sh smoke
bash deploy/manage_deploy.sh verify-release
```

Then: manual dashboard / Sources / Chat / Understanding; preset **410**; Step 055 overview/news quality; corpus / Qdrant before–after.

**Do not** use the obsolete order `deploy full` → `migrate`. **Do not** skip `migrate release` when `/opt` lacks the required migration files.

---

## Migration execution graph (recommendation B)

```text
migrate release
  → clean origin/main worktree
  → live /opt env (DATABASE_URL)
  → Alembic upgrade head
  → verify DB head (0019) + Settings columns

deploy full
  → clean origin/main worktree
  → sync code to /opt
  → internal run_migrations
  → Alembic upgrade head (expected no-op at 0019)
  → restart
  → smoke
  → verify
```

| Fact | Detail |
|------|--------|
| Duplicate DDL? | **No** — Alembic is revision-aware; at head the second run applies no new revisions |
| Second Alembic invocation | **Redundant but intentional** defense-in-depth after sync |
| Post-sync migrate failure | Must **still fail deploy** and be reported — may indicate environment or revision corruption |
| Substitute for `migrate release`? | **No** — post-sync migrate is not a schema-first cutover gate |

Approved engineering decision **B**: keep post-sync `run_migrations` inside `deploy full`. Do **not** remove it for bootstrap / routine deploy compatibility.

---

## Migration-first rationale

Migrations **0018** / **0019** are additive Settings booleans with `server_default=false`. Applying them while Release **0.7** remains running is the compatible direction. Starting Release **0.8** code before those columns exist risks Settings/startup failures.

---

## `migrate release` failure gate

If `migrate release` fails:

- do **not** run `deploy full`
- leave `/opt` Release 0.7 unchanged
- do **not** sync code
- do **not** restart services
- do **not** retry with manual SQL
- do **not** auto-downgrade
- retain the timestamped report under `/opt/ai-site-agent/logs/migrate-release-*.log`
- stop for operator review

---

## Policy vs hard enforcement

| Fact | Detail |
|------|--------|
| Hard block? | `manage_deploy.sh` does **not** yet refuse `deploy full` when `migrate release` was skipped |
| Enforcement today | Operator workflow + documentation (this plan, checklist, closure docs) |
| CLI proof? | **No** — the CLI does **not** prove the pre-migration gate ran |

**Deferred follow-up (not implemented):** deploy preflight that compares `/opt` migration head, `origin/main` migration head, and live DB revision, and refuses `deploy full` when schema-first migration is required but incomplete. Do **not** add a hidden marker file or state flag for this.

---

## Baseline honesty

Historical expected baselines (not current live proof unless re-measured):

| Metric | Historical expected |
|--------|---------------------|
| sources | 5023 |
| chunks | 17958 |
| claims | 39 |
| observations | 13 |
| evidence links | 21 |
| knowledge_version | 26 |
| memory_version | 177 |
| fixture.example | 0 |
| Qdrant `site_knowledge` | 18780 |

Last measured via `/api/build` (pre-deploy): `memory_version=177`, `knowledge_version=26`, Alembic **0017**. Corpus list/Qdrant counts may be unverified if overview auth fails — re-measure when possible; never fabricate.

---

## Classification reminder

| State | Value |
|-------|-------|
| Engineering Ready | PASS |
| Staging Validated | false |
| Production Ready | false |
| Deployment | **not executed** (until separately approved) |
| Migrations 0018/0019 live | **not applied** (until `migrate release` approved) |
| Machine migration | planned, not executed |
| Release 0.9 | blocked |
