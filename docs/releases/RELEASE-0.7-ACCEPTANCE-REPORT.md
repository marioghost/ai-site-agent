# Release 0.7 — Engineering Acceptance Report

**Date:** 2026-07-28  
**RFC:** RFC-100 Production Migration Strategy  
**Closure step:** Step 050  
**Runtime flags:** all Release 0.7 flags **OFF** (default)

---

## 1. Executive summary

Release 0.7 delivers **Memory integration seams** that remain inactive by default: typed Memory region reads, advisory Memory evidence assist, diagnostic Canonical Shadow comparison, and an offline evaluation gate. **Default runtime behavior is unchanged** — assist and shadow Settings flags remain OFF; no chat path uses Memory propositions.

Engineering acceptance is **PASS**. Staging validation with flags ON has **not** been performed. Production readiness is **not** claimed.

---

## 2. Lifecycle state

| Classification | Verdict |
|----------------|---------|
| **Engineering Ready** | **PASS** |
| **Staging Validated** | **false** — no real staging flag-ON evaluation |
| **Production Ready** | **false** |

Release 0.7 engineering closure may be **ACCEPTED** while staging and production remain pending.

---

## 3. Steps 046–049 delivered

| Step | Deliverable | Status |
|------|-------------|--------|
| **046** | Typed Memory region read views; source + deployment-corpus isolation; read-only, deterministic, bounded; no chat integration | ✅ |
| **047** | Advisory Memory evidence assist in Reasoning; `memory_evidence_assist_enabled` default OFF; one Memory read; fail-open; no EA/DFP input change; no claim proposition injection | ✅ |
| **048** | Diagnostic-only Memory Canonical Shadow; `memory_canonical_shadow_enabled` default OFF; set comparison only; no ranking/prompt/source/answer/cache influence | ✅ |
| **049** | Offline Memory Assist evaluation package; JSON + Markdown reports; `NO_GO` / `CONDITIONAL` / `STAGING_CANDIDATE`; no runtime/DB/network dependency | ✅ |
| **050** | Engineering closure (this report) | ✅ |

Release docs: `docs/releases/0.7-step-046-*.md` through `0.7-step-050-release-closure.md`.

---

## 4. Architecture delta from Release 0.6

| Area | Release 0.6 | Release 0.7 |
|------|-------------|-------------|
| Memory in chat | Not used | Optional advisory assist (flag OFF = unused) |
| Memory reads | Service APIs only | Typed `read_region()` views + corpus isolation |
| Evidence assist | None | Reasoning-owned advisory read before EA |
| Canonical vs Memory | None | Diagnostic shadow set compare (flag OFF) |
| Staging gate | Migration Confidence Gate (0.6) | + Offline Memory Assist eval (049) |
| Reasoning / EA / speech acts | Accepted | Unchanged; flags still OFF by default |

---

## 5. Memory region read contract (Step 046)

- `MemoryRegionRequest` / `MemoryRegionView` typed DTOs.
- Deterministic, bounded, read-only.
- Support/conflict tri-state via `evidence_loaded`.
- Test provenance excluded by default.
- No chat / Rag / Reasoning import of region views until Step 047 assist policy.

---

## 6. Deployment corpus isolation (Step 046 extension)

- `MemoryCorpusScope.DEPLOYMENT` resolves allowed hosts from Settings.
- Fail-closed when corpus boundary cannot be resolved.
- Fingerprint for assist cache identity (Step 047).
- Explicit `source_id` / `source_ids` remain engineering diagnostics only.

---

## 7. Advisory Memory Assist behavior (Step 047)

- Wired in `ReasoningService._coordinate_pipeline` before Evidence Assembly.
- At most **one** Memory region read when effective.
- Does **not** change ranking, selected hits, prompts, or answers.
- Fail-open on timeout/error (limitations recorded; pipeline continues).
- Effective only when Reasoning ON + `memory_evidence_assist_enabled` + `cache_namespace_v2_enabled`.

---

## 8. Canonical Shadow behavior (Step 048)

- Runs after `finalize_pipeline`; set comparison of Memory assist IDs vs retrieval context.
- Does **not** influence ranking, prompts, sources, answers, or caches.
- Skipped on answer-cache hits.
- Effective only when Reasoning + assist + cache v2 + shadow flags are all ON.

---

## 9. Offline evaluation gate (Step 049)

- Package: `app/services/evaluation/` + CLI `scripts/run_memory_assist_eval.py`.
- Consumes frozen diagnostics only — no DB, Qdrant, LLM, or flag mutation.
- Recommendations are engineering gates, not knowledge-accuracy claims.
- Synthetic fixtures validated; **real staging harvest not yet performed**.

