# ADR-0004: Exclude legacy boost fields from cache namespace hash

**Status:** Implemented  
**Date:** 2026-08-07  
**Authors:** Engineering  
**Supersedes:** —  
**Superseded by:** —  

---

## Context

`build_retrieval_namespace` hashed ORM boost columns
(`homepage_boost_*`, `title_match_boost`, `heading_match_boost`,
`short_query_lexical_boost`). Those fields were removed from the public Settings
API (Step 052) but still mutated ranking and the namespace via DB defaults /
legacy rows — coupling cache identity to deprecated knobs.

---

## Problem

Should retrieval/answer cache namespaces change when only legacy boost columns
differ?

---

## Options considered

### Option A — Drop boosts from namespace hash (chosen)

Namespace tracks live retrieval/context settings only. Boost column edits no
longer bust cache by themselves.

- **Pros:** Aligns with API removal; stops silent namespace churn from dead knobs;
  one-time mass miss is acceptable.
- **Cons:** If boosts still affect ranking in-process, two rows with different
  boosts can share a cache entry until boosts are fully removed from the
  pipeline.

### Option B — Keep hashing boosts

- **Pros:** Cache keys track ranking deltas.
- **Cons:** Perpetuates deprecated surface; contradicts Step 052 removal.

### Option C — Remove boosts from ranking and namespace together

Ideal end state; larger scope than this hygiene ADR.

---

## Decision

**Option A** now. Ranking cleanup of boosts remains a separate migration item
(roadmap). Correctness events still call `invalidate_for_correctness`.

---

## Trade-offs

Deploy once: existing cache rows with old hashes miss until TTL/sweep. No
operator action required beyond normal cleanup worker.

---

## Consequences

- `test_cache_namespace_still_hashes_orm_boost_fields` inverted
- Operators: one-time cold cache after upgrade is expected

---

## Rollback

Restore the five keys in `cache_namespace_service.retrieval_settings`.

---

## References

- `docs/releases/0.8-step-052-architecture-review.md`
- `backend/app/services/cache_namespace_service.py`
