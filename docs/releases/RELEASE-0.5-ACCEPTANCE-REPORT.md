# Release 0.5 Acceptance Report

**Knowledge OS Migration — RFC-100**  
**Release theme:** Tension Surfacing (read-only epistemic hypotheses — detection, admin API, Understanding panel, metrics)  
**Report date:** 2026-07-27  
**Steps completed:** 034–038  
**Governance:** [ADR-0002 Tension Taxonomy Ownership](../adr/0002-tension-taxonomy-ownership.md)  
**Flag defaults at release:** Unchanged from Release 0.4 — all migration flags **OFF**, including `memory_shadow_write_enabled=false`. No new runtime feature flag required for Tension Surfacing (admin auth gates API/UI).

This document closes Release 0.5 engineering deliverables and records readiness for Release 0.6 (ReasoningService extraction).

---

## 1. Release summary

### Theme

Make **possible Epistemic Memory problems** observable to administrators and operators as **epistemic hypotheses** (tensions) — without persistence, maintenance execution, reasoning integration, or chat/retrieval changes.

A Tension is **not** knowledge, belief, or fact.

### Step completion matrix

| Step | Title | Status |
|------|-------|--------|
| **034** | `TensionSurfacingService` — `support_deficit` + `conflict` | ✅ |
| **035** | `GET /api/understanding/tensions` (admin, read-only) | ✅ |
| **036** | Understanding / Epistemic Health dashboard panel | ✅ |
| **037** | Operational gauges `kos_*_tensions` | ✅ |
| **038** | Release 0.5 acceptance report | ✅ |

### What each step contributed

| Step | Platform contribution |
|------|------------------------|
| **034** | Conservative in-memory detection via Epistemic Memory reads; cognitive acceptance suite |
| **035** | Admin JSON API with provenance DTOs; pagination; no ORM exposure |
| **036** | Admin Understanding panel — summary, filter, expand, copy JSON; uncertainty wording EN/UK |
| **037** | `summarize_counts()` + Prometheus/JSON gauges; bounded scan |
| **038** | This report + ADR-0002 + maturity / metrics-bound docs |

### What intentionally did NOT change

| Area | Status |
|------|--------|
| Chat / retrieval / LLM / Executive hot path | Unchanged |
| TensionSurfacingService detection rules after acceptance | Frozen for 0.5 |
| Tension persistence | **Not implemented** |
| Maintenance / investigation planning | **Not implemented** |
| Reasoning consumption of memory or tensions | **Not implemented** |
| New tension types beyond v1 subset | **Not added** |
| Alembic head | Still `0015_memory_shadow_write_enabled` (no 0.5 schema) |

---

## 2. Cognitive Architecture alignment

Reviewed against [KNOWLEDGE_OS_ARCHITECTURE_v1.md](../KNOWLEDGE_OS_ARCHITECTURE_v1.md), [COGNITIVE_ARCHITECTURE.md](../COGNITIVE_ARCHITECTURE.md), [TENSION_SURFACING.md](../TENSION_SURFACING.md).

| Principle | Release 0.5 status |
|-----------|-------------------|
| Tension as hypothesis, not fact | ✅ Docs, API, UI, metrics wording |
| Epistemic Memory remains passive for reasoning | ✅ Verified — no chat/retrieval consumption |
| Detection ownership | ✅ [ADR-0002](../adr/0002-tension-taxonomy-ownership.md) — `TensionSurfacingService` sole taxonomy owner |
| Consumers only (dashboard / metrics) | ✅ No parallel taxonomies |
| Maintenance does not invent types | ✅ Maintenance not shipped; ownership rule preemptive |
| Conservative detection | ✅ Acceptance suite T-01…T-09 |

**Verdict:** Release 0.5 matches frozen architecture for **read-only tension observability**. Maintenance and belief revision remain future work.

---

## 3. Behavioral verification

| Check | Verified |
|-------|----------|
| Admin-only tensions API (401/403) | ✅ |
| Empty memory → no / zero tensions & gauges | ✅ |
| Support deficit / conflict fixtures | ✅ |
| Superseded claims ignored | ✅ |
| Metrics do not mutate `memory_version` | ✅ |
| Metrics layer has no epistemic ORM imports | ✅ |
| Version gauges still present / unchanged in meaning | ✅ |
| Golden parity unaffected | ✅ (release-check) |
| Chat / retrieval / Executive unchanged | ✅ Presentation + metrics only |

**Production chat/retrieval with flags OFF:** equivalent to Release 0.4 for user-facing answers.

---

## 4. Governance refinements (pre-038)

| Item | Status |
|------|--------|
| [ADR-0002](../adr/0002-tension-taxonomy-ownership.md) | **Accepted** — taxonomy ownership |
| `METRICS_CLAIM_SCAN_LIMIT` = 500 rationale | Documented as **engineering safety bound**, not cognitive limit |
| Current maturity matrix | In [TENSION_SURFACING.md](../TENSION_SURFACING.md) |

---

## 5. Operational readiness

