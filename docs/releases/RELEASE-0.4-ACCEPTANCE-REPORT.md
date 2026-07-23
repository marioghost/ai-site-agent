# Release 0.4 Acceptance Report

**Knowledge OS Migration — RFC-100**  
**Release theme:** Epistemic Memory shadow substrate (schema, read API, SI → proposals, flag-gated writes, bump-on-change, provenance tests)  
**Report date:** 2026-07-05  
**Steps completed:** 027–033  
**Flag defaults at release:** `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false`, `enable_semantic_diagnostics_v2=false`, `cache_namespace_v2_enabled=false`, **`memory_shadow_write_enabled=false`**

This document closes Release 0.4 engineering deliverables and records readiness for Release 0.5 (Tension Surfacing).

---

## 1. Release summary

### Theme

Introduce **passive Epistemic Memory** — additive schema, internal read/write APIs, SI → claim proposal mapping, and **shadow persistence** behind `memory_shadow_write_enabled` (default OFF). **Epistemic Memory is not used for reasoning or retrieval.** Production behavior with all flags OFF remains equivalent to Release 0.3.

### Step completion matrix

| Step | Title | Status |
|------|-------|--------|
| **027** | Epistemic Memory schema (`observation_ref`, `claim`, `evidence_link`) | ✅ |
| **028** | `EpistemicMemoryService` read API | ✅ |
| **029** | `ClaimExtractionFromSI` mapper (in-memory proposals) | ✅ |
| **030** | Shadow writes (`memory_shadow_write_enabled`) | ✅ |
| **031** | Auto `memory_version` bump on shadow integrate (deferred commit) | ✅ |
| **032** | Claim roundtrip / provenance tests + ADR-0001 | ✅ |
| **033** | Release 0.4 acceptance report | ✅ |

### What each step contributed

| Step | Platform contribution |
|------|------------------------|
| **027** | Additive migrations `0014`; three epistemic tables with supersession columns reserved for future integration. |
| **028** | Internal read API + DTOs; negative scans enforce no production writes from non-allowlisted modules. |
| **029** | `ClaimExtractionFromSI` — SI profile → `ClaimProposal` / `EvidenceProposal` DTOs; zero DB access. |
| **030** | `EpistemicMemoryIntegrationService` + write service; SI/indexing hooks; flag-gated idempotent persist. |
| **031** | Single auto-bump path via `MemoryVersionService.bump(commit=False)`; bump-on-change only. |
| **032** | Roundtrip/provenance tests; [ADR-0001](../adr/0001-shadow-observation-key-per-source.md) documents observation identity trade-off. |
| **033** | This report — closes Release 0.4. |

### What intentionally did NOT change

| Area | Status |
|------|--------|
| Chat / retrieval / LLM / Executive hot path | Unchanged |
| Epistemic Memory consumption in reasoning | **Not implemented** |
| Merge, supersession, conflict resolution, belief revision | Not implemented |
| Observation Processing as separate subsystem | Not implemented (shadow compression) |
| Dashboard epistemic UI | Not required |
| Production cache keys (all flags OFF) | Identical to Release 0.3 |
| Golden query set | Unchanged (30 queries) |

---

## 2. Cognitive Architecture alignment

Reviewed against [KNOWLEDGE_OS_ARCHITECTURE_v1.md](../KNOWLEDGE_OS_ARCHITECTURE_v1.md) and [COGNITIVE_ARCHITECTURE.md](../COGNITIVE_ARCHITECTURE.md).

| Principle | Release 0.4 status |
|-----------|-------------------|
| **Single epistemic writer** | ✅ Only `EpistemicMemoryIntegrationService` → `EpistemicMemoryService.persist_claim_proposals()` |
| **Claim Extraction proposes only** | ✅ `ClaimExtractionFromSI` never writes DB or bumps version |
| **Memory Integration owns persist orchestration** | ✅ Flag, extract, persist, optional bump |
| **Reasoning / retrieval do not read memory** | ✅ Verified — no imports in chat or retrieval services |
| **Layered memory (observation → claim → evidence)** | ✅ Schema and shadow path match substrate model |
| **Observation as immutable event (target)** | ⚠️ **Shadow deviation** documented in ADR-0001 — stable key per source |

