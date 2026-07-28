# ReasoningService (Release 0.6 — Steps 039–045)

**RFC-100** — stateless reasoning seam, evidence-acquisition coordinator,
evidence-sufficiency assessment, and speech-act selection.

## Why it exists

Release 0.6 extracts reasoning ownership from the legacy RAG path. Step 039
created the seam; Step 041 lets Reasoning **order** legacy retrieval adapters
when Evidence Assembly is also enabled; Step 043 adds **source-scoped**
evidence sufficiency; Step 044 selects a **speech act**; Step 045 lets
**Language** consume that act when a dedicated behavior flag is ON.

## What it owns now

| Owns (contract) | Reality |
|-----------------|---------|
| Chat-turn reasoning entry | ✅ `run` / `answer` / `answer_stream` |
| Typed request/result DTOs | ✅ `ReasoningRequest` / `ReasoningResult` |
| Path diagnostics | ✅ `reasoning_path=reasoning_service` |
| Evidence acquisition order (both flags ON) | ✅ `prepare → assemble → finalize` via RPS adapters |
| Evidence sufficiency (Step 043) | ✅ advisory / used by speech-act selection |
| Speech act (Step 044) | ✅ selection + diagnostics |
| Language activation (Step 045) | ✅ via `REASONING_SPEECH_ACTS_ENABLED` (Language renders) |

## Evidence sufficiency (Step 043)

Sufficiency answers only:

> Does the available **website** evidence appear sufficient to support the
> requested response?

It is **not** confidence in world truth. Completeness for list/enumeration
questions is especially uncertain and surfaces as `completeness_risk=true`
with status `unknown`.

## Speech acts (Steps 044–045)

Reasoning selects one of: `answer` | `qualify` | `clarify` | `refuse`.

| Policy (v1) | Speech act |
|-------------|------------|
| Narrow fact + sufficient evidence | `answer` |
| Completeness risk / enumeration | `qualify` |
| Ambiguous / underspecified need | `clarify` |
| No usable evidence / invalid provenance | `refuse` |
| Sufficiency unknown with some evidence | `qualify` |

**Refusal means** “insufficient **site** evidence,” not “false in the world.”
**Qualify** is preferred over false certainty.

Reasoning emits a concise typed language instruction (e.g.
`QUALIFY_INCOMPLETE_EVIDENCE`) — not free-form hidden reasoning and not a
duplicate final answer.

### Behavior activation

| Flag combo | User-visible answer |
|------------|---------------------|
| Reasoning OFF | Exact legacy (speech-acts flag ignored) |
| Reasoning ON + speech acts OFF | Step 044 advisory only |
| Reasoning ON + speech acts ON | Language renders the selected act |

See [LANGUAGE_SPEECH_ACTS.md](LANGUAGE_SPEECH_ACTS.md).

## Flag matrix (coordination)

| Reasoning | EA | Behavior |
|-----------|-----|----------|
| OFF | * | Legacy Rag / Executive |
| ON, EA OFF | — | Passthrough to Rag → RPS.`run` → DFP; sufficiency + speech act |
| ON, EA ON | — | Reasoning coordinates RPS stages; Rag language; sufficiency + speech act |

Speech-act **Language** activation is orthogonal: requires
`REASONING_SPEECH_ACTS_ENABLED` in addition to Reasoning ON.

## Rollback

- Reasoning path: `REASONING_SERVICE_ENABLED=false`
- Speech-act UX only: `REASONING_SPEECH_ACTS_ENABLED=false` (exact Step 044 advisory)

## Related

- [LANGUAGE_SPEECH_ACTS.md](LANGUAGE_SPEECH_ACTS.md)
- [FEATURE_FLAGS.md](FEATURE_FLAGS.md)
- [0.6-step-043-evidence-sufficiency.md](releases/0.6-step-043-evidence-sufficiency.md)
- [0.6-step-044-speech-act.md](releases/0.6-step-044-speech-act.md)
- [0.6-step-045-speech-act-language.md](releases/0.6-step-045-speech-act-language.md)

## Roadmap (Release 0.6)

| Step | Status |
|------|--------|
| **039–042** | Migration seams ✅ |
| **043** | Advisory evidence sufficiency ✅ |
| **044** | Advisory speech-act selection ✅ |
| **045** | Language consumes speech acts ✅ (engineering accepted) |
| **Closure** | Release 0.6 engineering accepted — see [RELEASE-0.6-ACCEPTANCE-REPORT.md](releases/RELEASE-0.6-ACCEPTANCE-REPORT.md) |
| **Next** | RFC-100 Step 047 — memory assist (not started) |

## Roadmap (Release 0.7)

| Step | Status |
|------|--------|
| **046** | Memory region read views (`read_region`) ✅ — internal only, contract hardened; no chat wiring |
| **047** | Reasoning activates memory before Evidence Assembly — **not started** |

### Step 047 caller obligations (MemoryRegionView)

Before interpreting claim support/conflict from Step 046 reads:

1. Check `MemoryClaimView.evidence_loaded` is `true`, or confirm `evidence_not_requested` is **not** in `limitations`.
2. When `evidence_loaded` is `false`, treat `has_support` and `has_conflict` as unknown (`null`).
3. Respect lifecycle validation: do not send `active_only=False` with `include_superseded=False`.
4. Use **deployment corpus isolation** for production: `MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT)` — Reasoning must not resolve source IDs or import `memory_corpus_resolver`.
5. Explicit `source_id` / `source_ids` remain for engineering diagnostics only.
6. Treat exclusion counters as diagnostic only; use `total_matched` and `provenance_summary` for region shape.
7. Check `corpus_scope_configured` and `corpus_limitations` before treating an empty region as “no knowledge.”

See [0.7-step-047-architecture-review.md](releases/0.7-step-047-architecture-review.md).
