# Release 0.9 — Engineering Acceptance Report

**Date:** 2026-07-31  
**RFC:** RFC-100 Production Migration Strategy  
**Closure step:** Step 062  
**Baseline tip (pre-closure):** `a5e67ea27c9b1eabfe4291309da7a8bc286bd55c` (`origin/main`)

---

## 1. Executive summary

Release 0.9 delivers **active maintenance engineering** (default OFF): ephemeral agenda ranking (058), maintenance cycle orchestration with env gates (059), authoritative Index→Integrate compose for legal Memory updates after fetch investigations (060), and process-local investigation metrics (061). Step **062** is engineering closure only.

**Engineering Ready: PASS.** Staging Validated: **false**. Production Ready: **false**.  
No deploy was performed as part of this closure. Maintenance execution remains default **OFF**. `kos_tension_resolved_total` remains **deferred**.

---

## 2. Lifecycle state

| Classification | Verdict |
|----------------|---------|
| **Engineering Ready** | **PASS** |
| **Staging Validated** | **false** |
| **Production Ready** | **false** |
| Deployment | **not executed** (this closure) |
| New Alembic revisions in 0.9 | **none** |
| Maintenance execution default | **OFF** |

Repository metadata: `APP_RELEASE="0.9"`, `accepted="0.9"`, `closed_0_9=true`, `engineering_ready=true`, `staging_validated=false`, `production_ready=false`, `in_progress=null`.

---

## 3. Commit inventory (Steps 058–061 + Index→Integrate)

| Step / contract | Feature commit | Subject |
|-----------------|----------------|---------|
| **058** | `e4e7972` | feat(epistemic): implement RFC-100 step 058 agenda ranking |
| **059** | `3d6d5aa` | feat(epistemic): implement RFC-100 step 059 maintenance cycle |
| **Index→Integrate** | `e04789b` | feat(indexing): add authoritative single-source index-integrate contract |
| **060** | `d414280` | feat(epistemic): implement RFC-100 step 060 investigation execution |
| **061** | `a5e67ea` | feat(observability): implement RFC-100 step 061 investigation metrics |
| **062** | *(this closure)* | Release 0.9 engineering closure |

Full tip before this closure commit: **`a5e67ea`**.

---

## 4. Steps 058–062 deliverables

| Step | Deliverable |
|------|-------------|
| **058** | Ephemeral agenda ranking → ordered `InvestigationPlan[]` |
| **059** | Ephemeral maintenance cycle; env `MAINTENANCE_EXECUTION_ENABLED` / budget; fail-closed defaults |
| **Index→Integrate** | Opt-in `index_and_integrate` compose (index → SI → Memory Integration); index-only callers unchanged |
| **060** | Fetch-only investigation execution via Index→Integrate; ephemeral results |
| **061** | Observe 059/060 DTOs → three process-local counters on existing `/api/metrics`; tension-resolved deferred |
| **062** | This engineering closure (docs + build metadata) |

---

## 5. Feature / env defaults

| Control | Default | Closure expectation |
|---------|---------|---------------------|
| `MAINTENANCE_EXECUTION_ENABLED` | **false** / unset | Remain OFF for normal 0.9 ops |
| `MAINTENANCE_INVESTIGATIONS_PER_CYCLE` | fail-closed | Remain 0 / unset unless approved experiment |
| `memory_evidence_assist_enabled` | false | **OFF** |
| `memory_canonical_shadow_enabled` | false | **OFF** |
| Reasoning / EA / Executive / speech-act env flags | false | Unchanged |

---

## 6. Metrics inventory (Release 0.9)

| Counter | Status |
|---------|--------|
| `kos_maintenance_cycles_total` | **shipped** (061) |
| `kos_investigations_planned` | **shipped** (061) |
| `kos_investigations_failed_total` | **shipped** (061) |
| `kos_tension_resolved_total` | **deferred** (not in 0.9) |

---

## 7. Explicitly unchanged

- ADR-0001 observation-key / shadow identity policy
- ADR-0002 tension hypothesis ownership (no tension closure)
- Chat / retrieval product path under maintenance defaults OFF
- Qdrant / corpus content — **not mutated** by engineering closure
- No new Business API, Dashboard, Settings, Scheduler, event bus, or Alembic from Step 062

---

## 8. Rollback plan

See [0.9-rollback.md](0.9-rollback.md).

- Level 1: keep / force `MAINTENANCE_EXECUTION_ENABLED=false` (and budget 0)
- Level 2: restore known-good tip on `origin/main`, then canonical `deploy full`

---

## 9. Validation (closure)

| Suite | Result |
|-------|--------|
| Step 058 ranking tests | PASS (existing) |
| Step 059 cycle tests | PASS (existing) |
| Index→Integrate tests | PASS (existing) |
| Step 060 investigation tests | PASS (existing) |
| Step 061 metrics tests | PASS (existing) |
| Step 062 build metadata / closure docs tests | PASS |
| `make release-check` | PASS (closure gate) |
| Deploy as part of closure | **Not performed** |
| Staging Validated | **false** |
| Production Ready | **false** |

---

## 10. Explicit confirmations

- Release 0.9 engineering closure **completed**.
- Step **062** **completed**.
- Release **1.0** **not started**.
- **No** deployment performed as part of this closure.
- Maintenance execution **not** enabled.
- `kos_tension_resolved_total` **not** introduced.
- Frozen packages for 058–061 and Index→Integrate **not** reopened.
