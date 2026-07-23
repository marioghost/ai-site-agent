# Memory version (`memory_version`)

RFC-100 Release 0.3 — epistemic memory revision counter.

## Why it exists

The agent maintains two distinct layers of “what we know”:

1. **Indexed content** — crawled pages/files in Qdrant, used by retrieval.
2. **Epistemic memory** — claims, evidence, and consolidated knowledge (future Knowledge OS modules).

Retrieval caches today key off **`knowledge_version`**, which bumps when indexed content changes. Claim revisions, shadow memory writes, and consolidation can change epistemic state **without** changing the index. Those events need their own revision counter so cache namespace v2 and downstream consumers can invalidate safely.

`memory_version` is that counter: a monotonic integer on the singleton `settings` row, default **1**.

## How it differs from `knowledge_version`

| | `knowledge_version` | `memory_version` |
|---|---------------------|------------------|
| **Tracks** | Index / crawl content changes | Epistemic memory (claims, evidence, consolidation) |
| **Authority** | `KnowledgeVersionService` | `MemoryVersionService` |
| **Bumps today** | Reindex, source delete, SI generation, etc. | Manual admin API (Step 022); **auto on shadow integrate** when flag ON and new rows (Step 031) |
| **Cache impact today** | Yes — `index_version` in cache namespace | Only when `cache_namespace_v2_enabled=true` (Step 023) |
| **Writable via Settings API** | No (read-only on `SettingsRead`) | No (read-only on `SettingsRead`) |

Both are read-only in the dashboard settings API. Only their respective services may write the column.

## Sole authority

**`MemoryVersionService`** (`backend/app/services/memory_version_service.py`) is the only component allowed to read or write `settings.memory_version`.

API:

| Method | Purpose |
|--------|---------|
| `get()` | Current version (minimum 1) |
| `ensure_initialized()` | Set to 1 if missing or &lt; 1; idempotent otherwise |
| `bump(commit=True)` | Increment by exactly 1 and persist. `commit=False` flushes in the caller transaction (shadow integrate) |

Do **not** assign `settings.memory_version` elsewhere. Call the service.

## Auto-bump on shadow claim integrate (Step 031)

**Single automatic path:** `EpistemicMemoryIntegrationService` after successful shadow persist.

```
memory_shadow_write_enabled=true
        ↓
ClaimExtractionFromSI → proposals (non-empty)
        ↓
EpistemicMemoryService.persist_claim_proposals()  (success, any_created)
        ↓
MemoryVersionService.bump(commit=False)   ← only auto caller
        ↓
Caller commits (SI batch / indexing save) or rolls back both epistemic rows and bump
```

### Bumps when

- Flag ON **and** at least one new observation, claim, or evidence link was persisted.

### Does not bump when

- Flag OFF
- Empty proposals
- Idempotent re-run (all rows already exist)
- Persist failure or mid-persist exception
- Caller transaction rolled back

### Why bump-on-change matters

Epistemic state can change **without** reindexing. Before memory-assisted evidence influences retrieval or answers, consumers need a revision signal. `memory_version` provides that signal; when `cache_namespace_v2_enabled=true`, a bump invalidates cached namespaces so stale answers cannot hide behind an unchanged `knowledge_version`.

**Epistemic Memory is still not used for reasoning or retrieval in Step 031** — bumps prepare cache and downstream modules for future cutover.

## Future milestones that will bump `memory_version`

| Step / milestone | Owner of bump |
|------------------|---------------|
| **022** | Manual admin API — `POST /api/settings/memory-version/bump` |
| **023** | Cache namespace v2 — `cache_namespace_v2_enabled` includes version in hash | Flag OFF by default |
| **031** | Auto-bump on shadow claim integrate | `EpistemicMemoryIntegrationService` only |
| Consolidation jobs | TBD — via `MemoryVersionService.bump()` |
| Memory schema migrations | TBD — bump after migration apply |

`knowledge_version` bumps remain owned by indexing, reprocess, source delete, and source intelligence flows via `KnowledgeVersionService`.

## Manual bump (Step 022 — operational stub)

Release 0.3 provides an **admin-only** API for operators to bump `memory_version` before automatic claim/memory integration exists.

```http
POST /api/settings/memory-version/bump
Authorization: Bearer <admin token>
Content-Type: application/json

{"reason": "optional operator note"}
```

Response:

```json
{
  "previous_memory_version": 1,
  "new_memory_version": 2,
  "reason": "manual_admin_stub"
}
```

