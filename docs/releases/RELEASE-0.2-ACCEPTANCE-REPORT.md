# Release 0.2 Acceptance Report

**Knowledge OS Migration — RFC-100**  
**Release theme:** Semantic diagnostics v2 stub + legacy visibility  
**Report date:** 2026-07-05  
**Steps completed:** 013–019  
**Flag defaults at release:** `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false`, `enable_semantic_diagnostics_v2=false`

This document closes Release 0.2 engineering deliverables and records validation status for the migration train.

---

## 1. Release 0.2 summary

### Theme

Prepare **engineering diagnostics** and **legacy visibility** for the Knowledge OS transition without changing production chat cognition, retrieval, or LLM behavior.

### Step completion matrix

| Step | Title | Status |
|------|-------|--------|
| **013** | `understanding_trace` schema stub | ✅ |
| **014** | Plumb stub through `ChatResponseBuilder` behind `enable_semantic_diagnostics_v2` | ✅ |
| **015** | Dashboard Understanding Trace panel (debug only) | ✅ |
| **016** | Knowledge Profile legacy banner | ✅ |
| **017** | `Deprecation` header on KP preset load endpoint | ✅ |
| **018** | Golden smoke expansion 10 → 30 queries | ✅ |
| **019** | Release 0.2 acceptance report | ✅ |

### What changed (by step)

| Step | Deliverable |
|------|-------------|
| **013** | `app/schemas/semantic_diagnostics.py` — `UnderstandingTraceRead` stub, helpers; optional field on `ChatResponse` |
| **014** | `ChatResponseBuilder` + chat/stream paths wire `understanding_trace` when flag ON and `debug=true`; Alembic `0011_semantic_diagnostics_v2`; Settings column + API |
| **015** | `UnderstandingTracePanel` in Chat Test diagnostics; i18n EN/UK; 27 dashboard tests |
| **016** | `KnowledgeProfileLegacyBanner` on KP page + generate wizard; EN/UK copy |
| **017** | `Deprecation: true` + `Link` on `POST /api/knowledge-profile/presets/load` only; 4 unit tests |
| **018** | `queries.json` v1.1 — 30 generic queries, 10 categories; parity runner + README |

### What intentionally did NOT change

| Area | Status |
|------|--------|
| Retrieval pipeline / document-first scoring | Unchanged |
| LLM prompts / generation / polish | Unchanged |
| Executive orchestration policy | Passthrough only (from 0.1) |
| Production chat responses (flags OFF) | Identical to 0.1 |
| `understanding_trace` population | Stub only — no reasoning steps |
| Knowledge Profile presets API behavior | Still loads presets; deprecation header additive |
| Dashboard end-user chat UI | No `understanding_trace` in message bubbles |

---

## 2. Validation status

**Recorded:** 2026-07-05, development environment (Python 3.12, Linux WSL2, Node vitest).

### Backend — migration unit suite

| Suite | Result | Count | Duration |
|-------|--------|-------|----------|
| Full RFC-100 migration unit suite | **PASS** | **131 passed** | ~3.26 s |

Includes: broad/hybrid/legacy guards, document-first, boilerplate, executive routing, golden, semantic diagnostics, KP deprecation.

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
  tests/test_semantic_diagnostics_schema.py \
  tests/test_chat_response_builder.py \
  tests/test_knowledge_profile_preset_deprecation.py \
  -m unit -q
