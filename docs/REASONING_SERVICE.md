# ReasoningService (Release 0.6 — Steps 039–043)

**RFC-100** — stateless reasoning seam, evidence-acquisition coordinator, and
advisory evidence-sufficiency assessment.

## Why it exists

Release 0.6 extracts reasoning ownership from the legacy RAG path. Step 039
created the seam; Step 041 lets Reasoning **order** legacy retrieval adapters
when Evidence Assembly is also enabled; Step 043 adds **source-scoped**
evidence sufficiency as an advisory contract — without changing answers.

## What it owns now

| Owns (contract) | Reality |
|-----------------|---------|
| Chat-turn reasoning entry | ✅ `run` / `answer` / `answer_stream` |
| Typed request/result DTOs | ✅ `ReasoningRequest` / `ReasoningResult` |
| Path diagnostics | ✅ `reasoning_path=reasoning_service` |
| Evidence acquisition order (both flags ON) | ✅ `prepare → assemble → finalize` via RPS adapters |
| Evidence sufficiency (Step 043) | ✅ advisory / shadow-only |
| Speech act / refuse / clarify | **Not yet** — fields remain unset for speech-act control |

## Evidence sufficiency (Step 043)

Sufficiency answers only:

> Does the available **website** evidence appear sufficient to support the
> requested response?

It is **not** confidence in world truth. Completeness for list/enumeration
questions is especially uncertain and surfaces as `completeness_risk=true`
with status `unknown`.

Assessment is:

- computed only when ReasoningService runs (flag ON);
- advisory — **does not** refuse, clarify, or change answer text;
- in-memory from existing `RagResult` fields (sources, `used_context`, intent);
- zero extra retrieval / LLM calls;
- no Epistemic Memory reads.

## What it must not own

- Qdrant / lexical / DFP internals
- ORM models / cache storage
- Prompt construction / LLM / polish / citations
- Epistemic Memory mutation
- HTTP schemas
- Final user-facing language decisions (still Rag)

## Call paths

| Flags | Behavior |
|-------|----------|
| Reasoning ON, EA OFF | Passthrough to Rag → RPS.`run` → DFP → sufficiency assess |
| Reasoning ON, EA ON | Reasoning coordinates RPS stages; Rag language; sufficiency assess |

## Statelessness

Holds only Session/Settings (+ Rag deps). No cross-call caches of answers,
claims, tensions, or pipeline results.

## Related docs

- [EVIDENCE_ASSEMBLY.md](EVIDENCE_ASSEMBLY.md)
- [FEATURE_FLAGS.md](FEATURE_FLAGS.md)
- [MIGRATION_CONFIDENCE_REPORT.md](MIGRATION_CONFIDENCE_REPORT.md)
- [0.6-step-043-evidence-sufficiency.md](releases/0.6-step-043-evidence-sufficiency.md)

## Migration confidence (Step 042)

All **8** flag combinations validated. See [MIGRATION_CONFIDENCE_REPORT.md](MIGRATION_CONFIDENCE_REPORT.md).

## Migration boundaries

| Step | Intent |
|------|--------|
| **042** | Migration Confidence Gate ✅ |
| **043** | Advisory evidence sufficiency ✅ |
| **044** | Streaming fully aligned / speech-act wiring |
| Later | Memory-assisted evidence; act on sufficiency |