- Uses **`MemoryVersionService` only** — no direct column writes.
- Does **not** invalidate caches unless `cache_namespace_v2_enabled=true` (Step 023).
- **`reason`** is echoed in the response only; it is not persisted.
- **Step 031+** auto-bumps on shadow claim integrate when new rows are created; this endpoint remains for manual ops.

## Cache namespace v2 (Step 023)

When **`cache_namespace_v2_enabled=true`** in Settings:

- `build_retrieval_namespace(settings, db=session)` adds `memory_version` to the namespace dict.
- Version is read via **`MemoryVersionService.get()`** only — not from direct settings access in namespace code.
- Retrieval and answer caches incorporate the namespace hash; a memory bump causes a miss on the next lookup.
- **Default OFF:** production cache keys and behavior are unchanged.

See [FEATURE_FLAGS.md](FEATURE_FLAGS.md#cache_namespace_v2_enabled).

## Cache Namespace Invariants (Step 024)

These invariants define how epistemic memory revision reaches caches **without** making cache code memory-aware.

### Principle

Caches are **version-aware** (they hash and compare namespace fingerprints and `knowledge_version` columns) but **not memory-aware** (they never read claims, call `MemoryVersionService.bump()`, or interpret epistemic state). Invalidation is entirely a consequence of **namespace evolution** when the flag is on.

```
memory_version bump (MemoryVersionService)
        ↓
cache_namespace_v2_enabled = true ?
        ↓ yes
build_retrieval_namespace(..., db)  →  MemoryVersionService.get()
        ↓
namespace dict gains memory_version key
        ↓
namespace_hash(namespace) changes
        ↓
retrieval/answer cache lookup miss (hash mismatch)
```

When the flag is **off**, the middle branch is skipped: memory bumps do not alter the namespace, and existing cache entries remain valid.

### Verified invariants

| # | Invariant |
|---|-----------|
| 1 | `cache_namespace_v2_enabled=false` → changing `memory_version` on the settings row does **not** change the namespace |
| 2 | `cache_namespace_v2_enabled=true` → changing memory version (via service) **does** change the namespace hash |
| 3 | Changing `knowledge_version` still updates `index_version` only (legacy behavior preserved) |
| 4 | `MemoryVersionService.bump()` never mutates `knowledge_version` |
| 5 | `KnowledgeVersionService.bump()` never mutates `memory_version` |
| 6 | Identical namespace inputs → identical retrieval cache keys |
| 7 | Namespace generation and `namespace_hash()` are deterministic |

### What cache code must not do

- Read `settings.memory_version` directly (only `MemoryVersionService.get()` in `cache_namespace_service.py`)
- Call `bump()` on either version service
- Perform version arithmetic (`knowledge_version + 1`, etc.)
- Know about claims, evidence, or Epistemic Memory modules

### Test suite

```bash
cd backend
.venv/bin/pytest tests/test_cache_namespace_v2_invariants.py tests/test_cache_namespace_v2.py -m unit -v
```

## Operational metrics (Step 025)

Operators can observe current revision counters without changing runtime behavior.

| Endpoint | Format | Auth |
|----------|--------|------|
| `GET /api/metrics` | Prometheus text (`kos_memory_version`, `kos_knowledge_version` gauges) | None (same as `/api/health`) |
| `GET /api/metrics/operational` | JSON `{ "memory_version", "knowledge_version" }` | None |

Both endpoints are **read-only**. Values come from **`MemoryVersionService.get()`** and **`KnowledgeVersionService.get()`** — not direct `settings.memory_version` reads in metrics code.

Example Prometheus scrape:

```text
# HELP kos_memory_version Epistemic memory revision counter (MemoryVersionService).
# TYPE kos_memory_version gauge
kos_memory_version 1
# HELP kos_knowledge_version Indexed knowledge revision counter (KnowledgeVersionService).
# TYPE kos_knowledge_version gauge
kos_knowledge_version 42
```

Bumping via `POST /api/settings/memory-version/bump` updates `kos_memory_version` on the next scrape. No cache, chat, or auto-bump side effects.

## Deploy

Requires migrations `0012_memory_version` and `0013_cache_namespace_v2_enabled` (Step 020–023):

```bash
cd backend
.venv/bin/alembic upgrade head
```

See [0.3-step-020-deploy.md](releases/0.3-step-020-deploy.md).

## Concurrency

Bumps use read-modify-write on the singleton settings row, matching `KnowledgeVersionService`. Row-level locking is not implemented yet; concurrent bumps follow the same semantics as `knowledge_version` today.