```

### Golden parity

| Metric | Release 0.1 | Release 0.2 |
|--------|---------------|---------------|
| Smoke queries | 10 | **30** |
| Categories | 5 | **10** |
| Golden tests (schema + parity) | 19 | **40** |
| Legacy vs executive parity | PASS | **PASS** |
| Exact answer assertions | None | None |
| Last run | — | **40 passed**, ~0.11 s |

```bash
cd backend
.venv/bin/pytest tests/test_golden_chat_parity.py tests/test_golden_queries_schema.py -m unit
```

### Dashboard

| Check | Result |
|-------|--------|
| Vitest | **27 passed** (5 files) |
| TypeScript `tsc --noEmit` | **PASS** |

```bash
cd dashboard
npm test && npx tsc --noEmit
```

### Optional / deferred

| Validation | Status |
|------------|--------|
| HTTP golden integration (`GOLDEN_CHAT_LIVE=1`) | SKIPPED — requires `POSTGRES_TEST_URL` |
| Staging: `enable_semantic_diagnostics_v2` ON | **PENDING OPS** |
| Staging: Executive shadow (0.1) | **PENDING OPS** — see `0.1-rollback.md` |
| Live P50/P95 chat latency | **PENDING OPS** |

---

## 3. Feature flag state

### Active migration flags

| Flag | Surface | Default (0.2) | Production recommendation |
|------|---------|---------------|---------------------------|
| `KNOWLEDGE_OS_EXECUTIVE_ENABLED` | Env | **false** | Keep OFF until staging sign-off |
| `enable_semantic_diagnostics_v2` | Settings DB | **false** | Keep OFF for production chat; enable on staging for diagnostics QA |

### Settings / API implications

| Item | Detail |
|------|--------|
| Migration | `0011_semantic_diagnostics_v2` adds `settings.enable_semantic_diagnostics_v2` (server default `false`) |
| Settings API | Read/update via `/api/settings` — field exposed in `SettingsRead` / `SettingsUpdate` |
| Dashboard toggle | Settings → Advanced → Tracing → “Semantic diagnostics v2” |
| Chat behavior | `understanding_trace` appears only when: flag ON **and** client `debug=true` **and** `enable_chat_debug_payload=true` |
| KP preset load | `Deprecation: true` + `Link: <docs/RFC-100-PRODUCTION-MIGRATION-STRATEGY.md>; rel="deprecation"` — always on preset load (no flag) |

### Planned flags (not in 0.2)

`cache_namespace_v2_enabled`, memory/claim/reasoning flags — see `docs/FEATURE_FLAGS.md`.

---

## 4. Rollback notes

Full runbook: **`docs/releases/0.2-rollback.md`**

| Scenario | Action | Complexity |
|----------|--------|------------|
| Disable semantic diagnostics | Settings `enable_semantic_diagnostics_v2=false` | **Trivial** — no restart |
| Disable Executive | `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false` + restart | **Low** |
| Revert deploy | Previous artifact; migration column is additive | **Low** |
| Alembic downgrade | `alembic downgrade 0010` — only if required | **Medium** — rare |

**Production ship config (0.2):** both flags **OFF** → behavior matches Release 0.1.

---

## 5. Architecture health delta (0.1 → 0.2)

| Metric | Release 0.1 | Release 0.2 | Δ |
|--------|-------------|-------------|---|
| Golden smoke queries | 10 | **30** | +20 |
| Golden categories | 5 | **10** | +5 (pricing, process, policy, comparison, ambiguity) |
| Migration unit tests | 89 | **131** | +42 |
| Dashboard unit tests | 0 | **27** | Engineering UI covered |
| Semantic diagnostics schema | None | **`understanding_trace` stub** | Foundation for 0.6 Reasoning |
| Chat diagnostics v2 UI | None | **Understanding Trace panel** | Debug-only |
| KP legacy visibility | None | **Banner + preset Deprecation header** | Operator clarity |
| DB migrations (RFC-100) | 0 | **1** (`0011`) | Additive settings column |
| Production retrieval path | Document-first | Document-first | Unchanged |
| Executive behavior | Passthrough | Passthrough | Unchanged |

### Boundaries respected

| Check | Status |
|-------|--------|
| No reasoning on hot path | ✅ Stub only |
| No retrieval / LLM changes in 0.2 | ✅ |
| Golden does not lock legacy boosts | ✅ Schema test enforces |
| Preset endpoint body unchanged | ✅ Tested |
| Other KP endpoints unmodified (headers) | ✅ Tested |

---

## 6. Remaining debt and next risks

### Remaining technical debt

| Item | Severity | Target release |
|------|----------|----------------|
| `understanding_trace` not populated (stub) | Expected | 0.6 ReasoningService |
| `speech_act` / `self_eval` stubs not added | Low | 0.2+ / MIG-004 remainder |
| `build_boost_tables()` / `category_boost()` dead code | Low | Guards + future removal |
| `CanonicalSourceService` profile doc-type rules | Medium | 0.7–0.8 |
| `RagService` / RPS god classes | High | 0.6 split |
| KP presets still functional | Medium | `allow_legacy_kp_presets` @ 0.8 |
| Executive passthrough only | Medium | 0.6 orchestration |
| No epistemic memory | High | 0.4 |
| Score-centric production diagnostics | Medium | Partially addressed (engineering panel only) |

### Risks for Release 0.3+

| Risk | Mitigation |
|------|------------|
| Operators enable `enable_semantic_diagnostics_v2` expecting real reasoning | Banner + stub `populated: false`; docs in FEATURE_FLAGS |
| Forgotten Alembic `0011` on deploy | Startup migration check; pre-deploy checklist |
| Golden CI time growth (30 queries) | Still &lt;1 s unit; monitor if expanded to 100 |
| Preset deprecation header breaks unknown clients | Header-only; body unchanged; tested |
| Parallel 0.1 Executive staging still pending | Non-blocking for 0.2 ship with flags OFF |

---

## 7. Release decision

### **READY FOR RELEASE**

Release 0.2 engineering deliverables are complete. Ship with:

- `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false`
- `enable_semantic_diagnostics_v2=false` (DB default after `0011`)
- Run `alembic upgrade head` before deploy

Production chat behavior remains equivalent to Release 0.1. New surfaces are **debug-only** (understanding trace) or **informational** (KP banner, preset deprecation header).

### Conditions (non-blocking for production ship with flags OFF)

| Item | Owner | When |
|------|-------|------|
| Apply migration `0011` on all environments | Ops | Deploy |
| Staging validation: semantic diagnostics panel | Ops | Before enabling flag ON |
| Staging Executive shadow (0.1 carryover) | Ops | Per `0.1-rollback.md` |
| HTTP golden in CI | Platform | When `POSTGRES_TEST_URL` available |

### Blocking issues

**None** for Release 0.2 with default flags OFF and migration applied.

### Recommendation

**Proceed to Release 0.3** (Steps 020–026: `memory_version`, `MemoryVersionService`, cache namespace v2) after review. Do not start Step 020 until this report is accepted.

---

## Appendix A — New / modified artifacts (0.2)

| Area | Path |
|------|------|
| Semantic diagnostics schema | `backend/app/schemas/semantic_diagnostics.py` |
| Builder plumbing | `backend/app/services/chat_response_builder.py` |
| Feature flag helper | `backend/app/services/feature_flags.py` |
| Migration | `backend/migrations/versions/0011_semantic_diagnostics_v2.py` |
| Dashboard panel | `dashboard/src/components/chat/UnderstandingTracePanel.tsx` |
| KP legacy banner | `dashboard/src/components/knowledge-profile/KnowledgeProfileLegacyBanner.tsx` |
| KP deprecation headers | `backend/app/api/knowledge_profile_deprecation.py` |
| Golden queries | `backend/tests/golden/queries.json` |
| Golden guide | `backend/tests/golden/README.md` |
| Rollback runbook | `docs/releases/0.2-rollback.md` |

## Appendix B — CI verification command (full 0.2 suite)

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
  tests/test_semantic_diagnostics_schema.py \
  tests/test_chat_response_builder.py \
  tests/test_knowledge_profile_preset_deprecation.py \
  -v -m unit

cd ../dashboard
npm test && npx tsc --noEmit
```

**Expected:** 131 backend + 27 dashboard tests passed (2026-07-05).

## Appendix C — Document index

| Document | Path |
|----------|------|
| RFC-100 strategy | `docs/RFC-100-PRODUCTION-MIGRATION-STRATEGY.md` |
| Feature flags | `docs/FEATURE_FLAGS.md` |
| Release 0.1 report | `docs/releases/RELEASE-0.1-ACCEPTANCE-REPORT.md` |
| Release 0.1 rollback | `docs/releases/0.1-rollback.md` |
| Release 0.2 rollback | `docs/releases/0.2-rollback.md` |
| Golden suite | `backend/tests/golden/README.md` |
