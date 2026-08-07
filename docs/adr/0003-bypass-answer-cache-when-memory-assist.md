# ADR-0003: Bypass answer cache when Memory evidence assist is effective

**Status:** Implemented  
**Date:** 2026-08-07  
**Authors:** Engineering  
**Supersedes:** —  
**Superseded by:** —  

---

## Context

Semantic answer cache short-circuits the chat turn before retrieval and before
advisory Memory evidence assist (RFC-100 Step 047). When assist is effective
(`reasoning` + `memory_evidence_assist` + `cache_namespace_v2`), a cached answer
would skip the assist path even though the namespace isolates assist vs
non-assist entries.

---

## Problem

Should answer cache lookup/store run on turns where Memory assist is effective?

---

## Options considered

### Option A — Bypass answer cache when assist is effective (chosen)

`answer_cache_policy.answer_cache_permitted` returns false when
`apply_memory_assist and memory_assist_effective(settings)`.

- **Pros:** Assist always runs; no stale short-circuit; one policy module for
  RagService + streaming.
- **Cons:** Lower answer-cache hit rate while assist is on.

### Option B — Rely on namespace isolation only

Keep lookup/store; hash includes `memory_evidence_assist` + corpus fingerprint.

- **Pros:** Higher hit rate within assist mode.
- **Cons:** Easy to regress (early return before assist); harder to reason about.

### Option C — Do nothing

- Unacceptable once assist is production-path.

---

## Decision

**Option A.** Answer cache is an optimization for non-assist turns. Retrieval
cache remains namespaced (including assist flags) and continues to run.

---

## Trade-offs

Fewer answer hits while assist is enabled; correctness of Memory assist wins.

---

## Consequences

- Trace skip reason: `memory_assist_active`
- Eng / operators: expect lower answer-cache hit rate with assist ON
- Invalidation and namespace rules unchanged

---

## Rollback

Revert `answer_cache_policy` gating in RagService / RagStreamingService.

---

## References

- `docs/MEMORY_VERSION.md`
- `backend/app/services/answer_cache_policy.py`
- `backend/app/services/reasoning/memory_assist_policy.py`
