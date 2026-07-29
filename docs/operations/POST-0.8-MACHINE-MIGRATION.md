# Post–Release 0.8 — Machine / Environment Migration (planning only)

**Status:** Planning document — **not executed** as part of RFC-100 Step 057  
**Related:** [RELEASE-0.8-ACCEPTANCE-REPORT.md](../releases/RELEASE-0.8-ACCEPTANCE-REPORT.md)  
**Date:** 2026-07-28

**Public operator entry point on every host:**

```bash
bash deploy/manage_deploy.sh <command>
```

Syntax: `bash deploy/manage_deploy.sh help`.  
Makefile targets (`make release-check`, etc.) are **internal developer/CI validation helpers only**.

This program migrates the entire operator workstation and runtime stack to a **new machine**. It is **out of band** from Release 0.8 Engineering Ready. Do not treat completion of Step 057 as authorization to cut over.

### Governance gate

After Release 0.8 engineering closure **and** its approved operational deployment, the next priority is **this machine migration**. Do **not** begin Release **0.9** or other new product functionality until machine-migration acceptance is recorded.

**Gate satisfied (2026-07-29):** the Release 0.8 operational deployment is complete and accepted — see [RELEASE-0.8-OPERATIONAL-DEPLOYMENT-REPORT.md](RELEASE-0.8-OPERATIONAL-DEPLOYMENT-REPORT.md). This machine migration is therefore the next approved program. Execution still requires an approved architecture review; `staging_validated` and `production_ready` remain **false**.

**Architecture review in progress:** [POST-0.8-MACHINE-MIGRATION-ARCHITECTURE-REVIEW.md](POST-0.8-MACHINE-MIGRATION-ARCHITECTURE-REVIEW.md) — Part 1 (old-machine topology and derived requirements) is complete; Part 2 (new-machine topology and cutover plan) is blocked on required inputs. **Migration execution is not authorized until that review is approved.**

---

## Goals

1. Reproduce a verified `origin/main` checkout of `ai-site-agent` (clean tree — no copied dirty worktree).
2. Recreate Cursor / agent tooling and project instructions.
3. Restore Postgres, Qdrant, Ollama, and `/opt` deploy layout with least surprise.
4. Validate via `deploy/manage_deploy.sh` (`status`, `verify-release`, `smoke`, health/build).
5. Keep `staging_validated` / `production_ready` **false** until the new environment itself is validated.

---

## Inventory

| Domain | Items |
|--------|-------|
| Git | Clean clone; verify `origin/main` tip; no force-push; no dirty-tree copy |
| Cursor | Install Cursor; rules, hooks, MCP/connectors, project instructions |
| Secrets | `.env`, `deploy/deploy.local.conf`, API keys, DB passwords — **secure channel only**; never commit |
| Language toolchains | Python 3.12+, Node (dashboard), system packages |
| PostgreSQL | `ai_site_agent` backup/restore; decide fate of `ai_site_agent_recovery` (incident DB only) |
| Qdrant | Storage volume / collections; verify point counts |
| Ollama | Models + service config |
| systemd / nginx | Unit inventory + site config |
| `/opt` layout | Classic Linux deploy path used by `deploy/manage_deploy.sh` |
| Deploy tooling | **Only** `bash deploy/manage_deploy.sh …` for public ops |
| Validation | `status`, `verify-release`, `smoke`, `health`, `build-info` |

---

## Gate A — Old-machine forensic baseline

Record before any cutover (read-only where possible):

| Item | How / note |
|------|------------|
| `origin/main` commit | `git rev-parse origin/main` |
| `/api/build` commit + release_status | `bash deploy/manage_deploy.sh build-info` |
| Alembic revision | from `build-info` / migrate status |
| Settings flags | `/api/settings` (Memory OFF; 0.8 flag defaults) |
| Corpus counts | sources/chunks/claims/observations/evidence links; knowledge/memory versions |
| Qdrant | collections + point counts (e.g. `site_knowledge`) |
| Ollama | model inventory (`ollama list` or service inventory) |
| Cursor | rules/hooks/MCP inventory (paths only — no secrets in git) |

---

## Gate B — Backup

| Asset | Requirement |
|-------|-------------|
| PostgreSQL | `bash deploy/manage_deploy.sh backup db` → dump + checksum + restore-list validation |
| Qdrant | Snapshot + checksum/inventory |
| Secrets/config | Encrypted or secure transfer of `.env` / `deploy.local.conf` |
| systemd/nginx | Unit and site-config inventory tarball |
| Cursor | Rules/config backup (non-secret) |

---

## Gate C — New-machine restore

1. Install OS packages, Postgres, Qdrant, Ollama, nginx, Node, Python.
2. **Clean clone** from `origin/main` (do **not** rsync a dirty working tree).
3. Restore Postgres; restore Qdrant; restore Ollama models/config.
4. Restore Cursor / project rules; place secrets via secure channel.
5. Install system dependencies required by `deploy/manage_deploy.sh doctor`.

---

## Gate D — Validation (new host)

When the new host still lacks migration files that `origin/main` requires (schema-first case), use the same Release 0.8 cutover order — **never** `deploy full` then bare `migrate`:

```text
status → backup db → migrate release → verify schema head
→ deploy full → health → build-info → smoke → verify-release
```

```bash
bash deploy/manage_deploy.sh doctor
bash deploy/manage_deploy.sh status
bash deploy/manage_deploy.sh backup db
bash deploy/manage_deploy.sh migrate release   # only supported schema-first path
# STOP unless head/post revision/columns verified (see RELEASE-0.8-PRE-DEPLOY-PLAN.md)
sudo bash deploy/manage_deploy.sh deploy full   # only when approved for this host
bash deploy/manage_deploy.sh health
bash deploy/manage_deploy.sh build-info
bash deploy/manage_deploy.sh smoke
bash deploy/manage_deploy.sh verify-release
```

| Command | Role on this host |
|---------|-------------------|
| `migrate` / `migrate live` | Alembic from **currently deployed `/opt`** tree only — cannot advance past files present in `/opt` |
| `migrate release` | **Only** supported schema-first command (clean origin/main worktree → live `/opt` DB) |
| `deploy full` inner migrate | Post-sync idempotent defense-in-depth; **not** a substitute for `migrate release` |

Manual checks after CLI gates:

- Dashboard load
- Chat + follow-up
- Source retrieval
- Corpus counts vs Gate A baseline
- Qdrant counts vs Gate A baseline
- Logs: `bash deploy/manage_deploy.sh logs --module backend`
- Flags still at intended defaults (Memory OFF; 0.8 flags as ops approved)

Apply Alembic **0018/0019** via **`migrate release`** when `/opt` does not yet contain those files. Do **not** rely on bare `migrate` for that gate.

---

## Gate E — Cutover and rollback

| Rule | Detail |
|------|--------|
| Freeze / write coordination | Avoid dual-write ambiguity during cutover |
| Old host | Retained for rollback window |
| Cutover | Explicit cutover **approver** sign-off |
| Rollback | Repoint operators to old host; **do not** clear Qdrant as a “fix” |
| Release 0.9 | Blocked until this migration is accepted |

---

## Explicit non-goals for Step 057

- Do **not** execute this migration during engineering closure.
- Do **not** mutate live Qdrant/Postgres from the agent session “to prepare” migration.
- Do **not** mark Staging Validated or Production Ready because a plan exists.
- Do **not** start Release 0.9 from this document alone.

---

## Owners / sign-off (fill at execution time)

| Role | Name | Date |
|------|------|------|
| Ops lead | | |
| Engineering | | |
| Cutover approver | | |
| Machine-migration acceptance | | |
