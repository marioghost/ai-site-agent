# Release checklist (all RFC releases)

Copy into PR or ops ticket.

**Public operator entry point (permanent policy):**

```bash
bash deploy/manage_deploy.sh <command>
```

`sudo` is required for deploy paths that write `/opt` and restart systemd (see examples below).  
Makefile targets (`make release-check`, etc.) are **developer/CI gates only** — not the public deploy workflow.

Canonical help (source of truth for syntax):

```bash
bash deploy/manage_deploy.sh help
```

---

## Release readiness tiers

Three **independent** states — see [LIFECYCLE.md](../LIFECYCLE.md) (Engineering Ready → Staging Validated → Production Ready).

| State | Requirement | Blocks |
|-------|-------------|--------|
| **Engineering-ready** | `make release-check` (or `bash deploy/manage_deploy.sh release check`) passes | Additive engineering may continue only per **post-release governance** below |
| **Staging-validated** | Approved `deploy full` + `smoke` + `verify-release` on Linux server; indexing + chat recorded | **Production-ready** |
| **Production-ready** | Staging-validated + rollback verified + ops sign-off | **Production deployment** |

**Do not mark production-ready without staging-validated.**

### Post–Release 0.8 governance (project policy)

After Release 0.8 engineering closure and its **approved operational deployment**, do **not** begin Release **0.9** or other new product functionality.

Next priority: **Post-0.8 Machine / Environment Migration** ([POST-0.8-MACHINE-MIGRATION.md](../operations/POST-0.8-MACHINE-MIGRATION.md)).

Sequence:

1. Merge and push Release 0.8 closure.
2. Approved Release 0.8 deployment and migrations **0018/0019**.
3. Validate Release 0.8 runtime (`status`, `verify-release`, smoke).
4. Execute the separately approved machine migration.
5. Validate the new machine.
6. Only after machine-migration acceptance may Release **0.9** planning begin.

Release 0.8 acceptance: [RELEASE-0.8-ACCEPTANCE-REPORT.md](RELEASE-0.8-ACCEPTANCE-REPORT.md). Prior: [RELEASE-0.7-ACCEPTANCE-REPORT.md](RELEASE-0.7-ACCEPTANCE-REPORT.md).

---

## Pre-merge (developer / CI)

- [ ] `make release-check` green (canonical CI/dev gate)
- [ ] New migrations have upgrade **and** downgrade
- [ ] Feature flags default **OFF** documented in `docs/FEATURE_FLAGS.md`
- [ ] Rollback runbook updated if schema or flags changed

---

## Deterministic release deploy chain

Normal Release 0.8+ cutover (schema-first):

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

Operator commands (from repo root):

```bash
bash deploy/manage_deploy.sh status
bash deploy/manage_deploy.sh backup db
bash deploy/manage_deploy.sh migrate release   # schema-first; no /opt sync, no restart
sudo bash deploy/manage_deploy.sh deploy full
bash deploy/manage_deploy.sh health
bash deploy/manage_deploy.sh build-info
bash deploy/manage_deploy.sh smoke
bash deploy/manage_deploy.sh verify-release
```

**Migrate command distinction:**

| Command | Alembic source | Effect |
|---------|----------------|--------|
| `migrate` | Live `/opt` install tree | Upgrade using currently deployed migration files only |
| `migrate live` | Same as bare `migrate` | Explicit alias of bare `migrate` |
| `migrate release` | Clean **origin/main** worktree | **Only** supported schema-first path; **no** code sync, **no** restart |

**`deploy full` and migrations (recommendation B):** after code sync, `deploy full` still runs internal `run_migrations` (`alembic upgrade head`). After a successful `migrate release`, that second invocation is an **idempotent no-op** (Alembic is revision-aware — no duplicate DDL). It is retained as **defense-in-depth** for bootstrap / routine deploys. It is **not** a substitute for `migrate release` when `/opt` lacks required migration files. A failure of the post-sync migrate must still fail deploy (possible environment/revision corruption).

**Policy vs enforcement:** the CLI does **not** hard-block `deploy full` if `migrate release` was skipped. Schema-first compliance is operator workflow + documentation. Deferred: preflight comparing `/opt` head, origin/main head, and live DB revision (not implemented).

Policy enforced by the CLI for deploy source: clean worktree from `origin/main` only (never dirty trees, never feature branches). `migrate release` refuses emergency overrides.

---

## Staging (required before production)

