# S008 — Implementation Package

```
Program: docs/releases/1.0-rfc-101-master-program.md
Package IDs: G8-P3, G8-P4, G9-P2, G9-P3
Inventory findings: A1.2, A17.2, A9.2, A15.1, A20.1
Execution Strategy: docs/releases/1.0-rfc-101-execution-strategy.md
```

**Step:** S008 — Structure polish, cleanup, validation, Product Readiness evidence
**Program:** `docs/releases/1.0-rfc-101-master-program.md`
**Roadmap:** `docs/releases/1.0-rfc-101-execution-roadmap.md`
**Execution Strategy:** `docs/releases/1.0-rfc-101-execution-strategy.md`
**Implementation HOW:** `docs/RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md`
**Baseline:** S007 accepted state (`docs/releases/S007-*`)

**Status:** **FROZEN for implementation** — authorized, scoped, and ready for Step S008 coding
**Duration band (roadmap):** S
**Prerequisites:** S001–S007 (full RFC-101 IA cutover: Home default, Knowledge/Ask/Insights/Settings ownership, Engineering Mode isolation)

---

## 1. Goal

S008 is the closing structural-hygiene and evidence step of the RFC-101 Product Completion frontend cutover (S001–S007). It does **not** move any more product ownership. It:

1. Verifies (and, only if a gap is found, lightly fixes) that `MigrationPlaceholder` is unused by every canonical product/engineering owner screen (`G8-P3`).
2. Greps for and documents dead/stranded component trees left behind by S002–S007 "migrate on touch" copies, without deleting anything still protected by a frozen prior-step test (`G8-P4`).
3. Writes the Product Readiness cold-demo protocol (`G9-P2`) and accessibility-pass protocol (`G9-P3`) — **protocol documents only**, no runtime execution claim.
4. Publishes the Product Completion Program status rollup, package coverage matrix, and program-level debt register update so S001–S008 have one coherent evidence trail.
5. Adds one final regression-lock test (`s008ProductCompletionFinal.test.ts`) snapshotting the accepted end-state route/nav/ownership contracts across all prior steps.

S008 is a **hygiene + evidence Step**. It is not a new product surface, not a backend Step, and does not reopen S001–S007 product ownership.

---

## 2. Frozen scope

### In scope

- Grep-verify `MigrationPlaceholder` has zero importers among canonical product/engineering screens (Home, Knowledge×3, Ask, Insights×2, Settings×4, Engineering×6); fix only if a regression is found (none was, per §6 evidence)
- Grep-verify no remaining `ChatHistoryModal` **import usages** outside its own definition file (file itself may stay; S006 already retired the only import)
- Document (not delete) the three stranded/dead component trees left over from S003/S004/S006/S007 migrate-on-touch copies, each of which is protected from deletion by at least one frozen prior-step `?raw`-source test
- `docs/releases/S008-cold-demo-protocol.md` (protocol only)
- `docs/releases/S008-accessibility-protocol.md` (protocol only)
- `docs/releases/S008-implementation-package.md` / `-implementation-evidence.md` / `-product-readiness-gate.md` / `-acceptance-evidence.md`
- `docs/releases/1.0-rfc-101-program-status.md` — update to reflect S002–S008 package rollup (was last updated at S001)
- `docs/releases/PRODUCT-COMPLETION-PACKAGE-COVERAGE-MATRIX.md` — new, full Appendix A package-ID coverage table for S001–S008 + G10 (optional, deferred)
- `docs/releases/1.0-rfc-101-product-debt-register.md` — append S003–S008 accepted-debt rows
- `dashboard/src/s008ProductCompletionFinal.test.ts` — new regression-lock test
- Full regression: `cd dashboard && npm test && npx tsc --noEmit`

### Out of scope (forbidden in this package)

| Area | Reason / Owner |
|------|----------------|
| `backend/**`, `alembic/**` | Forbidden — no backend Step |
| `deploy/**`, `scripts/release/**` | Forbidden — release engineering owns this, frozen by accepted remediation |
| `verify-release`, `smoke`, any provenance/identity tooling | Forbidden — `G10` (release tooling hygiene) is explicitly **optional** and left untouched this task; documented as optional/deferred, not implemented |
| Deleting `pages/SettingsPage.tsx`, `components/analytics/*`, `components/overview/*` (any file) | Still read by frozen tests (`s001EngineeringMode.test.ts`, `step065Ownership.test.ts`, `s004SettingsCutover.test.ts`, `s005HomeAskCutover.test.ts`, `s006EngineeringIsolation.test.ts`) — deleting would break accepted prior-step evidence; documented as accepted debt instead (§6) |
| Any further G1–G7 ownership move | Completed S001–S007; frozen |
| `G9-P2`/`G9-P3` **execution** (actually running a cold-demo trial or automated a11y scan) | Only the **protocol** is authored here; execution requires a separate, later authorized task per the Program's own dependency note ("execution evidence only when surfaces claim complete") |
| Commit / push / deploy | Explicitly forbidden for this task — implementation only |

