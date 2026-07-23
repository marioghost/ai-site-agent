# Release 0.3 Acceptance Report

**Knowledge OS Migration — RFC-100**  
**Release theme:** Epistemic Memory substrate (`memory_version`, cache namespace v2, operational metrics)  
**Report date:** 2026-07-05  
**Steps completed:** 020–026  
**Flag defaults at release:** `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false`, `enable_semantic_diagnostics_v2=false`, `cache_namespace_v2_enabled=false`

This document closes Release 0.3 engineering deliverables and records the **first readiness assessment** for persistent Epistemic Memory (Release 0.4+). It establishes the baseline before claim storage enters the codebase.

---

## 1. Release summary

### Theme

Introduce a **parallel revision counter** for epistemic memory (`memory_version`), sole-authority services, operator controls, cache-namespace integration (flag-gated), invariant validation, and observability — **without** changing production chat, retrieval, cache, or Executive behavior while flags remain OFF.

### Step completion matrix

| Step | Title | Status |
|------|-------|--------|
| **020** | `memory_version` schema substrate | ✅ |
| **021** | `MemoryVersionService` | ✅ |
| **022** | Manual admin memory bump API | ✅ |
| **023** | `cache_namespace_v2_enabled` + namespace integration | ✅ |
| **024** | Cache namespace v2 invariant tests | ✅ |
| **025** | Operational metrics (`kos_memory_version` gauge) | ✅ |
| **026** | Release 0.3 acceptance report | ✅ |

### What each step contributed

| Step | Platform contribution |
|------|------------------------|
| **020** | Additive DB column `settings.memory_version` (default `1`); ORM + read-only `SettingsRead` exposure. Establishes the **persistence substrate** for future claim revisions without wiring runtime behavior. |
| **021** | **`MemoryVersionService`** as sole authority for read/write of `memory_version` (`get`, `ensure_initialized`, `bump`). Defines the integration point for future claim integration, consolidation, and cache v2. |
| **022** | Admin-only **`POST /api/settings/memory-version/bump`** operational stub. Operators can validate revision counter and (when flag ON) cache invalidation before automatic bumps exist. |
| **023** | **`cache_namespace_v2_enabled`** flag (default OFF). When ON, `build_retrieval_namespace(..., db)` includes `memory_version` via `MemoryVersionService.get()`. When OFF, namespace is **bit-identical** to pre-0.3. |
| **024** | **Architectural proof** that cache invalidation is namespace-driven; cache layer remains version-aware but not memory-aware. Property + static negative tests guard against multiple writers and direct settings reads. |
| **025** | **`GET /api/metrics`** (Prometheus) and **`GET /api/metrics/operational`** (JSON). Read-only gauges `kos_memory_version` and `kos_knowledge_version` for operators. |
| **026** | This report — closes 0.3 and assesses Epistemic Memory readiness. |

### What intentionally did NOT change

| Area | Status |
|------|--------|
| Chat / retrieval / LLM / Executive hot path | Unchanged |
| Cache storage, TTL, lookup algorithms | Unchanged |
| Automatic `memory_version` bumps | Not implemented (Step 031+) |
| Epistemic Memory tables / claims / evidence | Not started (Step 027+) |
| Claim extraction / shadow writes | Not started (Steps 029–030) |
| Dashboard UI for memory_version | Not required (API/metrics only) |
| Production cache keys (flag OFF) | Identical to Release 0.2 |
| Golden query set | Unchanged (30 queries) |

---

## 2. Memory readiness

Assessment of Epistemic Memory **substrate** readiness (not full memory system).

| Component | Status | Notes |
|-----------|--------|-------|
| **`memory_version` substrate** | **Implemented** | Migration `0012`; column NOT NULL default `1`; read-only in Settings API update payload. |
| **`MemoryVersionService`** | **Implemented** | Sole writer; `get` / `ensure_initialized` / `bump`; tested including monotonicity and cross-version isolation. |
| **Manual bump (Step 022)** | **Implemented** | `POST /api/settings/memory-version/bump`; admin-only; returns previous/new version + reason echo. |
| **Cache namespace v2** | **Partially implemented** | Flag-gated namespace inclusion **implemented** and invariant-tested. RFC-100 also describes **dual-read** (try v2 then v1 key on lookup) — **not implemented**; deferred (not required for 0.3 ship with flag OFF). |
| **Operational metrics** | **Implemented** | `kos_memory_version` / `kos_knowledge_version` gauges; read-only via version services. |

### Readiness interpretation

