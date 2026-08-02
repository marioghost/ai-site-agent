# Feature Flags — Knowledge OS Migration

**RFC-100 Release 0.1+** (updated **Release 1.0 Step 063** — Knowledge OS flags default **ON**)  
**Owner:** Platform / migration lead  
**Principle:** Default **ON** for Knowledge OS path at Release 1.0 (Step 063). Legacy surfaces stay **OFF**. Kill-switch = explicit `false` + restart (unset no longer disables env flags).

This registry tracks migration flags only. Existing Settings toggles (reranking, caches, tracing, etc.) are unchanged and documented in the dashboard Settings UI.

---

## Naming convention

```
knowledge_os_<subsystem>_<behavior>_enabled   # env: KNOWLEDGE_OS_<SUBSYSTEM>_<BEHAVIOR>_ENABLED
enable_<feature>_v2                           # Settings column (diagnostics, cache)
allow_legacy_<surface>                        # deprecation gates
```

---

## Active flags (implemented)

| Flag | Surface | Default | Purpose | Activate when | Rollback | Remove |
|------|---------|---------|---------|---------------|----------|--------|
| `knowledge_os_executive_enabled` | Env `KNOWLEDGE_OS_EXECUTIVE_ENABLED` | **true** | Sole API entry for `/api/chat` and `/api/chat/stream` via `ExecutiveService`. Explicit `false` = hard kill-switch (HTTP 503 / SSE `executive_disabled`); no API fallback to Rag or Reasoning (Step 064) | Default ON (Step 063) | Set env `false`; restart — Ask becomes controlled unavailable | After 1.0 stabilization |
| `reasoning_service_enabled` | Env `REASONING_SERVICE_ENABLED` | **true** | Route chat through `ReasoningService` (Steps 039–045). With EA also ON (Step 041), Reasoning orders RPS prepare→assemble→finalize once. Steps 043–044 add sufficiency + speech-act diagnostics; Step 045 Language UX requires `REASONING_SPEECH_ACTS_ENABLED` | Default ON (Step 063) | Set env `false`; restart | After 1.0 stabilization |
| `evidence_assembly_enabled` | Env `EVIDENCE_ASSEMBLY_ENABLED` | **true** | Route RPS assemble stage through `EvidenceAssemblyService` (Step 040). With Reasoning also ON, Reasoning coordinates that stage | Default ON (Step 063) | Set env `false`; restart | After 1.0 stabilization |
| `reasoning_speech_acts_enabled` | Env `REASONING_SPEECH_ACTS_ENABLED` | **true** | Language consumes Reasoning speech acts (Step 045). **No effect when Reasoning OFF.** When Reasoning ON + this OFF → Step 044 advisory-only. When both ON → clarify/refuse deterministic; qualify limitation; answer unchanged | Default ON (Step 063) | Set env `false`; restart | After 1.0 stabilization |

