# ADR-0002: Tension Taxonomy Ownership

**Status:** Accepted  
**Date:** 2026-07-27  
**Authors:** Engineering (RFC-100 Release 0.5)  
**Supersedes:** —  
**Superseded by:** —  

---

## Context

RFC-100 Steps 034–037 introduced **Tension Surfacing**: conservative detection of
epistemic hypotheses (`support_deficit`, `conflict`), an admin read-only API,
Understanding dashboard panel, and operational gauges.

A Tension is **not** knowledge, belief, or fact — it is an epistemic hypothesis
about a *possible* problem in Epistemic Memory (see [TENSION_SURFACING.md](../TENSION_SURFACING.md)).

Multiple consumers now touch tensions:

- Dashboard Understanding panel (presentation)
- Operational metrics (`kos_*_tensions` gauges)
- Future Maintenance / Investigation / Reasoning (RFC-100 later releases)

Without an ownership rule, those consumers could invent parallel labels,
persist ad-hoc taxonomies, or diverge from detection semantics.

---

## Problem

Who owns the **definition** of tension types, and who may only **consume**
surfaced hypotheses?

---

## Options considered

### Option A — TensionSurfacingService owns taxonomy (chosen)

`TensionSurfacingService` (and its type constants / detection rules) is the
**sole owner** of which tension types exist and how they are detected.

Dashboard, Metrics, Maintenance, and Reasoning are **consumers only**.

- **Pros:** Single source of truth; prevents taxonomy drift; aligns with frozen
  subsystem ownership; new types require deliberate review.
- **Cons:** Consumers must wait for service changes to get new types.

### Option B — Each consumer defines its own labels / types

- **Pros:** Fast UI/metrics experimentation.
- **Cons:** Divergent taxonomies; metrics ≠ API ≠ dashboard; silent cognitive debt.

### Option C — Shared enum in a cross-cutting package, no owning service

- **Pros:** Shared constants.
- **Cons:** Detection rules can still fork; ownership of *meaning* remains unclear.

---

## Decision

**Adopt Option A.**

1. **`TensionSurfacingService` is the sole owner of tension definitions**
   (type codes, detection rules, summaries, count semantics).
2. **New tension types require architectural review** — an ADR when the change
   amends cognitive boundaries or expands the taxonomy beyond the accepted v1
   subset (`support_deficit`, `conflict`).
3. **Dashboard, Metrics, Maintenance, and Reasoning are consumers only** —
   they may display, count, or schedule work from surfaced hypotheses; they must
   not redefine what a tension type means.
4. **No subsystem may independently invent or persist its own tension taxonomy**
   (no parallel enum tables, no UI-only type codes that detection does not emit,
   no maintenance-local taxonomies).

This ADR does **not** change runtime detection, persistence, or Type inventory.

---

## Trade-offs

We accept slower addition of new types in exchange for **taxonomy coherence**
across API, dashboard, metrics, and future maintenance.

---

## Consequences

### Positive

- Clear ownership for Steps 034–037 and later Maintenance/Reasoning work.
- Metrics and UI stay aligned with detection.
- New types are explicit governance events (review / ADR).

### Negative

- Consumer teams cannot ship a new type without the surfacing service.

### Neutral

- Persistence of tensions remains **out of scope** until RFC explicitly requires it;
  when added, storage must still reference the owned taxonomy, not invent one.

---

## Migration impact

- **RFC-100 steps affected:** 034–037 (documents current ownership); 038+ consumers.
- **Feature flags:** None required by this ADR.
- **Rollback:** Documentation only.
- **User-visible changes:** None.
- **Database / storage:** None.

---

## Why other options were rejected

- **Option B** — Creates parallel cognitive vocabularies; violates single-writer /
  ownership discipline for epistemic concepts.
- **Option C** — Constants without an owning detection boundary still allow
  rule forks.

---

## Compliance checklist

- [x] Fits frozen cognitive model (Tension as hypothesis; Epistemic Maintenance
      consumes gaps — does not invent taxonomy elsewhere)
- [x] Subsystem responsibilities clarified — detection owner vs consumers
- [x] No silent technical debt — ownership explicit before Release 0.5 closure
- [x] Release + flag plan identified — docs-only; no flag
- [x] Tests and observability identified — acceptance suite + metrics remain
      consumers of service outputs