Release 0.3 delivers everything needed to **observe** and **manually advance** the epistemic revision counter and to **invalidate caches by namespace** when operators opt in (`cache_namespace_v2_enabled=true`). It does **not** deliver persistent claims, extraction, or automatic bump-on-write — those are explicitly Release 0.4.

**Substrate verdict:** Ready for Engineering Ready acceptance. Step 027 may proceed in parallel with staging ops (see [LIFECYCLE.md](../LIFECYCLE.md)).

---

## 3. Operational readiness

| Area | Status | Detail |
|------|--------|--------|
| **Deployment** | ✅ Documented | Migrations `0012`, `0013`; `alembic upgrade head` required. See `docs/releases/0.3-step-020-deploy.md`, `0.3-step-023-cache-namespace-v2.md`, `0.3-step-025-metrics.md`. |
| **Rollback** | ✅ Documented | `docs/releases/0.3-rollback.md` — flag OFF restores legacy behavior; downgrade paths documented per migration. |
| **Feature flags** | ✅ | `cache_namespace_v2_enabled` in `docs/FEATURE_FLAGS.md`; default **false**; no restart required to disable. |
| **Metrics** | ✅ | `/api/metrics`, `/api/metrics/operational`; unauthenticated (same pattern as `/api/health`). |
| **Tests** | ✅ | **272 passed** RFC migration unit suite (recorded 2026-07-05); includes 0.3 memory, cache v2, invariant, and metrics tests. |
| **Migration safety** | ✅ | Both migrations additive; server defaults preserve existing rows; downgrade drops columns only. |

### Validation commands

```bash
cd backend
.venv/bin/alembic upgrade head

.venv/bin/pytest \
  tests/test_broad_query_handling.py \
  tests/test_retrieval_hybrid.py \
  tests/test_legacy_guards.py \
  tests/test_document_first_retrieval.py \
  tests/test_boilerplate_retrieval.py \
  tests/test_golden_chat_parity.py \
  tests/test_golden_queries_schema.py \
  tests/test_chat_executive_routing.py \
  tests/test_chat_stream_executive_routing.py \
  tests/test_executive_service.py \
  tests/test_chat_dispatch_logging.py \
  tests/test_retrieval_pipeline_v2.py \
  tests/test_semantic_diagnostics_schema.py \
  tests/test_chat_response_builder.py \
  tests/test_knowledge_profile_preset_deprecation.py \
  tests/test_memory_version_schema.py \
  tests/test_memory_version_service.py \
  tests/test_memory_version_bump_api.py \
  tests/test_cache_namespace_v2.py \
  tests/test_cache_namespace_v2_invariants.py \
  tests/test_operational_metrics.py \
  tests/test_caching.py \
  -m unit -q
```

### Optional / deferred (ops)

| Validation | Status |
|------------|--------|
| Staging: `cache_namespace_v2_enabled` ON + manual bump → cache miss | **PENDING OPS** |
| Staging: scrape `/api/metrics` into monitoring | **PENDING OPS** |
| HTTP golden integration (`GOLDEN_CHAT_LIVE=1`) | SKIPPED — requires `POSTGRES_TEST_URL` |
| Staging Executive + semantic diagnostics (0.1 / 0.2 carryover) | **PENDING OPS** |

---

## 4. Architecture health (Release 0.2 → Release 0.3)

| Metric | Release 0.2 | Release 0.3 | Δ |
|--------|-------------|-------------|---|
| RFC migration unit tests | 131 | **272** | +141 |
| Golden smoke queries | 30 | **30** | — |
| Golden tests (schema + parity) | 40 | **40** | — |
| Dashboard unit tests | 27 | **27** | — |
| Active migration feature flags | 2 | **3** | +`cache_namespace_v2_enabled` |
| DB migrations (RFC-100 cumulative) | 1 (`0011`) | **3** (`0011`–`0013`) | +2 additive |
| New production services | — | **`MemoryVersionService`**, **`OperationalMetricsService`** | Substrate + observability |
| New API surfaces | KP deprecation header | **`/api/settings/memory-version/bump`**, **`/api/metrics`**, **`/api/metrics/operational`** | Ops-only |
| Deleted legacy code | — | **None** | Substrate release |
| Production chat behavior (flags OFF) | ≡ 0.1 | **≡ 0.2 ≡ 0.1** | Unchanged |
| Cache namespace (flag OFF) | Pre-0.3 | **Identical** | Proven by Step 024 |

### Technical debt removed (0.3)

| Item | Notes |
|------|-------|
| No parallel memory revision counter | **`memory_version` column + service** |
| No operator visibility into memory revision | **Metrics + manual bump API** |
| Undocumented cache/memory boundary | **Step 024 invariants + MEMORY_VERSION.md** |

