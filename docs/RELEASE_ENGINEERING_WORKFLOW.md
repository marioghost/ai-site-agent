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
10. Deploy only from `origin/main` (`manage_deploy.sh deploy full`)  
11. Verify runtime (`manage_deploy.sh verify-release`)  
12. Staging → Production (when release accepts)

---

## Deploy stages (mandatory)

```
backup → build → deploy → verify → restart → smoke
```

`--no-backup-db` is **refused** on release deploy.

## Single entrypoint policy

All future deployment and release-engineering functionality must live under
`deploy/manage_deploy.sh` (CLI or menu).

Do **not** introduce new standalone deploy scripts unless they are
bootstrap/recovery utilities (`install_*.sh`, one-shot cutovers).

## Deploy policy

Deploy **only** from `origin/main` via:

```bash
cd /path/to/ai-site-agent   # on main, clean, synced
sudo bash deploy/manage_deploy.sh deploy full
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
- [ ] `manage_deploy.sh release status` → Deploy readiness OK  
- [ ] `manage_deploy.sh deploy full`  
- [ ] `manage_deploy.sh verify-release` → VERDICT PASS  
- [ ] Spot-check chat smoke with flags OFF (no product regression)

---

## Related

- Audit classification: `docs/releases/RELEASE-ENGINEERING-HARDENING.md`  
- Cursor rule: `.cursor/rules/release-engineering-workflow.mdc`  
- Constitution: `docs/DEVELOPMENT_CHARTER.md`
