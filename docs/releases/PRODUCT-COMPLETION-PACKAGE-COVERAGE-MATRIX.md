# RFC-101 Product Completion — Package Coverage Matrix

```
Program: docs/releases/1.0-rfc-101-master-program.md
Package IDs: all (Appendix A) — see table below
Inventory findings: all (Master Inventory Part A/C)
Execution Strategy: docs/releases/1.0-rfc-101-execution-strategy.md
```

**Document type:** Coverage tracking (not a roadmap, not a re-decision of ownership)
**Date:** 2026-08-05
**Authority:** `docs/releases/1.0-rfc-101-master-program.md` Appendix A (package index) and §8 (progress tracking model)
**Produced by:** S008 (`G9-P1` template, `G9-P2`/`G9-P3` process — see `docs/releases/S008-implementation-package.md`)

This matrix maps **every** package ID in the Master Program's Appendix A to the Step that closed it and its current status, per the status enums defined in Master Program §8.1 (`Not started` · `In progress` · `Blocked` · `In review` · `Accepted` · `Rejected` · `Reopened` · `Completed`).

**Scope note:** "Completed" below means **implementation-complete with local verification** (`npm test`/`npx tsc --noEmit` passing) for the owning Step. **S001** and **S002** are already committed, pushed, deployed, and **ACCEPTED · CLOSED** on tip `9a7134c`. For the remaining **S003–S008** wave, commit/push/deploy/runtime-validation/Final-Acceptance remain `pending` per each Step's own `*-acceptance-evidence.md`. See `docs/releases/1.0-rfc-101-program-status.md` for the overall program-level rollup and outstanding review chain.

---

## G1 — Information Architecture & routing

| Package | Status | Closed by | Notes |
|---------|--------|-----------|-------|
| G1-P1 | Completed | S001 | Canonical route substrate for Home/Knowledge/Ask/Insights/Settings/Engineering |
| G1-P2 | Completed | S002 (Knowledge slice), S003 (Insights slice), S004 (`/users` slice), S005 (`/chat` slice), S007 (`/`/`/overview` slice) | Redirect map fully closed — every legacy path in the Master Inventory's redirect scope now redirects to its canonical owner |
| G1-P3 | Completed | S001 (baseline), S007 (finalize/verify) | `PRODUCT_NAV`/`ENGINEERING_NAV` single source; no dual labels |
| G1-P4 | Completed | S001 (initial), S007 (finalize/verify) | Glossary applied to all claimed nav/chrome labels (en/uk) |

## G2 — Engineering Mode shell

| Package | Status | Closed by | Notes |
|---------|--------|-----------|-------|
| G2-P1 | Completed | S001 | `/settings/general` Mode toggle host |
| G2-P2 | Completed | S001 | `EngineeringMode` context + `RequireEngineeringMode` guard, default off |
| G2-P3 | Completed | S001 (scaffolds), S006 (real content) | Six Eng destinations exist and are populated |

## G3 — Ask productization

| Package | Status | Closed by | Notes |
|---------|--------|-----------|-------|
| G3-P1 | Completed | S005 | `/ask` product chrome; `/chat` compatibility redirect |
| G3-P2 | Completed | S006 | Diagnostics moved to `/engineering/ask-details` |
| G3-P3 | Completed | S006 | History handoff to `/insights/activity`; `ChatHistoryModal` retired from Ask |
| G3-P4 | Completed | S006 | Ask reduced to single-column product-only chat console |

## G4 — Knowledge productization

| Package | Status | Closed by | Notes |
|---------|--------|-----------|-------|
| G4-P1 | Completed | S002 | Library owns browse/coverage |
| G4-P2 | Completed | S002 | Update owns refresh/indexing |
| G4-P3 | Completed | S002 | Site owns site identity (Knowledge Profile) |
| G4-P4 | Completed | S006 | Source Intelligence moved to `/engineering/knowledge` |

## G5 — Insights productization

| Package | Status | Closed by | Notes |
|---------|--------|-----------|-------|
| G5-P1 | Completed | S003 | Performance owns full analytics |
| G5-P2 | Completed | S003 | Activity owns past questions/requests |
| G5-P3 | Completed | S003 | Insights section layout (Performance/Activity sub-nav) |

## G6 — Home readiness

| Package | Status | Closed by | Notes |
|---------|--------|-----------|-------|
| G6-P1 | Completed | S005 | `/home` readiness model + checklist + CTA |
| G6-P2 | Completed | S006 (partial: SI/diagnostics receivers), S007 (final: LLM runtime + release/version tags to `EngStatusScreen`) | Every Overview capability redistributed; ledger in `S007-implementation-package.md` §6 |
| G6-P3 | Completed | S007 | `/` and `*` default to `/home`; `OverviewPage` is a redirect-only shim |

## G7 — Settings split

