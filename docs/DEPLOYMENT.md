# Deployment & Release Validation

**Engineering delivery guide** — minimum viable pipeline for safe RFC-100 releases.  
This is **not** a Knowledge OS architecture document.

**Stack:** **Primary model — classic Linux deployment:** systemd backend, nginx frontend, host PostgreSQL + Qdrant + Ollama, `deploy/manage_deploy.sh`, and Makefile release commands. **Docker is optional** (validation/CI only) — never required for releases or staging smoke.

---

## 1. Current deployment gap analysis

### What exists today

| Area | Status | Location |
|------|--------|----------|
| Production deploy (systemd + nginx) | **Mature** | `deploy/manage_deploy.sh`, `deploy/deploy.conf` |
| Staging deploy (same tooling) | **Added** | `make deploy-staging` → `manage_deploy.sh --mode update` |
| PostgreSQL setup / backup / migrate | **Mature** | `manage_deploy.sh --action run-migrations`, `check-postgres` |
| Staging tree build (no sudo) | **Partial** | `deploy/prepare_staging.sh` → `install_from_staging.sh` |
| Health probe after deploy | **Basic** | `GET /api/health` in `manage_deploy.sh` |
| Backend unit tests | **Strong** | ~272 RFC migration unit tests |
| Golden chat parity (unit) | **Strong** | 30 queries, legacy vs executive |
| Feature flag docs | **Good** | `docs/FEATURE_FLAGS.md` |
| Per-release rollback runbooks | **Good** | `docs/releases/0.*-rollback.md` |

### Critical gaps (before this pipeline)

| Gap | Risk | Mitigation added |
|-----|------|------------------|
| **No CI workflow** | Regressions merge undetected | `.github/workflows/release-test.yml` |
| **No unified `make test`** | Inconsistent local/CI commands | `Makefile` |
| **No repeatable staging deploy command** | Releases validated only ad hoc | `make deploy-staging` |
| **No post-deploy smoke script** | `/api/metrics`, settings, chat untested after deploy | `scripts/release/smoke-staging.sh` |
| **No migration rollback smoke** | Alembic failures found in production | `make test-migration` (disposable DB only) |
| **No release checklist artifact** | Ops steps scattered across reports | `RELEASE-CHECKLIST.md` |
| **Release marked READY without staging run** | False confidence | Updated 0.3 acceptance gate |

### Honest assessment

**There was no reliable staging/deploy test path** before this work. Production operators had `manage_deploy.sh`, but:

- No automated gate tied to git push
- No documented staging server workflow separate from production
- Smoke tests stopped at `/api/health` (no metrics, settings, chat)
- Release acceptance reports recorded **unit test PASS** but marked staging ops as **PENDING**

**Releases should not be treated as production-ready until `make smoke-staging` passes on a real Linux staging server.**

---

## 2. Minimum deployment architecture

### Environments

| Environment | Purpose | How |
|-------------|---------|-----|
| **Local** | Developer iteration | `backend/.venv`, `dashboard npm run dev`, host Postgres/Qdrant/Ollama |
| **Test / CI** | Automated gate on every PR | GitHub Actions: unit + dashboard + migration on Postgres service |
| **Staging** | Pre-production release validation | Linux VPS: `make deploy-staging` → `manage_deploy.sh --mode update` |
| **Production** | Live traffic | Same stack at `/opt/ai-site-agent` via `manage_deploy.sh` |

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────┐     ┌──────────────┐
│  Local dev  │────▶│  CI (GitHub) │────▶│  Staging (Linux VPS)│────▶│  Production  │
│  make test  │     │  make test   │     │ deploy-staging      │     │ manage_deploy│
└─────────────┘     │  migration   │     │ smoke-staging       │     │ systemd/nginx│
                    └──────────────┘     └─────────────────────┘     └──────────────┘
