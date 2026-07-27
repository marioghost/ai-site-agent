# Tension surfacing (Release 0.5)

**RFC-100 Steps 034–037** — conservative detection from Epistemic Memory, admin
read-only API + Understanding panel, and operational metrics. No persistence,
no maintenance execution.

## Semantic rule (critical)

A **Tension** is:

- **NOT** knowledge
- **NOT** a belief
- **NOT** a fact

A Tension is an **epistemic hypothesis**: a read-only signal that a *possible*
problem may exist inside Epistemic Memory (for example possible support deficit,
conflict, incompleteness, or authority gap).

Surfacing a tension never asserts that the problem is confirmed, never updates
claims, and must not be treated as retrieved knowledge for chat or reasoning.

**Metrics** count the same hypotheses — possible issues, not confirmed knowledge
errors. Non-zero gauges do **not** mean active maintenance is running.

## Purpose

`TensionSurfacingService` scans active claims via `EpistemicMemoryService` and
returns in-memory `TensionView` DTOs. The admin API maps those views to
`TensionRead` responses with enough provenance (`claim_ids`,
`observation_ref_ids`, `evidence_link_ids`, `summary`) to explain *why* each
hypothesis was surfaced — without exposing ORM models.

## Tension types (v1)

| Type | Code | Detection rule (conservative) |
|------|------|--------------------------------|
| Support deficit | `support_deficit` | Active claim with **no** evidence link `role=support` |
| Conflict | `conflict` | Explicit `role=conflict` evidence on a claim, **or** same observation has `support` for claim A and `conflict` for claim B (A ≠ B) |

Only these two types are detected and measured today.

## What is NOT detected (limitations)

- Semantic / NLP contradiction between propositions
- Conflicts inferred from confidence scores alone
- Superseded or inactive claims (`superseded_by_id` set)
- Gaps, ignorance records, belief-state tensions
- Cross-source conflict without explicit conflict evidence role
- Persisted tension store (no DB writes)

Prefer **false negatives over false positives**.

## Service API

```python
from app.services.epistemic_memory import EpistemicMemoryService
from app.services.tension_surfacing import TensionSurfacingService

memory = EpistemicMemoryService(db)
tensions = TensionSurfacingService(memory).surface_tensions()
counts = TensionSurfacingService(memory).summarize_counts()
```

`surface_tensions()` returns a deterministically ordered `list[TensionView]`.  
`summarize_counts()` returns bounded hypothesis counts for operators/metrics
(same detection path; default scan ≤ `METRICS_CLAIM_SCAN_LIMIT` active claims).

### Why `METRICS_CLAIM_SCAN_LIMIT` defaults to 500

The limit is an **engineering safety bound for metrics collection**, not a
cognitive limitation on Epistemic Memory or on how many hypotheses can exist.

- Operator scrapes (`GET /api/metrics`, `/api/metrics/operational`) must not
  walk an unbounded claim corpus on every Prometheus poll.
- `500` matches `DEFAULT_CLAIM_LIMIT` used by detection so metrics and
  surfacing share one ceiling and one cost model.
- Raising the limit increases per-scrape DB work (one evidence-link list per
  active claim in the scan window). Lowering it under-reports on large memories.
- It does **not** mean “only 500 tensions can exist” cognitively — only that
  **this scrape** counts hypotheses from at most 500 active claims.

### Cost / scalability

| Path | Bound | Expected cost |
|------|-------|----------------|
| Detection / metrics | ≤ `METRICS_CLAIM_SCAN_LIMIT` (500) active claims | One `list_claims` + one evidence-link list per claim |
| Unbounded full-corpus scan | **Not supported** | Avoided by design |

Claims beyond the scan limit are not counted until later pagination/aggregation work.

## Current maturity

| Capability | Status in Release 0.5 |
|------------|----------------------|
| **Observation** | Present as Epistemic Memory substrate (shadow identity per [ADR-0001](adr/0001-shadow-observation-key-per-source.md)); not a full event-sourced Observation Processing subsystem |
| **Claim** | Present — schema, read API, SI → proposals, flag-gated shadow writes |
| **Evidence** | Present — `evidence_link` roles including `support` / `conflict` |
| **Tension** | Present — read-only detection (`support_deficit`, `conflict`), admin API, dashboard, metrics; **not** persisted |
| **Maintenance** | **Not implemented** — no agenda, no budgeted repair execution |
| **Investigation** | **Not implemented** — no investigation planning from tensions |
| **Reasoning usage** | **Not implemented** — chat / retrieval / Executive do not consume tensions or Epistemic Memory |
| **Belief revision** | **Not implemented** — no merge / supersede / belief-update engine |

Taxonomy ownership: [ADR-0002](adr/0002-tension-taxonomy-ownership.md) —
`TensionSurfacingService` owns definitions; dashboard/metrics/maintenance/reasoning are consumers only.

## HTTP API (Step 035) + Dashboard (Step 036)

```
GET /api/understanding/tensions?page=1&page_size=50
Authorization: Bearer <admin JWT>
```

Admin UI: `/understanding` — read-only Epistemic Health panel (hypothesis wording only).

## Operational metrics (Step 037)

| Gauge | Meaning |
|-------|---------|
| `kos_open_tensions` | Total surfaced hypotheses (bounded scan) |
| `kos_support_deficit_tensions` | Possible support-deficit count |
| `kos_conflict_tensions` | Possible conflict count |

Endpoints (unchanged auth model — same as health):

- `GET /api/metrics` — Prometheus text (version gauges + tension gauges)
- `GET /api/metrics/operational` — JSON including version + tension fields

Metrics layer calls `TensionSurfacingService.summarize_counts()` only — **no direct
epistemic ORM access**. Read-only; no persistence; no maintenance.

## Ownership

| Concern | Owner |
|---------|--------|
| Epistemic reads | `EpistemicMemoryService` |
| Tension taxonomy + detection / counts | `TensionSurfacingService` ([ADR-0002](adr/0002-tension-taxonomy-ownership.md)) |
| HTTP exposure | `app.api.understanding` (consumer) |
| Dashboard | Understanding panel (consumer) |
| Operational gauges | `OperationalMetricsService` (consumer) |
| Persistence | **Not implemented** |

## Explicit non-goals

- No chat / retrieval / Executive / cache / reasoning changes
- No maintenance execution or investigation planning
- No tension table / ORM writes
- No new tension types without architectural review (ADR when appropriate)

## Tests

```bash
cd backend && .venv/bin/pytest \
  tests/test_tension_surfacing_service.py \
  tests/test_tension_acceptance.py \
  tests/test_understanding_tensions_api.py \
  tests/test_operational_metrics.py \
  -m unit -v
```

## Next steps (RFC-100)

Release 0.5 closed — see [RELEASE-0.5-ACCEPTANCE-REPORT.md](releases/RELEASE-0.5-ACCEPTANCE-REPORT.md).

- **039+** — ReasoningService extraction (Release 0.6)
- Later — Maintenance / Investigation as **consumers** of the owned taxonomy ([ADR-0002](adr/0002-tension-taxonomy-ownership.md))