**Step 042 / 064:** Pipeline confidence matrix is Reasoning × Evidence Assembly under Executive=ON (4 combos). Executive=`false` is the Step 064 emergency kill-switch — see Step 064 tests. Historical Step 042 also validated pre-064 8-way flag combos — see [MIGRATION_CONFIDENCE_REPORT.md](MIGRATION_CONFIDENCE_REPORT.md).
| `enable_semantic_diagnostics_v2` | Settings DB column | **true** | Additive debug field `understanding_trace` stub on chat responses when client `debug=true` | Default ON (Step 063 / migration `0020`) | Set Settings `false`; restart not required | After 1.0 stabilization |
| `cache_namespace_v2_enabled` | Settings DB column | **true** | Include `memory_version` in retrieval/answer cache namespace hash via `MemoryVersionService` | Default ON (Step 063 / migration `0020`) | Set Settings `false`; restart not required | After 1.0 stabilization |
| `memory_shadow_write_enabled` | Settings DB column | **true** | After SI generation, persist claim proposals to epistemic tables (shadow only; no retrieval/chat use) | Default ON (Step 063 / migration `0020`) | Set Settings `false`; restart not required | After 1.0 stabilization |
| `memory_evidence_assist_enabled` | Settings DB column | **true** | Advisory Memory region read in Reasoning before Evidence Assembly (Step 047) | Default ON (Step 063); effective when Reasoning + `cache_namespace_v2` ON | Set Settings `false`; restart not required | After 1.0 stabilization |
| `memory_canonical_shadow_enabled` | Settings DB column | **true** | Diagnostic Memory vs retrieval source-set comparison (Step 048); no answer influence | Default ON (Step 063); effective when Reasoning + assist + cache v2 ON | Set Settings `false`; restart not required | After 1.0 stabilization |
| `allow_legacy_kp_presets` | Settings DB column | **false** | Allow GET/POST Knowledge Profile industry preset APIs; **410** when false (Step 054) | Ops rollback only — keep false in normal operation | Set Settings `true` | Release 1.0+ |
| `legacy_doc_type_canonical_enabled` | Settings DB column | **false** | When true, RPS finalize runs KP doc-type CanonicalSourceService reorder; when false, skip (Step 055) | Ops rollback to restore pre-055 reorder | Set Settings `true` | Release 1.0+ |
| `MAINTENANCE_EXECUTION_ENABLED` | Env | **true** when unset | Gate maintenance investigation execution (Step 059+) | Default ON unset (Step 063); budget still defaults to **0** (no work) | Set env `false`; restart | After 1.0 stabilization |

**Step 046 (Memory read views):** no runtime flag — `read_region()` is internal-only until Step 047 wires assist.

**Release 1.0 Step 063:** Knowledge OS env + Settings flags above default **ON**. Legacy KP/doc-type flags remain **false**. See [1.0-step-063-implementation.md](releases/1.0-step-063-implementation.md).

**Release 1.0 Step 064:** API chat dispatch is **Executive-only**. `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false` is a hard controlled-unavailable kill-switch (HTTP 503 / SSE `error_type=executive_disabled`). Internal Executive → Reasoning / Rag degradation is unchanged. See [1.0-step-064-implementation.md](releases/1.0-step-064-implementation.md).

**Release 0.7–0.9 (historical):** Flags shipped default OFF through Release 0.9 engineering closure. Do not rewrite historical acceptance reports.

### `enable_semantic_diagnostics_v2`

**Code:** `app/models/settings.py` → `app/services/feature_flags.py` → `app/services/chat_response_builder.py` → `app/api/chat.py`

**Behavior when OFF:**

- `ChatResponse.understanding_trace` remains `null` (unchanged from Release 0.1)
- Explicit `understanding_trace` in stream payloads is preserved (forward compat)

**Behavior when ON (default as of Step 063) + client `debug=true` + `enable_chat_debug_payload=true`:**

- Response includes empty `understanding_trace` stub (`version: "stub"`, `populated: false`)
- Persisted session diagnostics JSON includes the same stub

**Behavior when ON + debug disabled:**

- No `understanding_trace` stub added

**Verification:**

```bash
cd backend
.venv/bin/pytest tests/test_semantic_diagnostics_schema.py tests/test_golden_chat_parity.py -v -m unit
```

---

### `knowledge_os_executive_enabled`

**Code:** `app/core/config.py` → `app/services/feature_flags.py` → `app/api/chat.py`

**Behavior when OFF (kill-switch, Step 064):**

- `_dispatch_non_stream_answer()` → HTTP **503** (`EXECUTIVE_DISABLED_DETAIL`); no Executive / Reasoning / Rag
- `_dispatch_stream_events()` → one SSE `error` with `error_type=executive_disabled`; stream closes
- Structured logs: `path=executive_disabled` (before orchestration)
- **No** API fallback to Rag or Reasoning

**Behavior when ON / unset (default as of Step 063):**

- Both routes call `ExecutiveService` exactly once (sole API orchestration entry)
- Internal: Executive → Reasoning (when enabled) or Executive-owned Rag degrade
- Structured logs: `path=executive`

**User-visible impact (normal path):** None when Executive remains enabled — Ask contracts unchanged.

**Verification:**