### Technical debt remaining (carried forward)

| Item | Severity | Target (RFC-100) |
|------|----------|------------------|
| No persistent Epistemic Memory (claims, evidence) | **High** | Release 0.4 (Steps 027–033) |
| No automatic memory bump on claim writes | Expected | Step 031 |
| Cache namespace dual-read (v2 then v1) | Low | Not scheduled in 0.3; optional hardening |
| `understanding_trace` stub only | Expected | Release 0.6 ReasoningService |
| Executive passthrough only | Medium | Release 0.6 |
| `RagService` / RPS god classes | High | Release 0.6 split |
| KP presets still functional | Medium | Release 0.8 deprecation |
| Row-level lock on version bumps | Low | Same as `knowledge_version` |

### Boundaries respected (0.3)

| Check | Status |
|-------|--------|
| Single writer for `memory_version` | ✅ `MemoryVersionService` only |
| Cache code does not call `bump()` | ✅ Static tests (Step 024) |
| Flag OFF → zero cache key change | ✅ Tested |
| Chat / retrieval / Executive unchanged | ✅ Golden parity unchanged |
| No claim tables or shadow writes | ✅ |

---

## 5. Remaining blockers before Epistemic Memory

These items are **missing by design** until Release 0.4. They block **using** epistemic memory in production, not **starting** Step 027 schema work.

| Blocker | RFC step | Status |
|---------|----------|--------|
| Epistemic memory tables (`observation_ref`, `claim`, `evidence_link`) | **027** | Not started |
| `EpistemicMemoryService` read API | **028** | Not started |
| `ClaimExtractionFromSI` mapper (SI → claim proposals) | **029** | Not started |
| Post-SI shadow write hook (`memory_shadow_write_enabled`) | **030** | Not started |
| Auto-bump `memory_version` on shadow claim integrate | **031** | Not started |
| Claim roundtrip / provenance tests | **032** | Not started |

**Not blockers for Step 027** (later releases per roadmap):

- ReasoningService extraction (Release 0.6)
- Tension surfacing (Release 0.5)
- Memory-assisted evidence routing (Release 0.7)

**0.3 substrate is sufficient** to add additive memory tables without retrofits to version ownership or cache namespace design.

---

## 6. Release decision

## 7. Release readiness tiers

| State | Status | Gates |
|-------|--------|-------|
| **Engineering-ready** | **✅ ACCEPTED** | Steps 020–026; `make release-check` |
| **Staging-validated** | **⏳ PENDING OPS** | See §8 validation log |
| **Production-ready** | **❌ NOT YET** | Requires staging-validated |

State model: [LIFECYCLE.md](../LIFECYCLE.md) — engineering and operations are **independent tracks**.

### Engineering-complete criteria (met)

Release 0.3 engineering deliverables are complete. Ship configuration:

- `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false`
- `enable_semantic_diagnostics_v2=false`
- `cache_namespace_v2_enabled=false` (DB default after `0013`)
- Run `alembic upgrade head` before deploy (revisions through `0013_cache_namespace_v2_enabled`)

Production behavior remains equivalent to Release 0.2 (and 0.1 for chat). New surfaces are **operator-only** (manual bump, metrics, `/api/build`) or **inactive until flagged** (cache namespace v2).

### Release pipeline (added post-0.3 acceptance)

| Artifact | Role |
|----------|------|
| `make release-check` | Pre-release gate (unit, golden, dashboard, optional migration/docker) |
| `make deploy` / `make smoke` | Linux server deploy + HTTP smoke |
| `GET /api/build` | Build metadata (commit, alembic head, flags, versions) |
| [STAGING-SEED-SMOKE.md](../STAGING-SEED-SMOKE.md) | Admin, indexing, chat smoke plan |

### Conditions (non-blocking for engineering acceptance)

| Item | Owner | When |
|------|-------|------|
| Apply migrations `0012`, `0013` on all environments | Ops | Deploy |
| Staging: `make release-check` + `make deploy-smoke` | Ops | Before **production deployment** |
| Staging: Executive ON/OFF chat smoke recorded | Ops | Before **production deployment** |
| Staging: scrape `/api/metrics` into monitoring | Ops | Before prod flag experiments |

### Blocking issues

**None** for **engineering-complete** acceptance with default flags OFF.

**Staging gate (required before production deployment):** Complete staging-validated tier per [STAGING-SEED-SMOKE.md](../STAGING-SEED-SMOKE.md). Do **not** mark production-ready until recorded. Does **not** block Step 027 engineering (additive, flags OFF).