---

## 10. Feature-flag matrix

| Flag | Surface | Default | Effective prerequisites | Closure state |
|------|---------|---------|-------------------------|---------------|
| `memory_evidence_assist_enabled` | Settings | false | Reasoning + cache v2 | **OFF** |
| `memory_canonical_shadow_enabled` | Settings | false | Reasoning + assist + cache v2 | **OFF** |
| `cache_namespace_v2_enabled` | Settings | false | — | **OFF** |
| `REASONING_SERVICE_ENABLED` | Env | false | — | **OFF** |
| `EVIDENCE_ASSEMBLY_ENABLED` | Env | false | — | **OFF** |
| `KNOWLEDGE_OS_EXECUTIVE_ENABLED` | Env | false | — | **OFF** |
| `REASONING_SPEECH_ACTS_ENABLED` | Env | false | Reasoning | **OFF** |

Step 046 and Step 049 introduce **no** new runtime flags.

---

## 11. Cache contract

- Assist effective → cache namespace includes Memory / corpus fingerprint segments (via cache namespace v2).
- Shadow does not write caches and does not change namespace beyond assist prerequisites.
- Answer-cache hit skips pipeline, assist, and shadow.

---

## 12. Streaming / non-streaming parity

- Assist and shadow attach through the same Reasoning coordination path used by stream and non-stream.
- Diagnostics appear on `final` / `RagResult` without changing streamed answer tokens when flags OFF.
- Golden parity and migration confidence remain green with flags OFF.

---

## 13. Retrieval / Memory / LLM execution counts

**Flags OFF (engineering default):** Zero Memory reads; identical retrieval/LLM counts to Release 0.6.

**When assist (+ shadow) effective (staging experiment only):**

| Resource | Max per uncached turn |
|----------|----------------------|
| Retrieval / DFP | 1 |
| Memory region read | 1 |
| LLM | ≤1 |

---

## 14. Security and source / corpus isolation

- Deployment corpus scope fail-closed.
- Test provenance excluded by default from operational reads.
- Assist/shadow diagnostics carry IDs and counts — not claim/chunk/prompt text in bounded debug payloads.
- Offline eval forbids unrestricted URL dumps and answer/prompt text in reports.

---

## 15. Truth and authority safety

- Memory remains **read-only** during chat.
- Memory propositions **never** enter prompts.
- Assist does not alter Evidence Assembly / DFP inputs.
- Shadow does not declare a “canonical winner” for answers.
- Eval recommendations never authorize production enablement.

---

## 16. Data coverage reality

| Metric (closure snapshot on `ai_site_agent`) | Value |
|-----------------------------------------------|-------|
| Sources | 5023 |
| Chunks | 17958 |
| Claims | 39 |
| Observations | 13 |
| Evidence links | 21 |
| Real Memory coverage | **Sparse** |

**Live readiness for staging activation:** **NO_GO / NOT_EVALUATED** — no real staging diagnostics harvest; synthetic `STAGING_CANDIDATE` fixtures must not be treated as live recommendations.

---

## 17. Test and validation results

Recorded at Step 050 closure (see closure note for commands):

| Gate | Result |
|------|--------|
| Step 046 region + corpus-scope tests | PASS |
| Step 047 assist tests | PASS |
| Step 048 shadow tests | PASS |
| Step 049 eval + `make test-memory-eval` | PASS |
| Reasoning / EA / cache / streaming suites | PASS |
| Golden parity | PASS |
| Migration confidence (unit) | PASS |
| `make release-check` | PASS |
| Live migration on `ai_site_agent` | **Not applied** (correct) |
| Disposable migration test | SKIP unless `POSTGRES_TEST_URL` set |

---

## 18. Migration chain

```
0016_memory_evidence_assist_enabled
  → 0017_memory_canonical_shadow_enabled  (code head)
```

- Single Alembic head in repository.
- Both migrations additive; defaults `false`; downgrades drop only own columns.
- **Not applied** to `ai_site_agent` during engineering closure.

---

## 19. Git commit inventory