| Area | Status | Detail |
|------|--------|--------|
| **Deployment** | ✅ | No new migrations; see [0.5-rollback.md](0.5-rollback.md) |
| **Rollback** | ✅ | Redeploy prior build; no schema downgrade required for 0.5 |
| **Feature flags** | ✅ | No new required flag; planned `tension_surfacing_enabled` remains optional/future for dashboard gating |
| **Metrics** | ✅ | `kos_open_tensions`, `kos_support_deficit_tensions`, `kos_conflict_tensions` |
| **Tests** | ✅ | Tension acceptance + API + operational metrics; `make release-check` green |
| **Migration safety** | ✅ | No 0.5 Alembic changes |

### Validation commands

```bash
make release-check

cd backend
.venv/bin/pytest \
  tests/test_tension_surfacing_service.py \
  tests/test_tension_acceptance.py \
  tests/test_understanding_tensions_api.py \
  tests/test_operational_metrics.py \
  -m unit -q
```

### Optional / deferred (ops)

| Validation | Status |
|------------|--------|
| Staging: Understanding panel with non-empty shadow memory | **PENDING OPS** |
| Staging: scrape tension gauges under load | **PENDING OPS** |
| Staging-validated tier (0.3/0.4 carryover) | **PENDING OPS** |

---

## 6. Architecture Health

### Subsystem boundaries

| Subsystem | Release 0.5 | Health |
|-----------|-------------|--------|
| Epistemic Memory | Unchanged substrate | ✅ |
| Tension Surfacing | Owner of taxonomy + detection | ✅ ADR-0002 |
| Understanding API / UI | Consumer | ✅ |
| Operational metrics | Consumer of `summarize_counts` | ✅ |
| Maintenance / Investigation / Reasoning | Not present | ✅ Deferred |

### Remaining technical debt

| Item | Severity | Target |
|------|----------|--------|
| ADR-0001 stale observation on re-SI | Medium | Memory Integration |
| Metrics scan bound 500 (under-count large memories) | Low | Raise bound or paginated aggregation when needed |
| Planned `tension_surfacing_enabled` not wired | Low | Optional dashboard gate |
| No tension persistence | Expected | Later RFC if required |
| Maintenance / investigation / belief revision | Expected | RFC-100 0.6+ / 0.9 |

### ADRs

| ADR | Status | Notes |
|-----|--------|-------|
| [0001](../adr/0001-shadow-observation-key-per-source.md) | Accepted | Shadow observation identity |
| [0002](../adr/0002-tension-taxonomy-ownership.md) | Accepted | Tension taxonomy ownership |

### Readiness for Release 0.6

| Gate | Status |
|------|--------|
| Tension observability (service, API, UI, metrics) | ✅ Complete |
| Taxonomy ownership ADR | ✅ Complete |
| Cognitive acceptance suite | ✅ Complete |
| Memory / tensions unused by reasoning | ✅ Verified |
| **Release 0.6 engineering (ReasoningService)** | **✅ MAY PROCEED** |

---

## 7. Outstanding risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Operators treat tensions as confirmed errors | Medium | Medium (process) | UI/metrics wording + docs |
| Large corpora under-counted by 500-claim scan | Medium | Low (ops visibility) | Documented bound; raise later |
| Taxonomy drift in future Maintenance UI | Low | High | ADR-0002 |
| Shadow flag still OFF → empty tensions in prod | High (by design) | Low | Expected until shadow staging |

---

## 8. Remaining work before Release 0.6

### Engineering (RFC-100)

| Step | Title |
|------|-------|
| **039** | Extract `ReasoningService` from RPS |
| **040** | Extract `EvidenceAssemblyService` |
| **041+** | Coordinator / flag wiring per RFC-100 |

### Not required before 0.6 starts

- Enabling `memory_shadow_write_enabled` in production
- Tension persistence
- Maintenance execution
- New tension types

---

## 9. Release decision

### Release readiness tiers

| State | Status | Gates |
|-------|--------|-------|
| **Engineering-ready** | **✅ ACCEPTED** | Steps 034–038; `make release-check` green |
| **Staging-validated** | **⏳ PENDING OPS** | Deploy + smoke + Understanding/metrics spot-check |
| **Production-ready** | **❌ NOT YET** | Requires staging-validated |

State model: [LIFECYCLE.md](../LIFECYCLE.md).

### Blocking issues

**None** for **engineering-complete** Release 0.5 acceptance.

---

## 10. Recommendation

### Engineering acceptance: **GRANTED**

Release 0.5 Steps 034–038 are **engineering-ready**.

### Release 0.6 — engineering may proceed

ReasoningService extraction (Steps 039+) may begin when:

1. This report is accepted.
2. Consumers of tensions continue to respect **ADR-0002** (no parallel taxonomies).

### Ship configuration (engineering-complete)

- Alembic head: `0015_memory_shadow_write_enabled`
- Migration flags **OFF**
- Tension API/UI available to **admin** only
- Metrics include tension gauges (hypothesis counts, bounded scan)

---

## Related documents

- [TENSION_SURFACING.md](../TENSION_SURFACING.md)
- [TENSION_ACCEPTANCE.md](../TENSION_ACCEPTANCE.md)
- [0.5-rollback.md](0.5-rollback.md)
- [RELEASE-0.4-ACCEPTANCE-REPORT.md](RELEASE-0.4-ACCEPTANCE-REPORT.md)
- [FEATURE_FLAGS.md](../FEATURE_FLAGS.md)