```bash
cd backend
.venv/bin/pytest tests/test_chat_executive_routing.py tests/test_chat_stream_executive_routing.py \
  tests/test_step_064_executive_sole_entry.py tests/test_executive_service.py \
  tests/test_golden_chat_parity.py -v -m unit
```

---

### `cache_namespace_v2_enabled`

**Code:** `app/models/settings.py` → `app/services/feature_flags.py` → `app/services/cache_namespace_service.py` → `RagService` / `RagStreamingService`

**Behavior when OFF (kill-switch):**

- Cache namespace dict matches pre-v2 behavior
- `memory_version` on the settings row is **ignored** for cache keys
- Existing retrieval and answer cache entries remain valid

**Behavior when ON (default as of Step 063):**

- `build_retrieval_namespace(..., db=session)` adds `memory_version` from **`MemoryVersionService.get()`**
- Bumping `memory_version` (manual Step 022 API or Step 031 auto-bump on new shadow rows) produces a new namespace hash → cache miss on next lookup
- `knowledge_version` / `index_version` behavior unchanged

**Does not:**

- Auto-bump `memory_version`
- Change cache storage schema or TTL logic
- Change chat, retrieval, or Executive paths

**Verification:**

```bash
cd backend
.venv/bin/pytest tests/test_cache_namespace_v2.py tests/test_caching.py tests/test_cache_safety.py -m unit -v
```

**Deploy:** requires migration `0013_cache_namespace_v2_enabled` (`alembic upgrade head`).

---

### `memory_shadow_write_enabled`

**Code:** `app/models/settings.py` → `app/services/feature_flags.py` → `EpistemicMemoryIntegrationService` → SI generation / inline indexing hooks

**Behavior when OFF (default):**

- Zero epistemic writes, zero `memory_version` bumps from shadow path
- Production runtime unchanged

**Behavior when ON:**

- After SI generation: `ClaimExtractionFromSI` → idempotent persist via `EpistemicMemoryService`
- `MemoryVersionService.bump(commit=False)` **only** when at least one new observation, claim, or evidence link is created (Step 031)
- Bump commits with the caller transaction (SI batch / indexing save)

**Does not:**

- Use Epistemic Memory for chat, retrieval, or reasoning
- Change `knowledge_version`
- Invalidate caches unless `cache_namespace_v2_enabled=true` (memory bump then changes namespace hash)

**Why auto-bump matters:** epistemic state can change without reindexing. Before memory-assisted evidence (Release 0.7+), consumers need a revision signal; with cache namespace v2 ON, bumps invalidate stale cached answers.

**Verification:**

```bash
cd backend
.venv/bin/pytest \
  tests/test_epistemic_memory_shadow_write.py \
  tests/test_epistemic_shadow_memory_version_bump.py \
  tests/test_epistemic_memory_roundtrip.py \
  tests/test_claim_extraction_from_si.py \
  -m unit -v
```

**Release 0.4:** Implemented (Steps 027–033). Default OFF — zero production behavior change until explicitly enabled in staging.

**Deploy:** requires migrations `0014_epistemic_memory_tables` and `0015_memory_shadow_write_enabled` (`alembic upgrade head`).

See [RELEASE-0.4-ACCEPTANCE-REPORT.md](releases/RELEASE-0.4-ACCEPTANCE-REPORT.md) and [0.4-rollback.md](releases/0.4-rollback.md).

---

## Planned flags (not implemented yet)

Do **not** enable until the release step that introduces them.

| Flag | Release | Purpose |
|------|---------|---------|
| `claim_extraction_enabled` | 0.4 | SI → claim proposals (optional gate; extraction runs inside shadow hook today) |
| `tension_surfacing_enabled` | 0.5 | Optional future gate for dashboard. Steps 035–036 ship admin-auth-gated; taxonomy owned by `TensionSurfacingService` ([ADR-0002](adr/0002-tension-taxonomy-ownership.md)). |
| `maintenance_execution_enabled` | 0.9 | Budgeted active maintenance investigations |

---

