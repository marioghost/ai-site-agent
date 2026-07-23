# Release 0.1 Acceptance Report

**Knowledge OS Migration — RFC-100**  
**Release theme:** Executive shell + migration guards  
**Report date:** 2026-07-05  
**Steps completed:** 001–012  
**Flag default at release:** `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false`

This document is the historical record of Release 0.1 and the **performance / quality baseline** for all future releases.

---

## 1. Executive migration summary

### What changed

| Area | Change |
|------|--------|
| **Orchestration entry** | `ExecutiveService` added (`answer`, `answer_stream`); passthrough to existing RAG stack |
| **Chat routing** | `api/chat.py` dispatches via `_dispatch_non_stream_answer` / `_dispatch_stream_events` behind feature flag |
| **Feature flag** | `KNOWLEDGE_OS_EXECUTIVE_ENABLED` (default **false**) in `app/core/config.py` |
| **Observability** | Structured dispatch logs: `request_id`, `path=legacy\|executive`, stream lifecycle fields |
| **Golden CI gate** | 10-query smoke suite + parity runner (legacy vs executive, mocked RAG) |
| **Legacy guards** | Runtime spies prove `build_boost_tables`, `category_boost`, legacy JSON columns not used on chat hot path |
| **Test migration** | `test_retrieval_hybrid.py`, `test_broad_query_handling.py`, `test_boilerplate_retrieval.py` → document-first patterns |
| **Dead code removal** | `hybrid_retrieval_service.py` deleted; import guard tests added |
| **Documentation** | `docs/FEATURE_FLAGS.md`, `docs/releases/0.1-rollback.md` |

### What intentionally did NOT change

- **Retrieval logic** — production path remains `RetrievalPipelineService` → `DocumentFirstRetrievalPipeline` → `HybridChunkRetriever` + document scoring/reranking
- **LLM generation, polish, caches** — unchanged when flag is OFF; unchanged in behavior when flag is ON (Executive passthrough)
- **Dashboard UI** — no migration surfaces yet
- **Knowledge Profile API / presets** — still present (deprecation in 0.2+)
- **Database schema** — no migrations in 0.1
- **Default production traffic** — flag OFF → identical to pre-0.1 `RagService` direct path

### Why Executive now exists

Per `KNOWLEDGE_OS_ARCHITECTURE_v1.md`, chat must eventually flow through a single orchestration authority. Release 0.1 installs the **strangler fig entry point** without changing cognition:

1. **Boundary** — `ExecutiveService` is the designated future owner of workflow coordination (refusal policy, maintenance, epistemic state in later releases).
2. **Safe cutover** — flag-gated routing with golden parity proves the shell before any orchestration policy lands.
3. **Observability** — dispatch logs distinguish legacy vs executive paths during migration.
4. **Release train** — enables 0.2+ work (diagnostics, memory, Reasoning) to target Executive instead of expanding `RagService` further.

---

## 2. Production readiness

### Feature flag state

| Flag | Implemented | Default | Production recommendation (0.1) |
|------|-------------|---------|--------------------------------|
| `KNOWLEDGE_OS_EXECUTIVE_ENABLED` | Yes | `false` | **Keep OFF** until staging shadow sign-off |

Planned flags (0.2+) are documented in `docs/FEATURE_FLAGS.md` but **not implemented** in code.

### Rollback procedure

Documented in `docs/releases/0.1-rollback.md` and `docs/FEATURE_FLAGS.md` § Kill-switch:

1. Set `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false` (or unset) → restart backend  
2. Clear retrieval + answer caches if needed  
3. Verify logs show `path=legacy`  
4. Run golden unit smoke  

**Rollback complexity:** Low — config-only, no DB rollback.

### Deployment procedure

See `docs/releases/0.1-rollback.md`:

1. Deploy with flag OFF (default)  
2. Post-deploy HTTP smoke + log check (`path=legacy`)  
3. Staging-only: enable flag ON → golden shadow + latency baseline  
4. Production: recommend holding flag OFF for initial 0.1 ship  

### Shadow validation results

| Validation layer | Environment | Result | Notes |
|------------------|-------------|--------|-------|
| Executive routing unit tests | CI / local | **PASS** | 11 routing + 3 executive service tests |
| Golden parity (legacy vs executive) | CI / local | **PASS** | 10 smoke queries × 2 paths, mocked RAG |
| Golden schema invariants | CI / local | **PASS** | 7 schema tests |
| Legacy guard tests | CI / local | **PASS** | 13 tests incl. hybrid deletion guards |
| Document-first migration tests | CI / local | **PASS** | hybrid/broad/boilerplate suites migrated |
| Full migration unit suite | CI / local | **PASS** | **89 passed** (2026-07-05) |
| HTTP golden integration | Staging | **SKIPPED** | Requires `POSTGRES_TEST_URL` + `GOLDEN_CHAT_LIVE=1` |
| Live staging chat shadow (flag ON) | Staging | **PENDING OPS** | Procedure in `0.1-rollback.md` §4 — run on first staging deploy |
| Production flag ON | Production | **NOT IN SCOPE** | 0.1 ships with flag OFF |

