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
| **Staging-validated** | Approved `deploy full` SUCCESS on Linux server, then separate product checks (indexing + chat recorded) | **Production-ready** |
| **Production-ready** | Staging-validated + rollback verified + ops sign-off | **Production deployment** |

**Do not mark production-ready without staging-validated.**

### Post–Release 0.8 governance (project policy)

After Release 0.8 engineering closure and its **approved operational deployment**, do **not** begin Release **0.9** or other new product functionality.

Next priority: **Post-0.8 Machine / Environment Migration** ([POST-0.8-MACHINE-MIGRATION.md](../operations/POST-0.8-MACHINE-MIGRATION.md)).

Sequence:

1. Merge and push Release 0.8 closure.
2. Approved Release 0.8 deployment and migrations **0018/0019**.
3. Validate Release 0.8 runtime (`deploy full` SUCCESS; optional diagnostics: `status` / `verify-release`).
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

## Deterministic release deploy chain (One Command)

Normal release is **one** operator command:

```bash
sudo bash deploy/manage_deploy.sh deploy full
```

Internal pipeline (owned by `deploy full`):

```text
preflight → backup → migration decision → conditional schema-first
→ build → sync → post-sync migrate → restart → health
→ verify-release → smoke → report → SUCCESS
```

Schema-first is **auto-detected** and executed internally when tip migrations are absent from `/opt`. Post-sync Alembic always runs (idempotent no-op OK; failure is fatal). Restart and health failures are fatal. Exit `0` only on full SUCCESS with a written report under `deployments/`.

**Migrate commands (diagnostics / recovery — not normal-release stages):**

| Command | Alembic source | Effect |
|---------|----------------|--------|
| `migrate` | Live `/opt` install tree | Upgrade using currently deployed migration files only |
| `migrate live` | Same as bare `migrate` | Explicit alias of bare `migrate` |
| `migrate release` | Clean **origin/main** worktree | Recovery schema-first only; **no** code sync, **no** restart |

Policy enforced by the CLI for deploy source: clean worktree from `origin/main` only (never dirty trees, never feature branches). `migrate release` refuses emergency overrides. Optional post-deploy diagnostics: `status`, `verify-release`, `health`, `build-info`, `doctor`.

---

## Staging (required before production)

- [ ] Developer/CI: `make release-check` green
- [ ] `bash deploy/manage_deploy.sh status` — `main` / `origin/main` aligned; tree clean (diagnostic)
- [ ] `sudo bash deploy/manage_deploy.sh deploy full` → **VERDICT: SUCCESS** (owns backup, schema-first if needed, verify, smoke)
- [ ] Inspect `deployments/latest.json` for outcome/commit/release
- [ ] Site indexed on staging (see [STAGING-SEED-SMOKE.md](../STAGING-SEED-SMOKE.md)) — product acceptance, not a deploy stage
- [ ] Optional diagnostics if needed: `health` / `build-info` / `verify-release`
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
- [ ] `bash deploy/manage_deploy.sh status` clean / `origin/main` tip confirmed (diagnostic)
- [ ] All Memory / migration experiment flags **OFF** unless separately approved
- [ ] `sudo bash deploy/manage_deploy.sh deploy full` → **VERDICT: SUCCESS**
- [ ] Rollback owner identified; release rollback doc reviewed (e.g. [0.8-rollback.md](0.8-rollback.md))

---

## Rollback verification

- [ ] Prefer Settings/env flag rollback first (see release-specific rollback doc)
- [ ] Settings flags confirmed via `/api/settings`
- [ ] For code rollback: known-good tip on `origin/main`, then `sudo bash deploy/manage_deploy.sh deploy full` (see [0.8-rollback.md](0.8-rollback.md))
- [ ] Runtime commit equals the intended rollback target (`deployments/latest.json` / optional `status` / `verify-release`)

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