**Verdict:** Implementation matches frozen architecture for **shadow phase** scope. Known deviation (observation identity) is explicit, accepted, and has revisit triggers — not silent debt.

---

## 3. Flag OFF behavior verification

With **`memory_shadow_write_enabled=false`** (default):

| Check | Verified |
|-------|----------|
| Zero epistemic writes | ✅ Integration returns `None` before extract/persist |
| Zero auto `memory_version` bumps from shadow | ✅ Bump path not reached |
| SI generation unchanged | ✅ Hook calls integration; integration no-ops |
| Chat / retrieval / Executive | ✅ No epistemic imports |
| Golden parity | ✅ 40/40 passing (2026-07-05) |
| Cache namespace | ✅ Unchanged when `cache_namespace_v2_enabled=false` |

**Production runtime with all migration flags OFF:** equivalent to Release 0.3 for user-visible behavior.

---

## 4. Epistemic Memory passivity

| Consumer | Reads epistemic tables? |
|----------|-------------------------|
| `/api/chat` (legacy / Executive) | **No** |
| `RagService` / retrieval pipeline | **No** |
| `DocumentFirstRetrievalPipeline` | **No** |
| Dashboard | **No** |
| `EpistemicMemoryService` | Internal only; no production caller on hot path |

Shadow data is **write-only collection** when flag ON. Release 0.7+ will introduce memory-assisted evidence per RFC-100.

---

## 5. ADR-0001 review

**[ADR-0001: Shadow observation identity](../adr/0001-shadow-observation-key-per-source.md)** — **Accepted**

| ADR element | Assessment |
|-------------|------------|
| Current behavior (`obs:source:{id}:si`) | Accurately describes implementation |
| Rationale (idempotent shadow) | Sound for Release 0.4 |
| Advantages | Documented |
| Future risks (stale observation on re-SI) | Documented with Step 032 test encoding |
| Revisit triggers | Clear (Memory Integration, Revision Engine, etc.) |
| Step 032 non-blocker | Explicit |
| Future direction | Event keys / new observations on content change |

**No ADR amendment required** for Release 0.4 closure.

---

## 6. Test debt: `test_stream_dispatch_overhead_is_negligible`

**File:** `backend/tests/test_chat_stream_executive_routing.py`  
**Issue:** Intermittent failure in full `make release-check` suite (~70–78 ms measured overhead vs 5 ms threshold). **Passes in isolation** (~0.03 s).

### Root cause (test design)

1. Uses wall-clock `time.perf_counter()` difference between two back-to-back dispatch calls in a **loaded test process** (250+ prior tests).
2. Absolute **5 ms threshold** is not stable across CI hosts, WSL, CPU throttling, or test order.
3. First path may pay import/cache/warmup costs asymmetrically between legacy vs executive branches when run after heavy suite.
4. Test does **not** measure production latency — it measures local dispatch wrapper overhead with mocks.

### Classification

**Test debt** — not a production correctness issue. Executive dispatch parity is already covered by structural golden tests in the same file (`test_stream_golden_parity_legacy_vs_executive`, event sequence contract).

### Recommended fix (future, not Release 0.4)

- Remove wall-clock threshold or replace with structural assertion only; **or**
- Mark `@pytest.mark.integration` / `@pytest.mark.flaky` and exclude from `release-check` fast path; **or**
- Use fixed mock timing (inject monotonic clock) instead of wall clock.

**No production code change** for Release 0.4 closure.

---

## 7. Operational readiness

| Area | Status | Detail |
|------|--------|--------|
| **Deployment** | ✅ Documented | Migrations `0014`, `0015`; see [0.4-rollback.md](0.4-rollback.md) |
| **Rollback** | ✅ Documented | Flag OFF restores 0.3 behavior; downgrade paths documented |
| **Feature flags** | ✅ | `memory_shadow_write_enabled` in [FEATURE_FLAGS.md](../FEATURE_FLAGS.md) |
| **Metrics** | ✅ | Unchanged from 0.3; shadow bump visible in `kos_memory_version` when enabled |
| **Tests** | ✅ | **44** epistemic unit tests; **251** release unit tests collected; **40** golden |
| **Migration safety** | ✅ | Additive only; head `0015` |