**CI shadow conclusion:** Executive path is **parity-equivalent** to legacy under golden invariants (mocked RAG). Live staging shadow is an **operator checklist item**, not a code blocker for shipping 0.1 with flag OFF.

### Golden parity status

| Metric | Value |
|--------|-------|
| Smoke queries | 10 |
| Categories covered | 5 (overview, list, fact, contact, negative) |
| Parity tests | 10 parametrized legacy vs executive |
| Forbidden behaviors enforced | 6 vocabulary tokens |
| Exact score assertions | None (by design) |
| CI command | `pytest tests/test_golden_chat_parity.py tests/test_golden_queries_schema.py -m unit` |
| Last run | **19 passed**, 0 failed (2026-07-05) |

---

## 3. Architecture health

### Before vs after (measurable)

| Metric | Pre–Release 0.1 | Post–Release 0.1 | Δ |
|--------|-----------------|------------------|---|
| `HybridRetrievalService` in `app/` | Present (test-only) | **Removed** | Dead module eliminated |
| `HybridRetrievalService` imports in `tests/` | 3 files | **0** | Guard test enforced |
| Chat orchestration entry | `RagService` direct | **Flag → Executive or RagService** | Strangler installed |
| Executive test coverage | 0 | **14+ dedicated tests** | Routing, stream, service, logging |
| Golden smoke queries | 0 | **10** | CI regression net |
| Legacy guard tests | 0 | **13** | Hot-path runtime spies |
| Migration unit tests (RFC-100 suite) | 0 | **89** | See §Performance baseline |
| Production imports of hybrid | 0 | 0 | Unchanged (never in prod) |
| `build_boost_tables` on chat hot path | Not called | Not called | Guarded |
| `category_boost` on chat hot path | Not called | Not called | Guarded |

### Executive coverage

| Surface | Covered by tests |
|---------|------------------|
| Non-stream dispatch flag OFF/ON | `test_chat_executive_routing.py` |
| Stream dispatch flag OFF/ON | `test_chat_stream_executive_routing.py` |
| `ExecutiveService` passthrough | `test_executive_service.py` |
| Dispatch logging `path=` | `test_chat_dispatch_logging.py` |
| Golden parity both paths | `test_golden_chat_parity.py` |
| Legacy path guards both paths | `test_legacy_guards.py` |

### Architectural boundary violations

| Check | Status |
|-------|--------|
| Chat bypasses Executive when flag ON | None — routing enforced in `chat.py` |
| Hybrid chunk fusion in production | None — module deleted |
| Legacy boost tables on chat hot path | None — guard tests pass |
| Executive contains business logic (0.1) | None — passthrough only (intentional) |
| God-class expansion in Executive | None — no new logic in Executive |

### Technical debt removed

| ID | Item |
|----|------|
| TD-08 | Test reliance on `HybridRetrievalService` — **resolved** |
| — | `hybrid_retrieval_service.py` (~365 lines) — **deleted** |
| — | False signal that chunk-first fusion is production path — **eliminated** |

### Technical debt created / remaining

| Item | Severity | Paydown |
|------|----------|---------|
| `knowledge_os_executive_enabled` flag + dual dispatch paths | Low | Remove at 1.0 |
| Executive passthrough (no orchestration yet) | Medium | 0.6 ReasoningService |
| `build_boost_tables()` / `category_boost()` dead code | Low | Future cleanup + guards |
| `CanonicalSourceService` profile doc-type rules | Medium | 0.7–0.8 |
| `RagService` / `RPS` god classes | High | 0.6 split |
| Score-centric diagnostics | Medium | 0.2 diagnostics v2 |
| No epistemic memory store | High | 0.4 |
| Live P95 baseline not yet captured | Low | First staging deploy |

---

## 4. Performance baseline

**Recorded:** 2026-07-05, development environment (Python 3.12, Linux WSL2).  
**Note:** End-to-end chat latency requires staging fixture site + Ollama/Qdrant. Procedures for live capture are in `docs/releases/0.1-rollback.md` §5.

### CI / mocked measurements (baseline for regression comparison)

| Metric | P50 | P95 | Method |
|--------|-----|-----|--------|
| **Executive dispatch overhead** (non-stream) | 0.0001 ms | 0.057 ms | 200 iterations, mocked RAG, exec − legacy |
| **Legacy dispatch** (mocked) | 0.063 ms | — | Same harness |
| **Executive dispatch** (mocked) | 0.064 ms | — | Same harness |
| **Golden suite duration** | — | — | **0.06 s** (19 tests) |
| **Full migration unit suite** | — | — | **2.56 s** (89 tests) |

