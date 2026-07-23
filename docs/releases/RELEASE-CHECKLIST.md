# Release checklist (all RFC releases)

Copy into PR or ops ticket.

## Release readiness tiers

Three **independent** states — see [LIFECYCLE.md](../LIFECYCLE.md) (Engineering Ready → Staging Validated → Production Ready).

| State | Requirement | Blocks |
|-------|-------------|--------|
| **Engineering-ready** | `make release-check` passes | Nothing on next additive RFC step |
| **Staging-validated** | `make deploy` + `make smoke` on Linux server; indexing + chat recorded | **Production-ready** |
| **Production-ready** | Staging-validated + rollback verified + ops sign-off | **Production deployment** |

**Do not mark production-ready without staging-validated.**

**Engineering may continue** (e.g. Release 0.5 / Step 034) while staging validation is pending. **Production deployment** remains blocked until staging-validated. Release 0.4 acceptance: [RELEASE-0.4-ACCEPTANCE-REPORT.md](RELEASE-0.4-ACCEPTANCE-REPORT.md).

---

## Pre-merge (developer / CI)

- [ ] `make release-check` green
- [ ] New migrations have upgrade **and** downgrade
- [ ] Feature flags default **OFF** documented in `docs/FEATURE_FLAGS.md`
- [ ] Rollback runbook updated if schema or flags changed

## Staging (required before production)

- [ ] `make release-check` green (local or CI)
- [ ] `make deploy` succeeds (Linux server, from repo root)
- [ ] Site indexed on staging (see [STAGING-SEED-SMOKE.md](../STAGING-SEED-SMOKE.md))
- [ ] `make smoke` succeeds
- [ ] `GET /api/build` shows expected `release`, `alembic_head`, versions
- [ ] `GET /api/metrics` shows `kos_memory_version`
- [ ] `SMOKE_CHAT=1 make smoke` — chat with Executive **OFF**
- [ ] Executive **ON** experiment documented + rolled back (staging only)
- [ ] Logs reviewed: `sudo journalctl -u ai-agent-backend -n 100 --no-pager`

## Optional (never required for release)

- [ ] `make test-migration` on disposable DB (auto-loaded from repo `.env` if set)
- [ ] Docker build validation — **optional**; `release-check` skips when Docker unavailable
- [ ] Flag-ON cache v2 experiment (`cache_namespace_v2_enabled`) — separate ops ticket

## Production deploy

- [ ] Staging-validated tier achieved
- [ ] `pg_dump` backup taken (`manage_deploy.sh --backup-db`)
- [ ] `alembic upgrade head` on production DB
- [ ] All migration flags **OFF** unless approved
- [ ] `make deploy` or `manage_deploy.sh --mode full`
- [ ] `make smoke` green on production URL
- [ ] Rollback owner identified; [0.x-rollback.md](0.3-rollback.md) reviewed

## Rollback verification

- [ ] Flag OFF rollback tested (`KNOWLEDGE_OS_EXECUTIVE_ENABLED=false` + restart)
- [ ] Settings flags OFF confirmed via `/api/settings`
- [ ] `make smoke` green after rollback
- [ ] `make rollback-staging` checklist reviewed

## Post-deploy verification

- [ ] Dashboard loads; hard refresh if frontend changed
- [ ] No error spike in backend logs (15 min watch)

## Release-specific notes

| Release | Migrations head | Key smoke |
|---------|-----------------|-----------|
| 0.1 | ≤ `0010` | health, golden unit |
| 0.2 | `0011_semantic_diagnostics_v2` | + settings flags present |
| 0.3 | `0013_cache_namespace_v2_enabled` | + `/api/build`, `/api/metrics`, memory_version |

See [DEPLOYMENT.md](../DEPLOYMENT.md) and [STAGING-SEED-SMOKE.md](../STAGING-SEED-SMOKE.md).