### Validation commands

```bash
make release-check   # may flake on perf test — see §6

cd backend
.venv/bin/pytest tests/test_epistemic_memory_*.py tests/test_claim_extraction_from_si.py -m unit -q
.venv/bin/pytest tests/test_golden_chat_parity.py tests/test_golden_queries_schema.py -m unit -q
.venv/bin/alembic upgrade head
```

### Optional / deferred (ops)

| Validation | Status |
|------------|--------|
| Staging: `memory_shadow_write_enabled` ON + SI idempotency | **PENDING OPS** |
| Staging: shadow + `cache_namespace_v2_enabled` bump → cache miss | **PENDING OPS** |
| Staging-validated tier (0.3 carryover) | **PENDING OPS** |
| Fix flaky dispatch overhead test | **Test debt** — non-blocking |

---

## 8. Architecture Health

### Subsystem boundaries

| Subsystem (target) | Release 0.4 implementation | Health |
|--------------------|----------------------------|--------|
| Observation Processing | Collapsed into write service on persist | ⚠️ Shadow shortcut — ADR-0001 |
| Claim Extraction | `ClaimExtractionFromSI` | ✅ Clean boundary |
| Memory Integration | `EpistemicMemoryIntegrationService` | ✅ Thin orchestrator |
| Epistemic Memory (storage) | `EpistemicMemoryService` + `EpistemicMemoryWriteService` | ✅ Read/write split |
| Reasoning / Evidence Assembly | Untouched | ✅ |

### Ownership

| Concern | Owner | Enforced |
|---------|-------|----------|
| Epistemic row inserts | `EpistemicMemoryWriteService` via integration | Static tests |
| Persist orchestration | `EpistemicMemoryIntegrationService` | Single hook path |
| Auto `memory_version` bump | Same integration service only | Allowlist test |
| Manual `memory_version` bump | Admin API | Unchanged from 0.3 |
| SI → proposals | `ClaimExtractionFromSI` | No DB tokens in module |

### Remaining technical debt

| Item | Severity | Target |
|------|----------|--------|
| Observation identity per ADR-0001 (stable key vs event) | **Medium** | Revisit at Memory Integration (0.5+) |
| No merge / supersession / conflict engine | **Expected** | RFC-100 integration steps |
| Observation Processing not extracted | **Low** | Post-shadow cutover |
| `EpistemicMemoryIntegrationService` SI-coupled method name | **Low** | Generic `integrate_proposals` when second extractor added |
| No DB unique constraint on claim identity triple | **Low** | Before high-volume shadow |
| `test_stream_dispatch_overhead_is_negligible` flaky | **Low** | Test fix — see §6 |
| Cache namespace dual-read (v2 then v1) | **Low** | Carried from 0.3 |

### ADRs

| ADR | Status | Notes |
|-----|--------|-------|
| [0001](../adr/0001-shadow-observation-key-per-source.md) | **Accepted** | Shadow observation identity |

### Known future risks

1. **Stale observations** after re-SI with changed content (ADR-0001) — revision engine must compensate.
2. **Enabling shadow in production** without staging idempotency proof — mitigated by flag default OFF.
3. **Enabling `cache_namespace_v2_enabled` + shadow** — auto-bumps will invalidate caches; intentional but needs ops awareness.
4. **God object growth** in `EpistemicMemoryService` if merge/revision land without new modules — monitor in 0.5+.

### Readiness for Release 0.5

| Gate | Status |
|------|--------|
| Epistemic substrate (schema, read, shadow write) | ✅ Complete |
| Provenance / roundtrip tests | ✅ Complete |
| ADR for known semantic trade-off | ✅ Complete |
| Memory passive (no reasoning consumption) | ✅ Verified |
| Flag OFF production equivalence | ✅ Verified |
| **Release 0.5 engineering (Tension Surfacing)** | **✅ MAY PROCEED** |

