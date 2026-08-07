# Cache operations runbook

Operator guide for retrieval cache, semantic answer cache, and SI LLM cache.

## Layers

| Layer | Storage | Key / match | Cleared by |
|-------|---------|-------------|------------|
| Retrieval | SQLite `retrieval_cache` | Exact key + namespace hash | `invalidate_retrieval_cache` / correctness / TTL |
| Answer | SQLite `answer_cache` + Qdrant `{collection}_answer_cache` | Semantic similarity + version + namespace | `invalidate_answer_cache` / correctness / TTL / stale sweep |
| SI LLM | SQLite `source_intelligence_llm_cache` | `cache_key` PK | TTL cleanup worker (by `cache_key`) |

Correctness events (settings that affect retrieval, knowledge profile, SI
generation) call `CacheInvalidationService.invalidate_for_correctness` — both
retrieval and answer caches.

## Manual clear (Eng Advanced)

- Clear retrieval / answer / all — dashboard Eng → Advanced → Caching
- CLI: `python -m app.scripts.maintenance` cache clear helpers (if present)

## Background cleanup

`CacheCleanupWorker` (interval from config):

1. Expired retrieval rows (batch delete by `id`)
2. Expired answer rows **and** Qdrant points (`AnswerCacheService.purge_expired`)
3. Stale answer namespace / knowledge_version (`purge_stale_namespace`)
4. Expired SI LLM rows by **`cache_key`** (not `id`)

## Memory assist

When Memory evidence assist is effective, **answer cache lookup/store are
skipped** (ADR-0003). Retrieval cache still applies under the assist namespace.

## After deploy notes

- ADR-0004: namespace no longer includes legacy boost fields → expect a one-time
  cold miss wave; cleanup worker removes orphans.
- Split live metrics: `/api/system/performance` exposes `cache_hit_rate`,
  `answer_cache_hit_rate`, `retrieval_cache_hit_rate`.

## Poisoned entries

`CacheInvalidationService.purge_poisoned_entries` removes empty retrieval rows
and fallback answers (maintenance / recovery).

## Feature flags

See `docs/FEATURE_FLAGS.md` — especially `cache_namespace_v2_enabled` (includes
`memory_version` in the namespace).