```

### Staging stack (Linux server)

| Component | Service | Notes |
|-----------|---------|-------|
| Backend | `ai-agent-backend` (systemd) | FastAPI on port 8000 |
| Dashboard | nginx static | Built via `npm run build` during deploy |
| PostgreSQL | host install | Separate DB e.g. `ai_site_agent_staging` |
| Qdrant | `qdrant` (systemd) | Port 6333 |
| Ollama | `ollama` (systemd) | Port 11434; required for chat smoke |

Install dependencies on a fresh staging VPS:

```bash
sudo bash deploy/manage_deploy.sh --action install-postgres
sudo bash deploy/manage_deploy.sh --action setup-postgres-db
# Qdrant/Ollama: see deploy/install_qdrant.sh, deploy/install_ollama.sh
```

### Background workers

Started inside backend process lifespan:

- `cache_cleanup_worker`
- `analytics_aggregation_worker`
- Indexing runs via API/worker (optional `WORKER_SERVICE_NAME` in deploy config)

Same as production — no separate worker service.

---

## 3. How each release is tested

| Layer | Command | Requires |
|-------|---------|----------|
| **Release gate** | `make release-check` | venv + node; optional `POSTGRES_TEST_URL`; Docker **optional** |
| Backend unit | release-check step 1 | Python venv |
| Golden parity | release-check step 2 | — |
| Dashboard vitest/tsc/build | release-check steps 3–5 | Node 18+ |
| Migration (disposable DB) | release-check step 6 if `POSTGRES_TEST_URL` | Postgres |
| Docker validate | release-check step 7 if `docker` installed | **Optional — SKIP if unavailable; never blocks release** |

### Deployment policy

| Policy | Detail |
|--------|--------|
| **Primary release path** | Linux VPS: systemd + nginx + host Postgres/Qdrant/Ollama via `deploy/manage_deploy.sh` |
| **Public operator entry** | `bash deploy/manage_deploy.sh <command>` only (`help` for syntax) |
| **Schema-first cutover** | `status` → `backup db` → `migrate release` → verify schema head → `deploy full` → `health` → `build-info` → `smoke` → `verify-release` (see [RELEASE-CHECKLIST.md](releases/RELEASE-CHECKLIST.md)) |
| **Migrate commands** | `migrate` / `migrate live` = live `/opt` tree only; `migrate release` = only supported schema-first path (clean **origin/main** worktree → live `/opt` DB) |
| **`deploy full` + Alembic** | Still runs post-sync `run_migrations` (idempotent no-op after successful `migrate release`; defense-in-depth; not a substitute for schema-first) |
| **Makefile gates** | `make release-check` (CI/dev). Do **not** use Makefile as the public deploy workflow |
| **Docker role** | Optional validation/staging path (`deploy/Dockerfile.validate`, CI). Not the production architecture |
| **Do not** | Redesign deployment around Docker; require Docker for releases; block staging validation when Docker is missing; use ad-hoc DEV_CHECKOUT migrate; skip `migrate release` when `/opt` lacks required migrations; use `deploy full` → bare `migrate` |

---
| Staging deploy | `make deploy` | Linux server + sudo |
| Staging smoke | `make smoke` | Running backend |
| Rollback verify | `make rollback-staging` + re-smoke | systemd |

See [STAGING-SEED-SMOKE.md](STAGING-SEED-SMOKE.md) for admin, indexing, chat (Executive ON/OFF).

### Staging smoke covers

- `GET /api/health`
- `GET /api/build` (commit, alembic head, flags, versions)
- `GET /api/metrics` (Prometheus)
- `GET /api/metrics/operational` (JSON)
- `POST /api/auth/login` + `GET /api/settings`
- Golden unit parity (local, in smoke script)
- Optional: `SMOKE_CHAT=1` → `POST /api/chat` (needs Ollama + indexed site)

---

## 4. Release commands (Makefile)

Run from **repo root** (`~/projects/ai-site-agent`), not `backend/`:

```bash
make release-check         # full pre-release gate (recommended)
make test                  # backend unit + dashboard (quick)
make deploy                # deploy checkout → /opt/ai-site-agent
make smoke                 # HTTP smoke tests
make deploy-smoke          # deploy + smoke
make test-migration        # alembic up/down/up (POSTGRES_TEST_URL)
make migrate               # alembic upgrade head (DATABASE_URL)
make rollback-staging      # rollback checklist
```

### Single-machine dev (WSL) note

If `deploy/deploy.local.conf` points at `/opt/ai-site-agent` for normal dev deploys,
`make deploy-staging` **ignores** it and uses `deploy/deploy.staging.local.conf` instead.

Alternatively, use the same path for both and run `sudo bash deploy/sync_to_opt.sh` for production deploy.

```bash
# 1. On staging VPS — install stack (once)
sudo bash deploy/manage_deploy.sh --action install-postgres
sudo bash deploy/manage_deploy.sh --action setup-postgres-db

# 2. Configure staging paths
cp deploy/deploy.staging.local.conf.example deploy/deploy.staging.local.conf
# Edit PROJECT_ROOT, ENV_FILE paths

# 3. Create staging .env on server
make init-staging
# Edit /opt/ai-site-agent-staging/.env — DATABASE_URL, JWT_SECRET_KEY, passwords

# 4. From dev checkout (SSH to staging or run locally if same machine)
cp .env.staging.example .env.staging   # smoke credentials
make deploy-staging
make smoke-staging