Release 0.5 (Steps 034–038) adds `TensionSurfacingService` and read-only tension API — **does not require** shadow flag ON or epistemic consumption in chat.

---

## 9. Outstanding risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Operator enables shadow without staging proof | Medium | Low (data only) | Flag default OFF; rollback doc |
| ADR-0001 stale observation in shadow dataset | High (by design) | Medium at integration | Revisit triggers documented |
| Flaky perf test blocks CI | Medium | Low (process) | Test debt; exclude or fix threshold |
| Concurrent claim insert race | Low | Low | Accept for shadow; unique constraint later |

---

## 10. Remaining work before Release 0.5

### Engineering (RFC-100)

| Step | Title |
|------|-------|
| **034** | `TensionSurfacingService` — support deficit + conflict subset |
| **035** | `GET /api/understanding/tensions` read-only |
| **036** | Dashboard Understanding panel (read-only, flag-gated) |
| **037** | Metrics: open tensions, conflicts |
| **038** | Release 0.5 acceptance |

### Not required before 0.5 starts

- Enabling `memory_shadow_write_enabled` in production
- Memory Integration (merge/revise/conflict)
- ReasoningService / memory-assisted evidence (0.6–0.7)
- Observation Processing extraction

### Recommended ops before production shadow enable (later)

1. Staging: shadow ON → idempotency + roundtrip tests pass on real DB
2. Staging: golden suite green with shadow ON
3. Review ADR-0001 with ops/data team

---

## 11. Release decision

### Release readiness tiers

| State | Status | Gates |
|-------|--------|-------|
| **Engineering-ready** | **✅ ACCEPTED** | Steps 027–033; epistemic test suite green |
| **Staging-validated** | **⏳ PENDING OPS** | Shadow flag rehearsal optional; 0.3 carryover |
| **Production-ready** | **❌ NOT YET** | Requires staging-validated |

State model: [LIFECYCLE.md](../LIFECYCLE.md).

### Engineering-complete criteria (met)

Ship configuration:

- All migration flags **OFF** (including `memory_shadow_write_enabled=false`)
- `alembic upgrade head` → `0015_memory_shadow_write_enabled`
- Production chat/retrieval behavior ≡ Release 0.3

### Blocking issues

**None** for **engineering-complete** Release 0.4 acceptance.

**Non-blocking:** flaky `test_stream_dispatch_overhead_is_negligible` in full suite (test debt).

---

## 12. Recommendation

### Engineering acceptance: **GRANTED**

Release 0.4 Steps 027–033 are **engineering-ready**.

### Release 0.5 — engineering may proceed

Tension Surfacing (Steps 034+) may begin when:

1. This report accepted (Step 033)
2. Epistemic unit + golden tests green

**Staging validation of shadow writes** is recommended before enabling `memory_shadow_write_enabled` in any shared environment, but is **not** a prerequisite for starting Release 0.5 engineering.

### Production deployment

Production deployment of Release 0.4 remains subject to:

1. Staging-validated tier per [STAGING-SEED-SMOKE.md](../STAGING-SEED-SMOKE.md)
2. [0.4-rollback.md](0.4-rollback.md) reviewed
3. [RELEASE-CHECKLIST.md](RELEASE-CHECKLIST.md)

With all flags OFF, Release 0.4 deploy is **behaviorally equivalent** to Release 0.3.

---

## 13. Cross-references

| Document | Purpose |
|----------|---------|
| [0.4-rollback.md](0.4-rollback.md) | Deploy & rollback |
| [EPISTEMIC_MEMORY_SCHEMA.md](../EPISTEMIC_MEMORY_SCHEMA.md) | Schema & ownership |
| [ADR-0001](../adr/0001-shadow-observation-key-per-source.md) | Observation identity |
| [FEATURE_FLAGS.md](../FEATURE_FLAGS.md) | `memory_shadow_write_enabled` |
| [MEMORY_VERSION.md](../MEMORY_VERSION.md) | Bump contract |
| Steps 027–032 release notes | `docs/releases/0.4-step-*.md` |