### Live chat latency (deferred to staging shadow)

| Metric | P50 | P95 | Status |
|--------|-----|-----|--------|
| Chat latency (non-stream) | — | — | **Pending** — capture on staging per runbook |
| Streaming first-token latency | — | — | **Pending** — from SSE `llm.first_token` event |
| Streaming completion latency | — | — | **Pending** — from SSE `final` event |

**Baseline policy:** Future releases compare against staging captures taken at first 0.1 deploy (flag OFF and ON). CI mocked dispatch overhead (<0.1 ms P95) establishes that Executive shell adds negligible local cost.

---

## 5. Lessons learned

### What worked well

- **Strangler with passthrough** — Executive routing shipped with zero behavioral delta; golden parity gave high confidence.
- **Flag default OFF** — production risk near zero for initial deploy.
- **Runtime guard tests** — spies on `build_boost_tables` / `category_boost` catch regressions better than static import graphs.
- **Document-first test migration** — deleting hybrid became safe only after tests targeted production components (`DocumentScorer`, `DocumentFirstRetrievalPipeline`).
- **Incremental steps with review gates** — 12 small steps prevented scope creep into Reasoning or Memory.

### What was unexpectedly difficult

- **Streaming test harness** — `_FakeOllama` needed `embed()` for streaming prepare path even with caches disabled.
- **Document reranker broad-query tests** — duplicate `title="Page"` caused false diversity rejections; required distinct titles.
- **Hybrid deletion blocked by boilerplate tests** — `_fuse` / `_brief` tests looked like production coverage but tested dead module only.

### Architectural decisions that proved correct

- **Executive as interface-only in 0.1** — avoided premature Reasoning extraction.
- **Golden invariants over exact answers** — stable CI without locking LLM phrasing.
- **Document-first as production truth** — hybrid removal did not affect live retrieval.
- **Separate legacy guards from golden parity** — complementary safety nets.

### What should never be repeated

- **Keeping dead modules because tests import them** — migrate tests first, then delete.
- **Bank-specific golden or migration fixtures** — generic corporate fixture reduced false coupling.
- **Chunk-first fusion tests as architecture documentation** — they implied a path that was not production.
- **Skipping flag registry until late** — ops needs `FEATURE_FLAGS.md` before staging enablement.

---

## 6. Release decision

### **READY FOR RELEASE**

Release 0.1 engineering deliverables are complete. Shipping with **`KNOWLEDGE_OS_EXECUTIVE_ENABLED=false`** preserves pre-0.1 production behavior while landing the migration foundation, CI gates, and documentation.

### Conditions (non-blocking for 0.1 ship with flag OFF)

| Item | Owner | When |
|------|-------|------|
| Staging shadow with flag ON | Ops | First staging deploy after this release |
| Live P50/P95 chat latency baseline | Ops | Staging §5 runbook |
| HTTP golden integration in CI | Platform | When `POSTGRES_TEST_URL` available in CI |

### Blocking issues

**None** for Release 0.1 with flag default OFF.

### Recommendation

**Proceed to Release 0.2** (Steps 013–019: semantic diagnostics v2 stub, dashboard debug section, KP legacy banner, golden expansion to 30 queries).

Development of 0.2 may proceed **in parallel** with staging shadow validation for 0.1; enabling Executive in production should wait for staging sign-off documented in `0.1-rollback.md` §4.

---

## Appendix A — Step completion matrix

| Step | Title | Status |
|------|-------|--------|
| 001 | ExecutiveService interface | ✅ |
| 002 | Non-stream chat flag routing | ✅ |
| 003 | Streaming chat flag routing | ✅ |
| 004 | Structured dispatch logging | ✅ |
| 005 | Golden queries.json | ✅ |
| 006 | Golden parity CI gate | ✅ |
| 007 | Legacy guard tests | ✅ |
| 008 | Migrate test_retrieval_hybrid | ✅ |
| 009 | Migrate test_broad_query_handling | ✅ |
| 010 | Delete hybrid_retrieval_service | ✅ |
| 011 | FEATURE_FLAGS.md | ✅ |
| 012 | Deploy runbook + validation framework | ✅ |

## Appendix B — CI verification command

```bash
cd backend
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
  -v -m unit
```

**Expected:** 89 passed (as of 2026-07-05).

## Appendix C — Document index

| Document | Path |
|----------|------|
| Feature flag registry | `docs/FEATURE_FLAGS.md` |
| Deploy & rollback | `docs/releases/0.1-rollback.md` |
| This report | `docs/releases/RELEASE-0.1-ACCEPTANCE-REPORT.md` |
| Migration strategy | `docs/RFC-100-PRODUCTION-MIGRATION-STRATEGY.md` |
| Golden suite README | `backend/tests/golden/README.md` |
