# Release 0.6 — Engineering Acceptance Report

**Date:** 2026-07-28  
**RFC:** RFC-100 Production Migration Strategy  
**Git commit (Steps 043–045):** `11d29b2410aa232534099c5858de5eaa93f71c62`  
**Closure commit:** (see git log after this document)  
**Runtime flags:** all OFF (default)

---

## 1. Executive summary

Release 0.6 delivers the **Reasoning cognitive pipeline**: a stateless `ReasoningService` seam, optional `EvidenceAssemblyService` coordination, advisory evidence sufficiency, typed speech-act selection, and Language rendering behind an independent flag. **Default runtime behavior is unchanged** — all migration flags remain OFF.

Engineering acceptance is **PASS**. Staging validation with flags ON has **not** been performed. Production readiness is **not** claimed.

---

## 2. Steps 039–045 delivered

| Step | Deliverable | Status |
|------|-------------|--------|
| **039** | `ReasoningService` extracted from RPS | ✅ |
| **040** | `EvidenceAssemblyService` seam | ✅ |
| **041** | Thin RPS coordinator when Reasoning + EA ON | ✅ |
| **042** | Migration Confidence Gate (8-flag matrix) | ✅ |
| **043** | Advisory evidence sufficiency | ✅ |
| **044** | Advisory speech-act selection (answer/qualify/clarify/refuse) | ✅ |
| **045** | Language speech-act rendering (`REASONING_SPEECH_ACTS_ENABLED`) | ✅ |

Release docs: `docs/releases/0.6-step-039-reasoning-service.md` through `0.6-step-045-speech-act-language.md`.

---

## 3. Architecture delta from Release 0.5

| Area | Release 0.5 | Release 0.6 |
|------|-------------|---------------|
| Chat routing | Executive optional passthrough → Rag | + Reasoning seam (flag OFF = legacy) |
| Retrieval | RPS inside Rag | + optional EA assemble stage (flagged) |
| Post-retrieval cognition | None in chat | Sufficiency + speech-act **diagnostics** (Reasoning ON) |
| User-visible language | Rag LLM only | Optional clarify/refuse/qualify (both flags ON) |
| Epistemic Memory in chat | Not used | Still not used |
| Tensions in chat | Not used | Still diagnostics-only (admin API) |

---

## 4. ReasoningService responsibilities

- Stateless per-request coordinator (no answer/claim/tension caches).
- When `REASONING_SERVICE_ENABLED`: wraps `RagService` / streaming with optional `pipeline_provider`.
- Steps 043–044: `assess_evidence_sufficiency` + `select_speech_act` after retrieval.
- Step 045: passes `apply_speech_acts` when `REASONING_SPEECH_ACTS_ENABLED`.
- Does **not** render final language strings (except delegating to Rag/Language).
- Does **not** read Epistemic Memory or tensions for chat.

---

## 5. EvidenceAssemblyService responsibilities

- Thin wrapper over DFP assemble stage (Step 040).
- Activated only when `EVIDENCE_ASSEMBLY_ENABLED` and Reasoning provides coordinator.
- Does not own sufficiency, speech acts, or LLM generation.

---

## 6. Remaining RagService responsibilities

- Single retrieval execution per turn.
- Retrieval cache read/write.
- LLM generation for answer/qualify paths.
- Language speech-act application when `apply_speech_acts=True` (Step 045).
- Session persistence, source formatting, trace integration.
- Legacy path when all migration flags OFF.

---

## 7. Speech-act behavior matrix

| Reasoning | `REASONING_SPEECH_ACTS_ENABLED` | User-visible behavior |
|-----------|--------------------------------|------------------------|
| OFF | * | Exact legacy |
| ON | OFF | Step 044 advisory diagnostics only |
| ON | ON | Language applies act |

| Act | LLM calls | Sources |
|-----|-----------|---------|
| answer | ≤1 (legacy) | Preserved |
| qualify | ≤1 + suffix | Preserved |
| clarify | 0 (deterministic UK/EN) | Dropped |
| refuse | 0 (deterministic UK/EN) | Dropped |

---

## 8. Cache behavior

- `speech_act_language` namespace segment: `"v1"` when speech acts active, `"off"` otherwise.
- Advisory-only (Reasoning ON, speech acts OFF) shares legacy cache namespace with flags OFF.
- No corpus mutation on cache operations.

---

## 9. Streaming behavior

- `ReasoningService.answer_stream` mirrors non-stream flag matrix.
- Deterministic clarify/refuse: early final event, no duplicate LLM stream.
- Semantically equivalent diagnostics on `final` event.

---

## 10. Migration Confidence Gate results

- **Suite:** `tests/test_migration_confidence_gate.py`
- **Coverage:** 8 combinations of Executive / Reasoning / Evidence Assembly flags.
- **Asserts:** single retrieval execution, single LLM call where applicable, stream order parity, error propagation.
- **Result:** PASS (included in `make release-check` backend unit suite).

---

## 11. Test results

| Gate | Result |
|------|--------|
| `make release-check` | **PASS** (8 steps) |
| Backend pure unit tests | **PASS** (~332 tests, no app DB) |
| Deploy rsync excludes regression | **PASS** |
| Golden parity | **PASS** (40 tests) |
| Dashboard vitest | **PASS** (252 tests) |
| TypeScript `tsc --noEmit` | **PASS** |
| Dashboard production build | **PASS** |
| Migration DB test | **SKIP** (no `POSTGRES_TEST_URL`) |
| Step 043–045 focused suite | **PASS** (205 tests) |

