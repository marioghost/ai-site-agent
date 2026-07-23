# Epistemic Memory schema (Release 0.4 — engineering complete)

**RFC-100 Steps 027–033** — persistent tables, read service, proposal mapper, **passive shadow writes** (flag-gated), bump-on-change, roundtrip tests, **Release 0.4 accepted**.

**Epistemic Memory is NOT used for reasoning or retrieval.** Shadow persistence collects data for future steps only.

## Purpose

Provide the database foundation for [Epistemic Memory](../KNOWLEDGE_OS_ARCHITECTURE_v1.md) (Part 6):

| Table | Cognitive role |
|-------|----------------|
| `observation_ref` | Immutable reference to an informative observation event |
| `claim` | Attributed proposition (revisable via supersession chain) |
| `evidence_link` | Connects a claim to an observation with provenance role |

## Ownership

| Concern | Owner (RFC-100) | Step | Status |
|---------|-----------------|------|--------|
| Schema | Alembic `0014` | **027** | Done |
| Read API | `EpistemicMemoryService` | **028** | Done |
| SI → claim proposals | `ClaimExtractionFromSI` | **029** | Done (in-memory) |
| Shadow writes | `EpistemicMemoryIntegrationService` | **030** | Done (flag OFF default) |
| Auto `memory_version` bump on integrate | Memory Integration | **031** | Done (deferred commit, bump-on-change) |
| Roundtrip / provenance tests | Integration tests | **032** | Done |
| Release 0.4 acceptance | Acceptance report + rollback | **033** | Done |

**Write path (Step 030):** only `EpistemicMemoryService.persist_claim_proposals()` may insert epistemic rows. `EpistemicMemoryIntegrationService` is the sole orchestrator (SI hook → mapper → write → optional bump). `ClaimExtractionFromSI` never touches the database.

## Shadow writes (Step 030)

| Setting | Default | When ON |
|---------|---------|---------|
| `memory_shadow_write_enabled` | **false** | After SI generation, persist proposals idempotently |

**When OFF:** zero epistemic writes, zero `memory_version` bumps from this path.

**When ON:**

1. Post-SI hook in `SourceIntelligenceGenerationService` and inline indexing
2. `ClaimExtractionFromSI` → proposals
3. `EpistemicMemoryIntegrationService.shadow_write_after_si()`
4. `EpistemicMemoryService.persist_claim_proposals()` — idempotent observation / claim / evidence rows
5. `MemoryVersionService.bump(commit=False)` only if at least one **new** row was created — commits with caller transaction (Step 031)

Observation key stable per source: `obs:source:{source_id}:si`. Re-running SI does not duplicate rows. See [ADR-0001](adr/0001-shadow-observation-key-per-source.md) for shadow identity semantics and revisit triggers.

**Not implemented:** merge, supersession, conflict resolution, belief revision, retrieval/chat consumption.

## EpistemicMemoryService

Read methods (Step 028) + `persist_claim_proposals()` write API (Step 030, integration-only).

## ClaimExtractionFromSI (Step 029)

In-memory mapper only — see [0.4-step-029](releases/0.4-step-029-claim-extraction-from-si.md).

## Migration

```bash
cd backend && .venv/bin/alembic upgrade head
# head: 0015_memory_shadow_write_enabled
```

## Tests

```bash
cd backend && .venv/bin/pytest tests/test_epistemic_memory_*.py tests/test_claim_extraction_from_si.py -m unit -q
```

ADR: [0001-shadow-observation-key-per-source](adr/0001-shadow-observation-key-per-source.md)

## Cross-references

- [0.4-step-027](releases/0.4-step-027-epistemic-memory-schema.md)
- [0.4-step-028](releases/0.4-step-028-epistemic-memory-service.md)
- [0.4-step-029](releases/0.4-step-029-claim-extraction-from-si.md)
- [0.4-step-030](releases/0.4-step-030-epistemic-shadow-write.md)
- [0.4-step-031](releases/0.4-step-031-shadow-memory-version-bump.md)
- [0.4-step-032](releases/0.4-step-032-claim-roundtrip-provenance.md)
- [RELEASE-0.4-ACCEPTANCE-REPORT](releases/RELEASE-0.4-ACCEPTANCE-REPORT.md)
- [0.4-rollback](releases/0.4-rollback.md)
- [ADR-0001](adr/0001-shadow-observation-key-per-source.md)
- [FEATURE_FLAGS.md](FEATURE_FLAGS.md) — `memory_shadow_write_enabled`
- [MEMORY_VERSION.md](MEMORY_VERSION.md)