### Explicitly deferred (not implemented, documented as optional)

- `G10-P1` — verify-release `/tmp` temp-file isolation fix
- `G10-P2` — operator messaging clarity for verify-release

Per the Master Program, G10 is independent of all Dashboard UI packages and was already functionally addressed at the deploy layer during the Phase 2 remediation referenced in `docs/releases/S001-frontend-deployment-remediation-phase-2-implementation-package.md` (temp-path isolation for that remediation's own deploy verification, not a rewrite of `deploy/lib/verify_release.sh` itself). G10-P1/P2 remain **optional deferred** — no `deploy/**` file is touched by S008.

---

## 3. Package IDs

| Identifier | Purpose | User-visible result | Dependencies | Completion criteria |
|------------|---------|---------------------|--------------|---------------------|
| `G8-P3` | Shared UI + data-hooks standardization verification | No behavior change; confirms migrated screens hold to their existing shared-hook patterns and that `MigrationPlaceholder` is fully retired from canonical owners | Soft: G8-P2 (already complete S002–S007) | Grep shows zero `MigrationPlaceholder` imports on any canonical product/eng screen; test asserts it |
| `G8-P4` | Dead-code / stranded component documentation | No behavior change; three stranded trees identified, ownership-decision recorded (leave in place, frozen-test-protected) rather than silently forgotten | Soft: related migration packages (G4, G5, G6, G7) — all complete | Every stranded tree has a named accepted-debt entry with rationale; no accidental deletion of anything a frozen test still reads |
| `G9-P2` | Cold-demo / visual / browser evidence protocol (protocol half) | Operators have a written, repeatable Mode-off cold-demo checklist ready to execute later | None for protocol authoring | `docs/releases/S008-cold-demo-protocol.md` exists, covers Home default / no Overview home / Insights / Settings / Knowledge / Ask / Eng Mode behavior, and makes no runtime-executed claim |
| `G9-P3` | Accessibility pass protocol | Operators have a written a11y checklist (keyboard, labels, contrast) for final screens ready to execute later | None for protocol authoring | `docs/releases/S008-accessibility-protocol.md` exists, covers keyboard/labels/contrast for all final screens, makes no runtime-executed claim |

---

## 4. Architecture impact

### Allowed layers to change

| Layer / concern | Allowed S008 impact |
|-----------------|---------------------|
| Tests | New `dashboard/src/s008ProductCompletionFinal.test.ts` only — no existing test file assertions changed |
| Documentation | This package, S008 evidence artifacts, cold-demo/a11y protocols, program status/coverage-matrix/debt-register updates |
| Production code | None required (verification found no regression); this package authorizes a fix **only if** grep verification in §6 had found a live `MigrationPlaceholder` import or a stray `ChatHistoryModal` import — neither was found |

### Forbidden areas

- `backend/**`, `deploy/**`, `scripts/release/**`, `alembic/**`
- verify-release, smoke, provenance/identity tooling
- Any S001–S007 ownership, route, or nav-config change
- Deleting any file still read by a frozen prior-step test
- Commit, push, or deploy

### Architectural invariants

1. RFC-101/RFC-102 ownership from S001–S007 is final; S008 only polishes and documents it.
2. No file is deleted if a frozen prior-step test still reads it via `?raw` or direct import — this is a hard rule carried over from S007's precedent (§2 of that package).
3. Protocol documents (`G9-P2`/`G9-P3`) never claim runtime execution occurred; they define the checklist for a later, separately authorized execution task.
4. `G10` remains fully out of this package's scope — no `deploy/**` file is read, referenced for modification, or touched.

---

## 5. Expected production files

### Required (new)

- `dashboard/src/s008ProductCompletionFinal.test.ts`
- `docs/releases/S008-cold-demo-protocol.md`
- `docs/releases/S008-accessibility-protocol.md`
- `docs/releases/S008-implementation-package.md` (this file)
- `docs/releases/S008-implementation-evidence.md`
- `docs/releases/S008-product-readiness-gate.md`
- `docs/releases/S008-acceptance-evidence.md`
- `docs/releases/PRODUCT-COMPLETION-PACKAGE-COVERAGE-MATRIX.md`

### Required (modified)

- `docs/releases/1.0-rfc-101-program-status.md` (S002–S008 rollup appended)
- `docs/releases/1.0-rfc-101-product-debt-register.md` (S003–S008 rows appended)

### Removed

- None. No dead-tree file is deleted (see §2/§6 rationale).

### Forbidden

- `backend/**`, `deploy/**`, `scripts/release/**`, `alembic/**`
- verify-release / smoke / provenance tooling
- Any `git commit` / `git push` / deploy invocation

---

## 6. Dead-tree / stranded-component ledger (G8-P4)

Three stranded trees exist, all left over from S002–S007 "migrate on touch" (RFC-102 P3 — copy to new owner, do not delete the original mid-migration). Each is kept in place because at least one **frozen prior-step test** reads it directly; deleting it would break already-accepted evidence. None is a duplicate *owner* (Execution Strategy R3/R6) — each has exactly one live owner elsewhere; the original is inert, unmounted source.

| Tree | Files | Superseded by | Frozen-test protection | Decision |
|------|-------|----------------|------------------------|----------|
| Legacy Analytics widgets | `src/components/analytics/*.tsx` (12 files: `AnalyticsHeader`, `AnalyticsKpiCard`, `AnalyticsKpiSection`, `AnalyticsTrendsSection`, `DistributionBarChart`, `InsightsSections`, `PopularQueriesSection`, `ProblematicQueriesSection`, `RetrievalQualitySection`, `SourceAnalyticsSection`, `TrendChartCard`) | `src/features/insights/performance/widgets/*` (S003 copy; `PerformanceScreen` is the sole live importer) | `s005HomeAskCutover.test.ts` reads `components/analytics/ProblematicQueriesSection.tsx?raw` | Accepted debt — leave in place |
| Legacy Settings encyclopedia | `src/pages/SettingsPage.tsx` (unrouted) + `src/components/settings/{SettingsAdvancedSection,RetrievalEnginePanel,MigrationFlagsPanel,SettingsHelpAccordion}.tsx` | `src/features/settings/*` (S004) + `src/features/engineering/{advanced,build}/widgets/*` (S006 copy) | `s001EngineeringMode.test.ts`, `step065Ownership.test.ts`, `s004SettingsCutover.test.ts`, `s006EngineeringIsolation.test.ts` all read these via `?raw` | Accepted debt — leave in place. **Not conflated** with `components/settings/{LlmRuntimePanel,OllamaModelsPanel}.tsx`, which remain live/shared (used by `EngStatusScreen`/`ModelsScreen`) |
| Legacy Overview widget remnants | `src/components/overview/{AnalyticsPreviewRow,AnalyticsPreviewSection,KnowledgeBaseStatusCard,OverviewFooterNote,OverviewUrlCard,StatusSummaryCard,UrlInfoCard,RequestsLineChartCard,SystemStatsCard,OverviewGrid}.tsx` | Widget capability redistributed per S007 §6 ledger (Performance, Library/Home, EngStatus, EngTensions) | `s007HomeDefaultOverview.test.ts` regex-asserts these are absent from `OverviewPage`/`PerformanceScreen`/`HomeScreen` (string match, not `?raw` import of these specific files) | Accepted debt — leave in place, consistent with the S007 precedent that first identified two of these files as orphaned |
| Legacy Overview panel (separately, frozen-test-**imported**) | `src/components/overview/OverviewKnowledgeOsPanel.tsx` | `EngStatusScreen` (release/memory/knowledge-version tags, S007) | `step065Ownership.test.ts` reads it via `?raw` directly (not just a string-absence check) | Accepted debt — leave in place (cannot be deleted without breaking a frozen import, independent of the other three) |
| Unused i18n key | `nav.overview` (en/uk) | N/A — never wired into any nav since S001/S005 | None (not test-protected, just harmless and out of scope) | Accepted debt — carried over from S007, no acceptance criterion requires removal |

**No new dead code was introduced by S008.** `components/overview/{OverviewHeader,OverviewKpiCard,SubsystemHealthPanel,icons,StatusIndicator,MetricCard}.tsx` remain live/shared and are excluded from this ledger.

**`MigrationPlaceholder` (G8-P3) verification result:** zero production importers. It is defined once (`shared/ui/MigrationPlaceholder.tsx`, re-exported from `shared/ui/index.ts`) and referenced only by regression tests (`s002KnowledgeCutover.test.ts`, `s003InsightsCutover.test.ts`, `s004SettingsCutover.test.ts`, `s005HomeAskCutover.test.ts`, `s006EngineeringIsolation.test.ts`, `s007HomeDefaultOverview.test.ts`, `s008ProductCompletionFinal.test.ts`) asserting its **absence** from canonical screens. No fix was required — the component itself is kept as a small shared helper available for any future scaffold, per its original S001 purpose.

**`ChatHistoryModal` verification result:** the component file (`components/chat/ChatHistoryModal.tsx`) has zero import usages anywhere in production source (confirmed by S006 — `AskScreen` now calls `onOpenHistory={() => navigate("/insights/activity")}` instead of mounting the modal). The file itself is kept (per task instruction "file may stay") since `s006EngineeringIsolation.test.ts` still asserts `AskScreen` does not import it (a negative string-match assertion, not an import of the modal file).

---

## 7. Testing strategy

- `dashboard/src/s008ProductCompletionFinal.test.ts` covering:
  - `/` and catch-all `*` redirect to `/home`
  - `/overview`, `/chat`, `/users`, `/analytics`, `/logs`, `/sources`, `/indexing`, `/knowledge-profile` are all redirect-only shims to their canonical owners, preserving search/hash
  - `PRODUCT_NAV` shape: Home, Knowledge trio, Ask, Insights duo, Settings quartet — no legacy path as an owner
  - No `MigrationPlaceholder` on Home/Ask/Performance/Activity/Settings×4/Engineering×6/Knowledge×3
  - `EngineeringLayout`/`ENGINEERING_NAV` expose exactly 6 destinations, all behind `RequireEngineeringMode`
  - Knowledge S002 ownership (Library/Update/Site) unchanged
- Full regression: `cd dashboard && npm test`
- Full type-check: `cd dashboard && npx tsc --noEmit`

---

## 8. Documentation requirements

Create/maintain under `docs/releases/`:

- `S008-implementation-package.md` (this file — frozen contract)
- `S008-implementation-evidence.md`
- `S008-product-readiness-gate.md`
- `S008-acceptance-evidence.md`
- `S008-cold-demo-protocol.md`
- `S008-accessibility-protocol.md`
- `PRODUCT-COMPLETION-PACKAGE-COVERAGE-MATRIX.md`
- `1.0-rfc-101-program-status.md` (updated)
- `1.0-rfc-101-product-debt-register.md` (updated)

Do not rewrite S001–S007 evidence, RFC-100/101/102, the execution roadmap, or the Master Program/Inventory/Execution Strategy.

---

## 9. Previous-step protection

S008 **must not modify** or reopen:

- S001–S007 product/engineering ownership, routes, nav config, or permissions
- RFC-100, Step 067
- Deployment architecture, provenance, identity, verify-release, smoke, backend, schema, release workflow

---

## 10. Risks

| Risk | Rating | Mitigation |
|------|--------|------------|
| Deleting a file a frozen test still reads | high if attempted | §6 ledger explicit; no deletions performed in this package |
| Overreaching into G10 (release tooling) | none | No `deploy/**` file opened for modification; documented as optional/deferred only |
| Protocol docs mistaken for executed evidence | controlled | Both protocol docs explicitly state "protocol only — no runtime execution claim" in their headers |
| Test regression from the new S008 test file | none observed | `npm test` run at 360/360 passing, `npx tsc --noEmit` clean (see evidence) |

---

## 11. Acceptance criteria

S008 is complete only when all are true:

1. `MigrationPlaceholder` has zero importers among canonical product/engineering owner screens (verified, documented).
2. No stray `ChatHistoryModal` import usages remain outside its own definition file (verified, documented).
3. All three stranded component trees are documented as accepted debt with a clear reason they are not deleted (frozen-test protection).
4. `docs/releases/S008-cold-demo-protocol.md` and `docs/releases/S008-accessibility-protocol.md` exist, are protocol-only, and make no runtime-execution claim.
5. `docs/releases/S008-implementation-package.md`, `-implementation-evidence.md`, `-product-readiness-gate.md`, `-acceptance-evidence.md` exist.
6. `docs/releases/1.0-rfc-101-program-status.md` reflects S001–S008 status (implementation-complete; commit/push/deploy/runtime/acceptance pending).
7. `docs/releases/PRODUCT-COMPLETION-PACKAGE-COVERAGE-MATRIX.md` exists covering every Appendix A package ID for S001–S008, with G10 marked optional/deferred.
8. `dashboard/src/s008ProductCompletionFinal.test.ts` exists and passes, covering the contracts in §7.
9. `docs/releases/1.0-rfc-101-product-debt-register.md` has S003–S008 accepted-debt rows appended.
10. No backend/deploy/scripts-release/alembic/verify-release/smoke/provenance file is touched; no commit/push/deploy performed.
11. `npm test` and `npx tsc --noEmit` pass.

---

## 12. Explicit non-goals

S008 will **not**:

- Move any further product/engineering ownership (S001–S007 is final)
- Delete any file a frozen prior-step test still reads
- Execute the cold-demo or accessibility protocols (protocol authoring only — execution is a later, separately authorized task)
- Touch `backend/**`, `deploy/**`, `scripts/release/**`, `alembic/**`, verify-release, smoke, or provenance tooling
- Implement `G10-P1`/`G10-P2` (documented as optional deferred only)
- Commit, push, or deploy any part of this change

---

## Implementation contract seal

This document is the **sole implementation contract** for S008.

Nothing outside this package may be implemented under the S008 label.

**S008 IMPLEMENTATION PACKAGE COMPLETE — READY FOR IMPLEMENTATION**
