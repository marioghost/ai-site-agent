# Release Engineering Workflow (Mandatory)

**Status:** Active project-wide policy  
**Scope:** Every future RFC-100 step and every release after Release 0.7  
**Source of truth:** `main` and `origin/main`  
**Canonical operator entry:** `bash deploy/manage_deploy.sh`

---

## Identity chain (must never break)

```
main  ==  origin/main  ==  build (.build-info.json)
                         ==  frontend (.deploy-identity.json)
                         ==  /opt runtime
                         ==  GET /api/build
```

Same git commit. No exceptions for normal deploys.

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
10. Schema-first when `origin/main` has migrations not yet in `/opt`: `migrate release` → verify schema head  
11. Deploy only from `origin/main` (`manage_deploy.sh deploy full`)  
12. Verify runtime (`manage_deploy.sh health` / `build-info` / `smoke` / `verify-release`)  
13. Staging → Production (when release accepts)

---

## Schema-first cutover (when required)

When `origin/main` contains Alembic revisions not present in the live `/opt` tree (e.g. Release 0.8 while `/opt` is still 0.7):

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

| Command | Meaning |
|---------|---------|
| `migrate` / `migrate live` | Alembic from **live `/opt`** tree only (`migrate live` = explicit alias of bare `migrate`) |
| `migrate release` | **Only** supported schema-first command: clean origin/main worktree → live `/opt` DB |
| `deploy full` inner `run_migrations` | Post-sync Alembic upgrade (expected **idempotent no-op** after successful `migrate release`; retained as defense-in-depth) |

Operators **must not** skip `migrate release` when `/opt` lacks the required migration files. Bare `migrate` cannot advance beyond migrations present in `/opt`. Post-sync migrate inside `deploy full` is **not** a substitute for schema-first.

**Policy vs enforcement:** the CLI does **not** hard-block `deploy full` if `migrate release` was skipped. Compliance is operator workflow + documentation today. Deferred follow-up: preflight comparing `/opt` head, origin/main head, and live DB revision (not implemented; no marker file).

## Deploy stages (mandatory inside `deploy full`)

```
backup → build → deploy (sync + internal run_migrations) → verify → restart → smoke
```

`--no-backup-db` is **refused** on release deploy. A failure of the post-sync migrate must still fail the deploy (may indicate environment or revision corruption).

## Single entrypoint policy

All future deployment and release-engineering functionality must live under
`deploy/manage_deploy.sh` (CLI or menu).

Do **not** introduce new standalone deploy scripts unless they are
bootstrap/recovery utilities (`install_*.sh`, one-shot cutovers).

## Deploy policy

Deploy **only** from `origin/main` via (after schema-first when required):

```bash
cd /path/to/ai-site-agent   # on main, clean, synced
bash deploy/manage_deploy.sh backup db
bash deploy/manage_deploy.sh migrate release   # when /opt lacks required migrations
sudo bash deploy/manage_deploy.sh deploy full
bash deploy/manage_deploy.sh health
bash deploy/manage_deploy.sh build-info
bash deploy/manage_deploy.sh smoke
bash deploy/manage_deploy.sh verify-release
```

Refuse when:

- branch ≠ `main`
- detached HEAD
- dirty working tree
- local `main` ≠ `origin/main`
- build-info / frontend identity / `/api/build` disagree

### Emergency mode (destructive override)

Never for routine Release work. Requires all of:

```bash
export EMERGENCY_DEPLOY_I_UNDERSTAND=YES
export EMERGENCY_DEPLOY_REASON='ticket/incident …'
export EMERGENCY_DEPLOY_CONFIRM=DEPLOY-OUTSIDE-ORIGIN-MAIN
```

Legacy `ALLOW_DIRTY_SYNC` / `DEPLOY_LOCAL_MAIN` are **rejected** unless emergency mode is active.

---

## Rollback lifecycle

1. Prefer flag OFF (no data deletion) — see `docs/releases/0.7-rollback.md`.  
2. Redeploy previous known-good `origin/main` commit only after it is restored on `origin/main` (revert merge + push), then `deploy full`.  
3. Do not rsync arbitrary checkouts as “rollback”.

---

## Operator checklist

- [ ] On `main`, clean tree  
- [ ] `main` == `origin/main`  
- [ ] `manage_deploy.sh status` / `release status` → Deploy readiness OK  
- [ ] `manage_deploy.sh backup db`  
- [ ] When schema-first required: `migrate release` → verify schema head (do **not** skip)  
- [ ] `manage_deploy.sh deploy full`  
- [ ] `health` / `build-info` / `smoke` / `verify-release` → VERDICT PASS  
- [ ] Spot-check chat smoke with flags OFF (no product regression)

---

## Related

- Audit classification: `docs/releases/RELEASE-ENGINEERING-HARDENING.md`  
- Cursor rule: `.cursor/rules/release-engineering-workflow.mdc`  
- Constitution: `docs/DEVELOPMENT_CHARTER.md`
