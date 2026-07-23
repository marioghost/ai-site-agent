# ADR-0001: Shadow observation identity keyed per source (`obs:source:{id}:si`)

**Status:** Accepted  
**Date:** 2026-07-05  
**Authors:** Engineering (RFC-100 Release 0.4)  
**Supersedes:** —  
**Superseded by:** —  

---

## Context

RFC-100 Steps 027–031 introduced Epistemic Memory as a **passive shadow substrate**: schema, read API, SI → claim proposal mapper, flag-gated shadow writes, and bump-on-change for `memory_version`. Epistemic Memory is **not** used for reasoning or retrieval in this phase.

The frozen Cognitive Architecture ([KNOWLEDGE_OS_ARCHITECTURE_v1.md](../KNOWLEDGE_OS_ARCHITECTURE_v1.md) §2.3, §4.2) defines **Observation** as an **immutable observation event** — “we read something informative at time T from source S.” On page re-index, Observation Processing emits a **new** `ObservationAdded`; prior observations are retained.

Shadow implementation (Steps 029–030) assigns observation identity via a stable key:

```
obs:source:{source_id}:si
```

Set in `ClaimExtractionFromSI._evidence_for_source()` and enforced uniquely in `observation_ref.observation_key`. Repeated Source Intelligence runs for the same source **reuse** the existing observation row rather than creating a new one.

This ADR records that decision, its rationale, and the conditions under which it must be revisited. **It does not change implementation, schema, or pipeline.**

---

## Problem

Shadow persistence requires **idempotent** writes: re-running SI over the same source must not duplicate observations, claims, or evidence links. At the same time, the target architecture eventually requires observations to represent **events**, not the latest mutable state of a source.

Which observation identity policy should shadow use, knowing full Memory Integration and a Revision Engine do not exist yet?

---

## Options considered

### Option A — Stable key per source (chosen for shadow)

One `observation_key` per `(source_id, SI pipeline)` — `obs:source:{source_id}:si`.

- **Pros:** Simple idempotency; no duplicate observations on SI re-run; minimal shadow complexity; aligns with “one SI snapshot observation” mental model during collection.
- **Cons:** Re-SI after content change reuses stale `content_hash` / `excerpt`; conflicts with event-sourced observation lifecycle in §4.2; revision/supersession must compensate later.

### Option B — Event key including content hash

e.g. `obs:source:{source_id}:si:{content_hash}`.

- **Pros:** New observation when indexed content changes; closer to immutable-event semantics.
- **Cons:** Breaks idempotency for identical re-runs unless hash stable; more rows during shadow; premature integration semantics before Revision Engine exists.

### Option C — Event key including timestamp / run id

e.g. `obs:source:{source_id}:si:{observed_at}` or batch run UUID.

- **Pros:** True event log; each SI run is distinct.
- **Cons:** No idempotency on retry; shadow tables grow quickly; requires run-id plumbing not present in Step 030.

### Option D — Defer shadow writes until Observation Processing exists

- **Pros:** Architecturally pure.
- **Cons:** Delays RFC-100 shadow collection gate; violates approved Step 030 scope.

---

## Decision

**Adopt Option A for the shadow phase (Steps 029–031, flag `memory_shadow_write_enabled`).**

Observation identity is **one stable key per source** for SI-derived observations. Re-SI updates claims (when proposition/provenance differs) but **does not** create a new observation when the key already exists. Observation rows are treated as **immutable after first insert** (get-or-create, no update path).

This is a **deliberate shadow shortcut**, not the long-term observation lifecycle.

---

## Trade-offs

We accept **semantic staleness** (observation may not reflect latest source content after re-SI) in exchange for **write idempotency** and **minimal shadow surface area** before Memory Integration owns match, merge, supersede, and conflict.

---

## Consequences

### Positive

- Idempotent shadow writes without duplicate observations.
- Stable join point for claims and evidence links during collection.
- Low operational risk while flag defaults OFF.
- Clear, testable contract for Step 032 roundtrip/provenance tests.

### Negative

- Re-SI with changed content leaves **first-seen** `content_hash` and `excerpt` on the observation row.
- New claims from later SI runs may link to a **stale** observation — revision engine must reconcile.
- Diverges from §4.2 “new ObservationAdded on page update” until revisited.

### Neutral

- Schema already supports multiple observations per source (unique key is application-defined, not `source_id` alone).
- Future change is primarily **key policy + integration logic**, not a breaking schema redesign.

---

## Migration impact

- **RFC-100 steps affected:** 029–032 (shadow); future integration steps (0.5+) when revisiting.
- **Feature flags:** `memory_shadow_write_enabled` (default OFF) — unchanged.
- **Rollback:** Disable flag; no schema change required.
- **User-visible changes:** None (shadow only).
- **Database / storage:** No schema change. Revisit may add key variants or new rows; `observation_ref` immutability preserved.

---

## Why other options were rejected

- **Option B** — Premature event semantics; complicates idempotency before integration exists.
- **Option C** — Defeats retry idempotency; volume and run-tracking overhead unjustified for shadow.
- **Option D** — Out of scope for approved Release 0.4 shadow steps.

---

## Revisit triggers

Revisit this ADR (supersede with ADR-0002 or later) when **any** of:

1. **Memory Integration** implements match / merge / supersede / conflict (RFC-100 0.5+).
2. **Revision Engine** must distinguish claim revisions caused by **content change** vs. extractor change.
3. **Observation Processing** becomes a first-class subsystem emitting `ObservationAdded`.
4. Shadow data is used for **memory-assisted evidence** or reasoning (Release 0.7+).
5. Staging metrics show **stale observation rate** (re-SI with changed `content_hash` but unchanged observation row) above agreed threshold.

---

## Possible future direction

After Memory Integration and Revision Engine exist (not before):

1. **Observation Processing** emits a new observation event when `content_hash` (or artifact version) changes.
2. Keys may evolve to e.g. `obs:source:{source_id}:si:{content_hash}` or `obs:source:{source_id}:event:{uuid}` with explicit event metadata.
3. **Memory Integration** links new claims to new observations; matches old claims via revision/supersession; opens conflicts when propositions diverge.
4. Prior shadow rows remain valid historical records; migration is **policy + integration**, not destructive rewrite.

---

## Relationship to Step 032

**This ADR is NOT a blocker for RFC-100 Step 032.**

Step 032 adds claim roundtrip and provenance tests that **encode current shadow behavior**, including stable observation reuse and provenance chain integrity. Tests should reference this ADR where stale-observation semantics are asserted.

---

## Compliance checklist

- [x] Fits frozen cognitive model (documents temporary shadow deviation; target model unchanged)
- [x] Subsystem responsibilities unchanged — decision is identity policy within existing write path
- [x] No silent technical debt — explicit ADR and Step 032 test documentation
- [x] Release + flag plan identified — shadow flag OFF default; revisit at integration cutover
- [x] Tests and observability identified — Step 032 roundtrip/provenance; stale-observation test case