| Conceptual step | Commit | Title |
|-----------------|--------|-------|
| 046 read views + contract hardening | `118cd7592c93b1969f526c2b111d5332f2c401a5` | `fix(memory): harden Step 046 read-view contracts` |
| 046 deployment corpus scope | `ceae6df7f288d094fd83e0ea0f43cef529377d00` | `feat(memory): add deployment corpus scope to region reads` |
| 047 advisory Memory assist | `f0e583dfaaa4a670cab9e0700cb92f655a1b1ae2` | `feat(reasoning): add advisory memory evidence assist` |
| 049 offline evaluation gate | `3ef647be3e1b814c763ffa58dd57ed425901c2df` | `feat(evaluation): add offline memory assist release gate` |
| 048 Memory Canonical Shadow | `367615baf693358a5695e1c24d594d1502aad897` | `feat(reasoning): add memory canonical shadow diagnostics` |
| 050 engineering closure | *(this closure commit)* | `chore(release): close Release 0.7 engineering checkpoint` |

### Chronological inversion (historical only)

Step **049** (`3ef647b`) was committed **before** the Step **048** repair commit (`367615b`). History was **not** rewritten. The final tree contains all dependencies; the inversion is chronological only and does not affect runtime correctness.

---

## 20. Architecture health

All Release 0.7 invariants hold under flags OFF (see snapshot §10 and Step 050 health review):

- Legacy answers preserved; single retrieval; ≤1 LLM; Memory read-only; no proposition injection; shadow non-influencing; eval offline-only; corpus fail-closed; no Qdrant/corpus writes; independent `knowledge_version` / `memory_version`.

---

## 21. Remaining technical debt

| Item | Blocks engineering closure? |
|------|----------------------------|
| RagService remains runtime request owner | No |
| Reasoning still wraps Rag | No |
| Language activation still inside Rag | No |
| RPS finalize retains canonical/context policy | No |
| Real Memory coverage sparse | No (blocks **staging activation**) |
| PostgreSQL integration tests need disposable `POSTGRES_TEST_URL` | No |
| Real staging evaluation pending | No (blocks **Staging Validated**) |

---

## 22. Staging activation prerequisites

1. Deploy Release 0.7 code; apply migrations **0016–0017** on staging DB only after backup.
2. Restart backend; verify `/api/health` and `/api/build`.
3. Smoke with **all new flags OFF**.
4. Harvest controlled real staging diagnostics.
5. Run Step 049 evaluator on **real** diagnostics.
6. Review `NO_GO` / `CONDITIONAL` / `STAGING_CANDIDATE`.
7. Enable assist/shadow only under a separately approved controlled experiment.

See [0.7-rollback.md](0.7-rollback.md) and post-closure ops plan in the Step 050 note.

---

## 23. Rollback strategy

Preferred path: disable Settings/env flags (no data deletion, no reindex, no Qdrant clear). Full levels: [0.7-rollback.md](0.7-rollback.md).

`ai_site_agent_recovery` is **not** a feature rollback mechanism.

---

## 24. Release decision

| Classification | Verdict |
|----------------|---------|
| **Engineering Ready** | **PASS** |
| **Staging Validated** | **false** |
| **Production Ready** | **false** |

**Release 0.7 engineering closure:** **ACCEPTED** (`closed_0_7: true` in repository metadata).

---

## 25. Readiness for Release 0.8

**Release 0.8 has not started.**

Planning may begin only after this closure is recorded. Implementation of Release 0.8 roadmap items (boost cleanup, legacy KP presets, Memory-influencing canonical paths, etc.) is **out of scope** for this checkpoint.

---

## Corpus immutability (closure validation)

| Metric | Before | After |
|--------|--------|-------|
| Database | `ai_site_agent` | `ai_site_agent` |
| Sources | 5023 | 5023 |
| Chunks | 17958 | 17958 |
| Claims | 39 | 39 |
| Observations | 13 | 13 |
| Evidence links | 21 | 21 |
| `fixture.example` sources | 0 | 0 |
| `knowledge_version` | 20 | 20 |
| `memory_version` | 10 | 10 |
| Migrations 0016–0017 on `ai_site_agent` | absent | absent |
| Qdrant | not modified | not modified |

---

## References

- [0.7-rollback.md](0.7-rollback.md)
- [0.7-step-050-release-closure.md](0.7-step-050-release-closure.md)
- [FEATURE_FLAGS.md](../FEATURE_FLAGS.md)
- [REASONING_SERVICE.md](../REASONING_SERVICE.md)
- [EPISTEMIC_MEMORY_SCHEMA.md](../EPISTEMIC_MEMORY_SCHEMA.md)
- [KNOWLEDGE_OS_ARCHITECTURE_SNAPSHOT_0.7.md](../architecture/KNOWLEDGE_OS_ARCHITECTURE_SNAPSHOT_0.7.md)
- [RFC-100-PRODUCTION-MIGRATION-STRATEGY.md](../RFC-100-PRODUCTION-MIGRATION-STRATEGY.md)