### `memory_evidence_assist_enabled` (Step 047)

**Code:** `memory_assist_policy.py` → `ReasoningService._coordinate_pipeline` → `cache_namespace_service.py`

**Effective when:** `REASONING_SERVICE_ENABLED` + flag ON + `cache_namespace_v2_enabled`.

**Behavior when OFF (default):** Zero Memory reads on chat path; assist diagnostics absent.

**Does not:** Change retrieval ranking, canonical selection, prompts, LLM inputs, or answers.

**Deploy:** migration `0016_memory_evidence_assist_enabled`.

See [0.7-step-047-memory-evidence-assist.md](releases/0.7-step-047-memory-evidence-assist.md).

---

### Step 049 — no feature flag

Offline Memory Assist evaluation (`app/services/evaluation/`) introduces **no** Settings or env flag. It consumes frozen diagnostics only and never enables assist/shadow.

See [0.7-step-049-offline-memory-eval.md](releases/0.7-step-049-offline-memory-eval.md).

### `memory_canonical_shadow_enabled` (Step 048)

**Code:** `memory_canonical_shadow_comparator.py` → `ReasoningService._coordinate_pipeline`

**Effective when:** Reasoning ON + assist ON + cache v2 ON + shadow flag ON.

**Behavior when OFF (default):** Comparator returns `path=off`; zero shadow diagnostics.

**Does not:** Perform retrieval, Memory reads, or influence answers. Skipped on answer cache hit.

**Deploy:** migration `0017_memory_canonical_shadow_enabled`.

See [0.7-step-048-memory-canonical-shadow.md](releases/0.7-step-048-memory-canonical-shadow.md).

### `allow_legacy_kp_presets` (Step 054)

**Code:** `feature_flags.allow_legacy_kp_presets` → `api/knowledge_profile.py` (`list_presets`, `load_preset`)

**Default:** **false** (Settings column; migration `0018_allow_legacy_kp_presets`).

**Behavior when OFF (default):**

- `GET /api/knowledge-profile/presets` → **410** (`legacy_kp_presets_disabled`)
- `POST /api/knowledge-profile/presets/load` → **410** (same detail)
- Stored `knowledge_profile_json` continues to drive chat/retrieval
- Empty JSON still falls back to `generic_corporate`
- Generation/wizard and in-process `PRESETS` remain available to code/tests

**Behavior when ON (rollback):** Preset list/load behave as before Step 054 (including Deprecation headers on successful load).

**Does not:** Change ranking, Memory, Reasoning, cache namespaces, or rewrite profiles.

**Rollback:** Settings PUT `allow_legacy_kp_presets=true`.

**Deploy:** apply migration `0018` only with an approved release deploy — do not apply to `ai_site_agent` during implementation review.

See [0.8-step-054-architecture-review.md](releases/0.8-step-054-architecture-review.md) and [0.8-step-054-implementation.md](releases/0.8-step-054-implementation.md).

### `legacy_doc_type_canonical_enabled` (Step 055)

**Code:** `feature_flags.legacy_doc_type_canonical_enabled` → `RetrievalPipelineService.finalize_pipeline`

**Default:** **false** (Settings column; migration `0019_legacy_doc_type_canonical_enabled`).

**Behavior when OFF (default):** Skip KP document-type `CanonicalSourceService.select_context` reorder; retain post-DFP / broad-inject hit order (downstream bilingual dedupe / ContextBuilder unchanged).

**Behavior when ON (rollback):** Legacy doc-type reorder runs when `enable_canonical_source_selection` is also true.

**Does not:** Change DocumentScorer, Memory Assist, canonical shadow, or implement Memory authority selection.

**Rollback:** Settings PUT `legacy_doc_type_canonical_enabled=true`.

**Cache:** Flag is part of retrieval cache namespace fingerprint.

**Deploy:** apply migration `0019` only with an approved release deploy — do not apply to `ai_site_agent` during implementation review.

See [0.8-step-055-architecture-review.md](releases/0.8-step-055-architecture-review.md) and [0.8-step-055-implementation.md](releases/0.8-step-055-implementation.md).