---

## 7. Recommendation

### Engineering acceptance: **GRANTED**

Release 0.3 Steps 020–026 are **engineering-ready**.

### Step 027 — engineering may proceed

Step 027 (Epistemic Memory tables) is **additive schema with flags OFF** per RFC-100. It may begin when:

1. `make release-check` passes (engineering gate)
2. Step 026 accepted (this report)

**Staging validation is not a prerequisite for Step 027 development.** It is a prerequisite for **production deployment** of Release 0.3 and for **production-ready** sign-off.

### Production deployment — blocked until staging-validated

Production deployment of Release 0.3 remains **blocked** until:

1. **Staging-validated** tier achieved (`make deploy-smoke` + indexing + chat smoke)
2. Rollback procedure reviewed ([0.3-rollback.md](0.3-rollback.md))
3. [RELEASE-CHECKLIST.md](RELEASE-CHECKLIST.md) complete

Infrastructure issues (sudo, staging unavailable) delay **production**, not **engineering**.

### Current gates

| Gate | Status |
|------|--------|
| Engineering-ready (020–026) | **✅ ACCEPTED** |
| Step 027 engineering start | **✅ ALLOWED** |
| Staging-validated | **⏳ Pending ops** |
| Production-ready / production deploy | **❌ Blocked until staging-validated** |

**Suggested gate before Step 030 (shadow writes):** complete Steps 027–029 and `032` claim roundtrip tests; keep `memory_shadow_write_enabled=false` until proven in staging.

---

## 8. Operational validation log

**Recorded:** 2026-07-05 (automated attempt + live endpoint probe)  
**Environment:** WSL dev host, `/opt/ai-site-agent` (single-machine staging)  
**Operator:** CI/automation session (non-interactive — no sudo password)

### Summary

| Step | Result | Notes |
|------|--------|-------|
| `make release-check` | **✅ PASS** | 7 steps; migration skipped (no `POSTGRES_TEST_URL`); Docker skipped (not installed) |
| `make deploy-smoke` | **❌ BLOCKED** | `sudo` password required — deploy did not run |
| Seed/index fixture site | **⏳ NOT RUN** | Blocked on deploy + admin auth |
| `SMOKE_CHAT=1 make smoke` | **⏳ NOT RUN** | Blocked on auth |
| Executive ON/OFF + rollback | **⏳ NOT RUN** | Blocked on deploy + auth |

**Staging-validated tier: NOT ACHIEVED.** **Production deployment blocked.** Step 027 engineering is **not blocked** (see [LIFECYCLE.md](../LIFECYCLE.md)).

### `make release-check` (2026-07-05T18:24:18Z)

| Step | Result |
|------|--------|
| Backend unit tests | PASS |
| Golden parity | PASS (40 tests) |
| Dashboard vitest | PASS (27 tests) |
| TypeScript check | PASS |
| Dashboard build | PASS |
| Migration test | SKIP — `POSTGRES_TEST_URL` not set |
| Docker build | SKIP — docker not installed |

### `make deploy-smoke`

```
sudo: a terminal is required to read the password
make deploy-smoke → exit 2
```

**Action required (operator):** run interactively on the host:

```bash
cd ~/projects/ai-site-agent
make deploy-smoke
```

This rsyncs current checkout (including `GET /api/build`) to `/opt/ai-site-agent`.

### Live endpoint probe (pre-redeploy stack at `/opt`)

Backend was **running** from prior deploy. Probed at `http://127.0.0.1:8000`.

#### `GET /api/health` — **✅ PASS**

```json
{
  "app": {"status": "ok", "detail": "Backend running"},
  "ollama": {"status": "ok", "detail": "Ollama reachable"},
  "qdrant": {"status": "ok", "detail": "Qdrant reachable"},
  "database": {
    "status": "ok",
    "migration_version": "0013_cache_namespace_v2_enabled",
    "engine": "PostgreSQL",
    "latency_ms": 0.56
  }
}
```

#### `GET /api/build` — **❌ FAIL (404)**

Deployed artifact predates build-metadata hardening. Endpoint not present until `make deploy` succeeds.

Expected after redeploy: `release`, `git_commit`, `build_time`, `alembic_head`, `memory_version`, `knowledge_version`, `feature_flags`.

#### `GET /api/metrics` — **✅ PASS**

```
kos_memory_version 1
kos_knowledge_version 24
```

#### `GET /api/metrics/operational` — **✅ PASS**

```json
{"memory_version": 1, "knowledge_version": 24}
```

#### `POST /api/auth/login` — **❌ FAIL (401)**