# Optional chat smoke (Ollama running with models pulled):
SMOKE_CHAT=1 make smoke-staging
```

### Production deploy (unchanged)

```bash
cd /opt/ai-site-agent
sudo bash deploy/manage_deploy.sh --mode full --yes
curl -sf http://127.0.0.1:8000/api/health
make smoke-staging STAGING_BASE_URL=http://127.0.0.1:8000
```

---

## 5. Exact commands per release

### Release 0.1 (Steps 001–012)

```bash
make test-backend
cd backend && .venv/bin/alembic upgrade head   # through 0010 on that tag
# Flags: KNOWLEDGE_OS_EXECUTIVE_ENABLED=false
make deploy-staging && make smoke-staging
```

### Release 0.2 (Steps 013–019)

```bash
make release-check
cd backend && .venv/bin/alembic upgrade head   # through 0011
# Flags OFF: KNOWLEDGE_OS_EXECUTIVE_ENABLED, enable_semantic_diagnostics_v2
make deploy-staging && make smoke-staging
```

### Release 0.3 (Steps 020–026)

```bash
make release-check
make test-migration   # disposable DB in CI; not on live staging DB
make deploy-staging && make smoke-staging
curl -s http://127.0.0.1:8000/api/metrics | grep kos_memory_version
curl -s http://127.0.0.1:8000/api/metrics/operational
# Flags OFF: all migration flags (see FEATURE_FLAGS.md)
```

---

## 6. Release checklist

Use before marking any RFC release **production-ready**:

- [ ] `make test` green locally or in CI
- [ ] `make test-migration` green on disposable DB (CI)
- [ ] `alembic upgrade head` applied on staging
- [ ] Migration flags default **OFF** unless explicitly approved for staging experiment
- [ ] `make smoke-staging` green
- [ ] Rollback runbook read (`docs/releases/0.x-rollback.md`)
- [ ] Logs visible: `sudo journalctl -u ai-agent-backend -n 100 --no-pager`
- [ ] Metrics visible: `GET /api/metrics` shows expected gauges
- [ ] Optional: `SMOKE_CHAT=1` with Ollama for end-to-end chat path

Template: [docs/releases/RELEASE-CHECKLIST.md](releases/RELEASE-CHECKLIST.md)

---

## 7. Rollback checklist

### Immediate (no redeploy)

| Action | Command |
|--------|---------|
| Disable Executive | `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false` + restart backend |
| Disable semantic diagnostics v2 | Settings `enable_semantic_diagnostics_v2=false` |
| Disable cache namespace v2 | Settings `cache_namespace_v2_enabled=false` |
| Clear caches if needed | Admin `POST /api/settings/cache/clear-all` |

### Application rollback

| Environment | Action |
|-------------|--------|
| Staging / Production | `git checkout <previous-tag>` then `sudo bash deploy/manage_deploy.sh --mode update --yes` |
| Prebuilt tree | `bash deploy/prepare_staging.sh && sudo bash deploy/install_from_staging.sh` |

### Migration rollback policy

| Policy | Detail |
|--------|--------|
| **Preferred** | Leave additive columns; disable flags |
| **Allowed** | `alembic downgrade` on disposable staging DB only, with backup |
| **Production downgrade** | Requires explicit ops approval + `pg_dump` backup |

See per-release: `docs/releases/0.1-rollback.md`, `0.2-rollback.md`, `0.3-rollback.md`.

### Emergency env override

`KNOWLEDGE_OS_EXECUTIVE_ENABLED=false` — only migration env kill-switch in 0.3; Settings flags cover cache/diagnostics.

---

## 8. Files in this pipeline

| Path | Role |
|------|------|
| `Makefile` | Unified release commands (repo root) |
| `deploy/manage_deploy.sh` | Linux deploy & ops manager |
| `deploy/deploy.staging.local.conf.example` | Staging server path overrides |
| `.env.staging.example` | Staging env + smoke credentials template |
| `scripts/release/*.sh` | Test, deploy, smoke, rollback scripts |
| `.github/workflows/release-test.yml` | CI: unit + dashboard + migration |
| `docs/DEPLOYMENT.md` | This document |
| `docs/releases/RELEASE-CHECKLIST.md` | Printable checklist |

---

## 9. Recommendation: Release 0.3 acceptance

| Question | Answer |
|----------|--------|
| Is engineering complete for 0.3? | **Yes** — Steps 020–026 delivered |
| Is CI gate in place? | **Yes** — after merging this pipeline |
| Has staging smoke been run? | **Operator must run** `make deploy-staging && make smoke-staging` on Linux server |
| Can 0.3 deploy to production today? | **No** — staging-validated required |
| Can Step 027 (claim tables) start? | **Yes** — Engineering Ready ([LIFECYCLE.md](LIFECYCLE.md)) |

**Release stance:** Release 0.3 is **engineering-ready** but **not production-ready** until staging-validated.

---

## Cross-references

- Production ops: `deploy/manage_deploy.sh`, `deploy/OLLAMA.md`
- Feature flags: `docs/FEATURE_FLAGS.md`
- Release reports: `docs/releases/RELEASE-0.*-ACCEPTANCE-REPORT.md`
- Memory version: `docs/MEMORY_VERSION.md`
