# Release Engineering Workflow (Mandatory)

**Status:** Active project-wide policy  
**Scope:** Every future RFC-100 step and every release after Release 0.7  
**Source of truth:** `main` and `origin/main`  
**Canonical operator entry:** `bash deploy/manage_deploy.sh`  
**Canonical normal release:** `sudo bash deploy/manage_deploy.sh deploy full`

---

## Identity chain (must never break)

```
main  ==  origin/main  ==  build (.build-info.json)
                         ==  frontend (.deploy-identity.json)
                         ==  /opt runtime
                         ==  GET /api/build
                         ==  tip APP_RELEASE
```

Same git commit. No exceptions for normal deploys.  
Release identity is derived from tip `APP_RELEASE`. A stale configured `RELEASE_VERSION` is warned and ignored.

---

## Lifecycle (no exceptions)

1. Architecture Review  
2. Implementation on a temporary feature branch  
3. Tests  
4. Engineering Review  
5. Fixes  
6. Acceptance  
7. Merge into `main` (`manage_deploy.sh release merge`)  
8. Validate again on `main` (`release check` / tests)  
9. Push `origin/main` (`manage_deploy.sh release push`) — **ask separately**  
10. Deploy with the **one** normal-release command (`manage_deploy.sh deploy full`)  
11. Product staging validation (separate lifecycle; not a deploy stage)  
12. Staging → Production (when release accepts)

### Release 1.0 acceptance (Product Readiness Gate)

For Release 1.0 work, **step 6 Acceptance** means **both**:

- Functional Acceptance (RFC-100 / `make release-check`)
- **Product Readiness Gate** result ∈ {`PASS`, `PASS WITH DEBT`, `N/A`}  
  (`docs/RFC-PRODUCT-READINESS.md` §6)

| Gate result | Step 6 |
|-------------|--------|
| PASS | Allowed |
| PASS WITH DEBT | Allowed; debt recorded |
| FAIL | **Blocked** |
| N/A | Allowed (backend-only / non-user-facing; one-line justification) |
| Missing | **Blocked** |

Product Readiness runs **in parallel** with Release 1.0 engineering. The Gate is **not** a deploy stage and **not** a substitute for One Command Deployment. It does **not** delay starting Step 063.

```
Release 1.0 Engineering  +  Product Readiness  =  Release 1.0 Accepted Product
                         ↑
              Product Readiness Gate (per change)
```

Release 1.0 cannot be marked **Accepted** until Product Readiness Program completion criteria are met **and** no open Gate debt of class **must be resolved before Release 1.0 Acceptance** remains. See `docs/LIFECYCLE.md`.

---

## Normal release (One Command Deployment)

```bash
cd /path/to/ai-site-agent   # on main, clean, synced with origin/main
sudo bash deploy/manage_deploy.sh deploy full
```

That single command owns the frozen pipeline:

```text
preflight → backup → migration decision → conditional schema-first
→ build → sync → post-sync migrate → restart → health
→ verify-release → smoke → report → SUCCESS
```

| Behaviour | Rule |
|-----------|------|
| Schema-first | Auto-detected; run **internally** when tip migrations are absent from `/opt` |
| Post-sync Alembic | Always runs after sync (idempotent no-op OK; failure is fatal) |
| Restart / health | Fail-hard (no soft-ignore) |
| Verify + smoke | Required internal gates |
| Exit `0` | Only full Success Contract + success report written |
| Report | One JSON under `deployments/` (SUCCESS and FAILED); `latest.json` updated |

Operators must **not** run `backup db`, `migrate release`, `health`, `build-info`, `smoke`, or `verify-release` as part of a normal release. Those remain **diagnostics / audit / recovery** only.

### Migration commands (recovery / diagnostics)

| Command | Meaning |
|---------|---------|
| `migrate` / `migrate live` | Alembic from **live `/opt`** tree only |
| `migrate release` | **Recovery** schema-first: clean origin/main worktree → live `/opt` DB (no code sync, no restart) |

Bare `migrate` cannot advance beyond migrations present in `/opt`. Standalone `migrate release` is **not** a normal-release stage.

## Deploy policy

Refuse when:

- branch ≠ `main`
- detached HEAD
- dirty working tree
- local `main` ≠ `origin/main`
- build-info / frontend identity / `/api/build` disagree (verify-release gate)
- migration decision is ambiguous / DB unreachable / live DB ahead of tip / multiple heads

### Emergency mode (destructive override)

Never for routine Release work. Requires all of:

```bash
export EMERGENCY_DEPLOY_I_UNDERSTAND=YES
export EMERGENCY_DEPLOY_REASON='ticket/incident …'
export EMERGENCY_DEPLOY_CONFIRM=DEPLOY-OUTSIDE-ORIGIN-MAIN
```

Legacy `ALLOW_DIRTY_SYNC` / `DEPLOY_LOCAL_MAIN` are **rejected** unless emergency mode is active.

## Single entrypoint policy

All future deployment and release-engineering functionality must live under
`deploy/manage_deploy.sh` (CLI or menu).

Do **not** introduce new standalone deploy scripts unless they are
bootstrap/recovery utilities (`install_*.sh`, one-shot cutovers).

---

## Rollback lifecycle

Code rollback: put the known-good tip on `origin/main`, then run **one** command:

```bash
sudo bash deploy/manage_deploy.sh deploy full
```

Do not auto-downgrade the database. Schema failures require operator review (`review_schema_no_autodowngrade`).

Optional diagnostics after SUCCESS or FAILED: `status`, `verify-release`, `health`, `build-info`, `doctor`.

See release-specific rollback docs under `docs/releases/`.