```
{"detail":"Invalid username or password"}
```

Default seed password (`admin` / `фвьшт`) does **not** match this database — admin password was changed after first login. Smoke scripts need the live admin password:

```bash
export STAGING_ADMIN_USER=admin
export STAGING_ADMIN_PASSWORD='<your-admin-password>'
make smoke
```

#### `POST /api/chat` (Executive OFF) — **⏳ NOT RUN**

Blocked on auth token. After auth fix + indexed site:

```bash
SMOKE_CHAT=1 make smoke
```

#### `POST /api/chat` (Executive ON) — **⏳ NOT RUN**

Requires redeploy with env change + restart:

```bash
# /opt/ai-site-agent/.env
KNOWLEDGE_OS_EXECUTIVE_ENABLED=true
sudo systemctl restart ai-agent-backend
SMOKE_CHAT=1 make smoke
# Rollback:
KNOWLEDGE_OS_EXECUTIVE_ENABLED=false
sudo systemctl restart ai-agent-backend
make smoke
```

See [STAGING-SEED-SMOKE.md](../STAGING-SEED-SMOKE.md) §5–6.

#### Rollback verification — **⏳ NOT RUN**

Documented in [0.3-rollback.md](0.3-rollback.md). Run after Executive ON experiment.

#### Golden unit parity (in smoke script) — **✅ PASS**

40 golden tests passed locally during `make smoke`.

### Ops checklist to close staging-validated

- [ ] `make deploy-smoke` (interactive sudo) — deploys `/api/build` + latest code
- [ ] Set `STAGING_ADMIN_PASSWORD` to live admin password
- [ ] Index fixture site per [STAGING-SEED-SMOKE.md](../STAGING-SEED-SMOKE.md)
- [ ] `SMOKE_CHAT=1 make smoke` — Executive OFF
- [ ] Executive ON experiment + rollback to OFF + re-smoke
- [ ] Update this section with PASS/FAIL and timestamps
- [ ] Achieve **staging-validated** → enables **production-ready** review
- [ ] Step 027 engineering may proceed in parallel (not gated by this checklist)

---

## Appendix A — Ship configuration summary

```bash
# Environment
KNOWLEDGE_OS_EXECUTIVE_ENABLED=false

# Settings (DB defaults after migrations)
enable_semantic_diagnostics_v2=false
cache_namespace_v2_enabled=false

# Deploy
cd backend && .venv/bin/alembic upgrade head
```

## Appendix B — New test files (0.3)

| File | Focus |
|------|-------|
| `tests/test_memory_version_schema.py` | Step 020 schema |
| `tests/test_memory_version_service.py` | Step 021 service |
| `tests/test_memory_version_bump_api.py` | Step 022 API |
| `tests/test_cache_namespace_v2.py` | Step 023 flag behavior |
| `tests/test_cache_namespace_v2_invariants.py` | Step 024 invariants |
| `tests/test_operational_metrics.py` | Step 025 metrics |
| `tests/test_build_info.py` | Release hardening `/api/build` |

## Appendix D — Build metadata (`GET /api/build`)

Added in release pipeline hardening (post-0.3 acceptance):

| Field | Source |
|-------|--------|
| `release` / `app_version` | `.build-info.json` (written on deploy) or default `0.3` |
| `git_commit` | `.build-info.json` or `GIT_COMMIT` env |
| `build_time` | `.build-info.json` or `BUILD_TIME` env |
| `alembic_head` | Live DB revision |
| `memory_version` / `knowledge_version` | Version services |
| `feature_flags` | Env + Settings migration flags |

Unauthenticated (same as `/api/health`). Used by `make smoke` and ops verification.

## Appendix C — Cross-references

| Document | Role |
|----------|------|
| `docs/MEMORY_VERSION.md` | Memory vs knowledge version; cache invariants; metrics |
| `docs/FEATURE_FLAGS.md` | `cache_namespace_v2_enabled` |
| `docs/releases/0.3-rollback.md` | Deploy & rollback |
| `docs/releases/RELEASE-0.2-ACCEPTANCE-REPORT.md` | Prior release baseline |
| `docs/DEPLOYMENT.md` | Staging pipeline, smoke tests, release gates |
| `docs/LIFECYCLE.md` | Project-wide capability lifecycle |
| `docs/STAGING-SEED-SMOKE.md` | Admin, indexing, chat smoke plan |
| `docs/releases/RELEASE-CHECKLIST.md` | Pre-production checklist |
| `docs/RFC-100-PRODUCTION-MIGRATION-STRATEGY.md` | Full roadmap |

---

**End of Release 0.3 acceptance report.**