### Release 0.7 closure (Step 050)

Engineering accepted — [RELEASE-0.7-ACCEPTANCE-REPORT.md](releases/RELEASE-0.7-ACCEPTANCE-REPORT.md), [0.7-rollback.md](releases/0.7-rollback.md). Flags remain OFF; staging_validated=false; production_ready=false.

### Release 0.8 closure

Engineering accepted — [RELEASE-0.8-ACCEPTANCE-REPORT.md](releases/RELEASE-0.8-ACCEPTANCE-REPORT.md), [0.8-rollback.md](releases/0.8-rollback.md). `closed_0_8=true`; staging_validated=false; production_ready=false. Migrations 0018/0019 not claimed applied live.

---

## Kill-switch procedure

Use when Executive path causes regression in staging or production.

1. **Disable flag:** set `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false` and restart backend pods/processes.
   (**Do not** rely on unsetting the variable — as of Step 063, unset means **ON**.)
2. **Expect controlled unavailable (Step 064):**
   - `POST /api/chat` → HTTP **503** with operator detail that Executive was disabled.
   - `POST /api/chat/stream` → SSE `error` with `error_type=executive_disabled` (no token/final).
   - **No** fallback to direct RagService, RagStreamingService, or ReasoningService.
3. **Clear caches** (optional): Admin → clear retrieval / semantic answer cache if needed after recovery.
4. **Verify:** logs show `path=executive_disabled` on new chat requests; golden unit suite still green for Executive ON.
5. **Recover:** set `KNOWLEDGE_OS_EXECUTIVE_ENABLED=true` (or unset) and restart; confirm `path=executive`.
6. **Post-mortem** within 24h if production was affected.

Disabling `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false` is the primary chat-path kill-switch (hard unavailable as of Step 064).

---

## Golden smoke verification

**CI (required on every PR touching chat/RAG):**

```bash
cd backend
.venv/bin/pytest tests/test_golden_chat_parity.py tests/test_golden_queries_schema.py -v -m unit
```

**Staging shadow (required before enabling flag in staging/prod):**

1. Deploy with Executive **ON** (default after Step 063); confirm golden unit suite green on build.
2. Confirm logs show `path=executive` on Ask requests.
3. Optional: verify kill-switch briefly on staging only (`=false` → 503 / SSE `executive_disabled`), then restore ON.
4. Optional HTTP integration: `POSTGRES_TEST_URL=... GOLDEN_CHAT_LIVE=1 pytest tests/test_golden_chat_parity.py -m integration`

See `docs/releases/0.1-rollback.md` for full deploy/rollback steps.

---

## Flag lifecycle

| Phase | Action |
|-------|--------|
| Introduce | Default OFF; document here; add guard/parity tests |
| Staging | Enable; golden + shadow validation |
| Production | Gradual enable or hold OFF until next release gate |
| Default ON | Release 1.0 for core migration flags |
| Remove | Delete flag + dead branch after 2 releases at default ON |

---

## Cross-references

| Document | Role |
|----------|------|
| `RFC-100-PRODUCTION-MIGRATION-STRATEGY.md` | Migration sequence |
| `docs/releases/0.1-rollback.md` | Release 0.1 deploy & rollback |
| `docs/releases/0.2-rollback.md` | Release 0.2 deploy & rollback |
| `docs/releases/RELEASE-0.1-ACCEPTANCE-REPORT.md` | Release 0.1 baseline & decision |
| `docs/releases/RELEASE-0.2-ACCEPTANCE-REPORT.md` | Release 0.2 baseline & decision |
| `docs/releases/RELEASE-0.3-ACCEPTANCE-REPORT.md` | Release 0.3 baseline & Epistemic Memory readiness |
| `docs/releases/0.3-rollback.md` | Release 0.3 deploy & rollback |
| `docs/DEPLOYMENT.md` | Staging pipeline, smoke tests, release gates |
| `docs/releases/RELEASE-CHECKLIST.md` | Pre-production checklist |
| `backend/tests/golden/README.md` | Golden query suite |