---

## 12. Performance / call-count impact

**Flags OFF (production default):** Zero additional retrieval or LLM calls — identical to Release 0.5.

**Flags ON (staging only):**

| Path | Retrieval | LLM |
|------|-----------|-----|
| answer / qualify | 1 | ≤1 |
| clarify / refuse | 1 | 0 |

Migration Confidence Gate enforces single execution per combo in unit tests.

---

## 13. Database incident closure reference

- **Incident:** 2026-07-27 shared test DB wipe.
- **Postmortem:** `docs/incidents/2026-07-27-shared-test-db-wipe.md` — **CLOSED**.
- **Canonical DB:** `ai_site_agent` (5023 sources, 17958 chunks restored).
- **Rollback DB:** `ai_site_agent_recovery` retained, not used by runtime.

---

## 14. Database safety verification

- No `POSTGRES_TEST_URL` → `DATABASE_URL` fallback.
- `make_engine(fresh=True)` refuses `ai_site_agent`.
- `release-check` skips destructive DB tests without disposable test URL.
- Corpus immutable through closure validation (see §Corpus immutability below).

---

## 15. Feature flags and defaults

| Flag | Default | Active at closure |
|------|---------|-------------------|
| `KNOWLEDGE_OS_EXECUTIVE_ENABLED` | false | false |
| `REASONING_SERVICE_ENABLED` | false | false |
| `EVIDENCE_ASSEMBLY_ENABLED` | false | false |
| `REASONING_SPEECH_ACTS_ENABLED` | false | false |
| `enable_semantic_diagnostics_v2` | false | false |
| `cache_namespace_v2_enabled` | false | false |
| `memory_shadow_write_enabled` | false | false |

`GET /api/build` reports `code_present`, `value`, and `active` per capability.

---

## 16. Rollback procedures

See [`0.6-rollback.md`](0.6-rollback.md) — five levels from speech-act flag OFF through code revert. No database rollback required for feature flags.

---

## 17. Architecture health

| Principle | Status |
|-----------|--------|
| Executive orchestration-only | ✅ |
| Reasoning stateless | ✅ |
| Reasoning owns sufficiency + speech-act **decisions** | ✅ |
| Language owns **wording** only | ✅ |
| Evidence Assembly thin | ✅ |
| Single retrieval execution | ✅ (gate tested) |
| ≤1 LLM for answer/qualify | ✅ |
| Epistemic Memory not in chat | ✅ |
| Tensions diagnostics-only | ✅ |
| RagService legacy orchestrator | ✅ |
| No new God Service | ✅ |

---

## 18. Remaining technical debt

| Item | Severity |
|------|----------|
| Staging validation with flags ON not recorded | Medium — required before production enablement |
| Runtime `/api/build` on live process may lag until restart/deploy | Low |
| Epistemic test rows (33 test claims) not cleaned | Low — deferred |
| One-click `reindex-all` / `reset-db` still operator-destructive | Medium — operational hardening |
| RFC index titles 043–045 differ from delivered scope | Documented in RFC-100 reconciliation note |
| `ai_site_agent_recovery` retention | Operational — remove only after observation period |

---

## 19. Release decision

| Classification | Verdict |
|----------------|---------|
| **Engineering Ready** | **PASS** — code committed, tests green, corpus immutable |
| **Staging Validated** | **NOT CLAIMED** — no flag-ON staging run recorded |
| **Production Ready** | **NOT CLAIMED** — flags remain OFF |

**Release 0.6 engineering closure:** **ACCEPTED** (`closed_0_6: true` in repository metadata).

---

## 20. Readiness for Release 0.7

**Next step:** RFC-100 **Step 046** — Memory read views: claims by region.

**Prerequisites met for planning:**

- Reasoning seam stable and tested.
- No chat dependency on Epistemic Memory yet.
- Migration flags OFF preserves legacy production behavior.

**Before Step 046 implementation:** optional staging run with Reasoning flags ON; epistemic test-row cleanup (operator decision).

---

## Corpus immutability (closure validation)

| Metric | Before | After |
|--------|--------|-------|
| Database | `ai_site_agent` | `ai_site_agent` |
| Sources | 5023 | 5023 |
| Chunks | 17958 | 17958 |
| `fixture.example` | 0 | 0 |
| Qdrant points | 18780 | 18780 |
| `knowledge_version` | 26 | 26 |
| `memory_version` | 177 | 177 |
| `ai_site_agent_recovery` sources | 5023 | 5023 (untouched) |

No reindex. No Qdrant modification. No fixture insertion.

---

## Deploy safety (closure)

| Check | Result |
|-------|--------|
| Repo `manage_deploy.sh` excludes `.env` | ✅ |
| `/opt` script synchronized | ✅ SHA256 `955bd5de…` (before: `b3653b1f…`) |
| Regression test `test-deploy-rsync-excludes.sh` | ✅ in `release-check` |

---

## References

- `docs/REASONING_SERVICE.md`
- `docs/LANGUAGE_SPEECH_ACTS.md`
- `docs/FEATURE_FLAGS.md`
- `docs/MIGRATION_CONFIDENCE_REPORT.md`
- `docs/RFC-100-PRODUCTION-MIGRATION-STRATEGY.md` (Release 0.6 reconciliation note)