- [ ] Developer/CI: `make release-check` green
- [ ] `bash deploy/manage_deploy.sh status` — `main` / `origin/main` aligned; tree clean
- [ ] `bash deploy/manage_deploy.sh backup db`
- [ ] `bash deploy/manage_deploy.sh migrate release` → Alembic head verified (STOP if not 0019 + columns)
- [ ] `sudo bash deploy/manage_deploy.sh deploy full` succeeds
- [ ] Site indexed on staging (see [STAGING-SEED-SMOKE.md](../STAGING-SEED-SMOKE.md))
- [ ] `bash deploy/manage_deploy.sh health` / `build-info` / `smoke` green (smoke also runs inside `deploy full`)
- [ ] `bash deploy/manage_deploy.sh verify-release` green
- [ ] `GET /api/build` shows expected `release`, `alembic_head`, versions
- [ ] `GET /api/metrics` shows `kos_memory_version`
- [ ] Chat smoke with Executive **OFF** (flags-off paths)
- [ ] Any Executive **ON** experiment documented + rolled back (staging only)
- [ ] Logs reviewed: `bash deploy/manage_deploy.sh logs --module backend` (or equivalent journal via doctor/status guidance)

---

## Optional (never required for release)

- [ ] `make test-migration` on disposable DB (auto-loaded from repo `.env` if set) — developer gate
- [ ] Docker build validation — **optional**; `release-check` skips when Docker unavailable
- [ ] Flag-ON cache v2 experiment (`cache_namespace_v2_enabled`) — separate ops ticket

---

## Production deploy

- [ ] Staging-validated tier achieved
- [ ] `bash deploy/manage_deploy.sh status` clean / `origin/main` tip confirmed
- [ ] `bash deploy/manage_deploy.sh backup db`
- [ ] Schema-first when new migrations ship: `bash deploy/manage_deploy.sh migrate release`
- [ ] All Memory / migration experiment flags **OFF** unless separately approved
- [ ] `sudo bash deploy/manage_deploy.sh deploy full`
- [ ] `bash deploy/manage_deploy.sh health` / `build-info` / `smoke` / `verify-release` green
- [ ] Rollback owner identified; release rollback doc reviewed (e.g. [0.8-rollback.md](0.8-rollback.md))

---

## Rollback verification

- [ ] Prefer Settings/env flag rollback first (see release-specific rollback doc)
- [ ] Settings flags confirmed via `/api/settings`
- [ ] For code rollback: known-good tip on `origin/main`, then `sudo bash deploy/manage_deploy.sh deploy full` + `verify-release` (see [0.8-rollback.md](0.8-rollback.md))
- [ ] `bash deploy/manage_deploy.sh smoke` green after rollback
- [ ] Runtime commit equals the intended rollback target (`status` / `build-info` / `verify-release`)

---

## Post-deploy verification

- [ ] Dashboard loads; hard refresh if frontend changed
- [ ] No error spike in backend logs (15 min watch): `bash deploy/manage_deploy.sh logs --module backend`

---

## Release-specific notes

| Release | Migrations head | Key smoke |
|---------|-----------------|-----------|
| 0.1 | ≤ `0010` | health, golden unit |
| 0.2 | `0011_semantic_diagnostics_v2` | + settings flags present |
| 0.3 | `0013_cache_namespace_v2_enabled` | + `/api/build`, `/api/metrics`, memory_version |
| 0.4 | `0015_memory_shadow_write_enabled` | + epistemic tables present; shadow flag OFF |
| 0.5 | `0015` (no new migrations) | + `kos_open_tensions`; admin `/understanding` |
| 0.6 | `0015` (no new migrations) | Reasoning/EA/speech-act flags OFF; golden parity |
| 0.7 | `0017_memory_canonical_shadow_enabled` (code head) | Assist/shadow Settings OFF; `/api/build` `closed_0_7`; no Memory chat influence |
| 0.8 | `0019_legacy_doc_type_canonical_enabled` (code head) | Preset 410 default; doc-type canonical flag OFF; `/api/build` `closed_0_8`; staging_validated=false; 0018/0019 not claimed live |
| 0.9 | `0019` (no new migrations) | Maintenance execution OFF; `/api/build` `closed_0_9`; three investigation counters only; `kos_tension_resolved_total` deferred; staging_validated=false |

See [DEPLOYMENT.md](../DEPLOYMENT.md) and [STAGING-SEED-SMOKE.md](../STAGING-SEED-SMOKE.md). Operator deploy always via `bash deploy/manage_deploy.sh …`.