| Package | Status | Closed by | Notes |
|---------|--------|-----------|-------|
| G7-P1 | Completed | S004 | General complete (language + Mode toggle) |
| G7-P2 | Completed | S004 | Models owns model selection |
| G7-P3 | Completed | S004 | Answers owns four modes only |
| G7-P4 | Completed | S004 | Access owns user management; `/users` redirects |
| G7-P5 | Completed | S006 | Advanced knobs/prompt → `/engineering/advanced`; flag catalog → `/engineering/build` |

## G8 — Frontend architecture (RFC-102)

| Package | Status | Closed by | Notes |
|---------|--------|-----------|-------|
| G8-P1 | Completed | S001 | `features/*`/layouts/shared skeleton created |
| G8-P2 | Completed | S002, S003, S004, S005 (each explicitly claims a "slice"); S006/S007 continue the same pattern for Engineering/Home without a separate explicit label | Every migrated owner lives under RFC-102 feature-module structure; no new permanent logic added to legacy monoliths |
| G8-P3 | Completed | S008 | Verified zero `MigrationPlaceholder` importers among canonical owners; no gap found, no code change required |
| G8-P4 | Completed | S008 | Three stranded trees identified and documented as accepted debt (frozen-test protected, not deleted) — see `S008-implementation-package.md` §6 |

## G9 — Product Readiness process

| Package | Status | Closed by | Notes |
|---------|--------|-----------|-------|
| G9-P1 | Completed | S001 | Gate record template + debt register seeded |
| G9-P2 | Completed (protocol) / Execution **open** | S008 | `docs/releases/S008-cold-demo-protocol.md` authored; running the checklist against a live instance is a separate, later task |
| G9-P3 | Completed (protocol) / Execution **open** | S008 | `docs/releases/S008-accessibility-protocol.md` authored; running the checklist is a separate, later task |

## G10 — Release tooling hygiene (optional, independent)

| Package | Status | Closed by | Notes |
|---------|--------|-----------|-------|
| G10-P1 | **Not started — optional, deferred** | — | `deploy/lib/verify_release.sh` `/tmp` ownership fix not implemented; explicitly out of every Dashboard Step's scope including S008 per task instruction; deploy-time verify (`sudo` context) remains authoritative and unaffected |
| G10-P2 | **Not started — optional, deferred** | — | Operator messaging clarity depends on G10-P1; same deferral rationale |

G10 is independent of, and never blocks, Dashboard Product Completion per Master Program §4.3 ("G10 ∥ G12 ∥ G9-P1 ∥ G8-P1 ∥ G11-P0"). Program Completion (§12) does not require G10 to be resolved for the Dashboard program itself, though the Master Program does list G10 among the twelve clusters for full closure bookkeeping — this matrix records it as the one cluster intentionally left open by explicit operator instruction across S001–S008.

## G11 — Backend deferred non-product (excluded, tracked)

| Package | Status | Closed by | Notes |
|---------|--------|-----------|-------|
| G11-P0 | Completed (boundary record only) | S001 | Dual-read cache fallback, `kos_tension_resolved_total`, pipeline deferred adapters explicitly excluded from every Dashboard package S001–S008; no Dashboard package implements G11 work |

## G12 — Lifecycle/docs clarity

| Package | Status | Closed by | Notes |
|---------|--------|-----------|-------|
| G12-P1 | Completed | S001 | Engineering-closure vs Product-Accepted-Product clarification published |
| G12-P2 | Completed | S001 | Program SoT pointer published |

---

## Rollup

| Cluster | Package count (excl. G11 per Program §8.1) | Completed | Open / deferred |
|---------|----------------------------------------------|-----------|------------------|
| G1 | 4 | 4 | 0 |
| G2 | 3 | 3 | 0 |
| G3 | 4 | 4 | 0 |
| G4 | 4 | 4 | 0 |
| G5 | 3 | 3 | 0 |
| G6 | 3 | 3 | 0 |
| G7 | 5 | 5 | 0 |
| G8 | 4 | 4 | 0 |
| G9 | 3 | 3 (2 protocol-only; execution open) | 0 packages, 2 execution items open |
| G10 | 2 | 0 | 2 (optional, deferred by explicit instruction) |
| G12 | 2 | 2 | 0 |
| **Total (excl. G11)** | **37** | **35** | **2 (G10, optional)** |
| G11 (excluded cluster) | 1 | 1 (boundary record) | — |

**Implementation-complete:** 35/37 in-scope packages (all except the two optional/deferred G10 packages). Two additional items (`G9-P2`/`G9-P3` **execution**, as distinct from the protocol packages themselves) remain explicitly open per Master Program §4.2's own dependency notation ("Surfaces claiming complete" as the hard dependency for execution).

**Not yet closed for S003–S008:** commit, push, deploy, runtime validation, and Final Acceptance for the remaining Product Completion wave (S001/S002 already accepted on tip `9a7134c`). Cold-demo and accessibility **execution** remain open — see `docs/releases/1.0-rfc-101-program-status.md`.
