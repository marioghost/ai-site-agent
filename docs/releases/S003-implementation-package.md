# S003 — Implementation Package

**Step:** S003 — Insights product cutover  
**Program:** `docs/releases/1.0-rfc-101-master-program.md`  
**Roadmap:** `docs/releases/1.0-rfc-101-execution-roadmap.md`  
**Execution Strategy:** `docs/releases/1.0-rfc-101-execution-strategy.md`  
**Implementation HOW:** `docs/RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md`  
**Baseline commit:** `9a7134c05e2e9348baf65b59c2d75f4fcfdb1ac9`  

**Status:** **FROZEN for implementation** — authorized, scoped, and ready for Step S003 coding  
**Duration band (roadmap):** L  
**Prerequisites:** S001 ACCEPTED · CLOSED; S002 ACCEPTED · CLOSED (Knowledge cutover complete; must not be reopened)

---

## 1. Goal

S003 completes the **Insights product cutover** for Release 1.0 Dashboard Product Completion.

The exact product goal is:

1. Move product-facing Insights surfaces to their RFC-101 owners:
   - Performance under `/insights/performance`
   - Activity under `/insights/activity`
2. Make those canonical Insights screens the **sole product owners** for analytics and activity/history jobs.
3. Convert legacy top-level entrypoints (`/analytics`, `/logs`) into compatibility redirects rather than parallel owners.
4. Complete Insights section layout / in-section navigation so Performance and Activity are the only Insights children.
5. Leave Activity ready as the history owner for later Ask handoff (`G3-P3` in S006) **without** performing that handoff in S003.
6. Leave Performance ready as a receiver for later Overview chart/feed redistribution (`G6-P2` in S007) **without** emptying Overview in S003.

S003 is a **product ownership migration Step**, not a deploy/remediation Step, not an Engineering Mode isolation Step, not a Home/Overview Step, and not a backend Step.

---

## 2. Frozen scope

### In scope

- Insights section product ownership only
- Canonical route ownership for Performance / Activity
- Redirect compatibility for legacy Analytics / Logs entrypoints
- Insights navigation, labels, section shell, and screen ownership
- RFC-102 migration of touched Insights product code into `features/insights/*`
- Tests and acceptance evidence for the Insights cutover
- Documentation directly required by S003 evidence/review flow

### Out of scope (forbidden in this package)

| Area | Reason / Owner |
|------|----------------|
| Knowledge ownership / Library / Update / Site | Completed in S002; frozen |
| Settings split (`G7-*`) | S004 |
| Home shell / Ask coexistence (`G6-P1`, `G3-P1`) | S005 |
| Ask history modal retirement / Eng ask-details (`G3-P2`–`G3-P4`) | S006 |
| Overview widget redistribution / Home default (`G6-P2`, `G6-P3`) | S007 |
| Structure polish / cleanup / validation tooling | S008 |
| Engineering Mode isolation moves (`G4-P4`, `G7-P5`, …) | S006 |
| Backend APIs, persistence, schema, Alembic | Forbidden |
| Deploy / provenance / verify-release / smoke architecture | Frozen by accepted remediation |
| Release metadata / lifecycle semantics | Frozen |
| Bundling S004+ into S003 | Explicitly forbidden |

### Future steps (not part of S003)

- S004: Settings product split
- S005: Home shell + Ask coexistence shell
- S006: Engineering isolation + Ask progressive disclosure / history handoff
- S007: Home default + Overview retirement
- S008: cleanup, validation, tooling, remaining product evidence hygiene

---

## 3. Package IDs

| Identifier | Purpose | User-visible result | Dependencies | Completion criteria |
|------------|---------|---------------------|--------------|---------------------|
| `G5-P1` | Performance becomes the product owner for analytics / performance workflows | Users navigate to a real Performance screen under `/insights/performance`; old Analytics surface no longer acts as a parallel top-level owner | Hard: S001 Insights routes; soft: later `G6-P2` for Overview chart move timing | `/insights/performance` is the product analytics owner; legacy `/analytics` redirects; no second product-level Analytics owner remains; Performance is receiver-capable for later Overview charts without performing that move now |
| `G5-P2` | Activity becomes the product owner for past questions / request activity | Users manage activity/history under `/insights/activity`; old Logs surface no longer owns the product job | Hard: S001 Insights routes | `/insights/activity` is the unique product activity/history owner; `/logs` redirects; Activity is ready for later Ask handoff (`G3-P3`) without performing that handoff in S003 |
| `G5-P3` | Insights section layout owns in-section sub-navigation | Users move between Performance and Activity inside Insights without extra top-level Insights children | Hard: S001 Insights paths; soft: `G5-P1`/`G5-P2` | Insights layout provides Performance/Activity section nav only; no extra top-level Insights children |
| `G1-P2` (S003 slice) | Apply redirect increments for retired Insights legacy paths | Legacy Analytics/Logs bookmarks keep working while canonical Insights routes become authoritative | Hard: `G5-P1`/`G5-P2` ownership decisions | `/analytics` → Performance and `/logs` → Activity resolve via redirects without duplicate product ownership |
| `G8-P2` (S003 slice) | Migrate touched Insights product code into RFC-102 target structure | New/updated Insights screens live in `features/insights/*`, thin pages, layouts, and shared modules | Standing authority: RFC-102 | All new or migrated S003 owners land in RFC-102-compliant locations; no permanent new product logic is added to legacy Analytics/Logs page monoliths |

---

## 4. Architecture impact

### Allowed layers to change

| Layer / concern | Allowed S003 impact |
|-----------------|---------------------|
| Routing | Canonical Insights routes remain authoritative; legacy Analytics/Logs entrypoints become redirects |
| Navigation | Sidebar / section navigation labels, ordering, and destinations for Insights only |
| React components | Insights screens, Insights widgets, thin route adapters, Insights layout |
| Page ownership | Transfer Analytics/Logs product ownership to Performance/Activity |
| Menus / sidebar | Remove duplicate top-level Analytics/Logs product owners; point users to canonical Insights owners |
| Placeholders | Replace S001 scaffold placeholders only for S003-owned Insights destinations |
| Insights screens | Performance / Activity product screens and their feature-local widgets |
| Analytics / Logs entrypoints | Compat redirects and owner cutover only |
| Tests | Ownership, redirect, nav, compatibility, runtime evidence support |
| Documentation | This package, S003 evidence artifacts, review records directly tied to S003 |

### Forbidden areas

- Deployment scripts and deploy workflow
- Provenance generation or verification logic
- `verify_release.sh`, `smoke-staging.sh`, release-check remediation behavior
- Backend APIs, schema, Alembic, DB data model
- Release metadata, `APP_RELEASE`, lifecycle semantics
- RFC-100, Step 067, remediation law, or accepted evidence
- Knowledge owners completed in S002 (`features/knowledge/**` product behavior), except unavoidable shared link updates that point *to* Insights (must not reopen Knowledge ownership)
- Engineering Mode destinations outside preserving current behavior
- Overview emptying, Home default change, Ask history modal retirement
- Starting S004+ or bundling those packages into S003

### Architectural invariants

1. RFC-101 defines product ownership; S003 implements it, does not reinterpret it.
2. RFC-102 defines structure; migrated Insights owners must land in target feature/layout/page layers.
3. Legacy and final may coexist only as **redirect + final owner**, not as dual product owners.
4. Engineering Mode isolates complexity; S003 must not leak engineering surfaces into default product.
5. S002 Knowledge ownership remains the sole Knowledge product owner set; S003 must not regress it.

---

## 5. Expected production files

Paths are expected from baseline `9a7134c` plus RFC-102 Insights targets. Final filenames may vary slightly but must remain inside these boundaries.

### Required

- `dashboard/src/App.tsx`
- `dashboard/src/layouts/InsightsLayout.tsx`
- `dashboard/src/lib/navConfig.ts` (Insights destinations only if still incorrect; already points to `/insights/performance` and `/insights/activity` on baseline)
- `dashboard/src/lib/permissions.ts` if route/nav permissions require explicit Insights owner updates
- `dashboard/src/features/insights/performance/*`
- `dashboard/src/features/insights/activity/*`
- `dashboard/src/features/insights/shared/*` if sibling-sharing is needed
- `dashboard/src/pages/AnalyticsPage.tsx` → redirect wrapper only
- `dashboard/src/pages/LogsPage.tsx` → redirect wrapper only
- `dashboard/src/i18n/en.ts`
- `dashboard/src/i18n/uk.ts`
- Product link bridges that still target `/analytics` or `/logs` (e.g. Overview preview links) — retarget to canonical Insights routes only
- Insights-related tests under `dashboard/src/**/*test.ts*`
- S003 evidence / gate docs under `docs/releases/`

### Optional

- `dashboard/src/shared/ui/*` if Insights product screens need already-authorized primitive reuse
- `dashboard/src/hooks/*` if a reusable hook is used by more than one Insights feature
- `dashboard/src/api/resources/*` or feature-local Insights API modules if current fetch ownership needs clean RFC-102 placement
- `dashboard/src/types/*` for shared Insights DTO typing only
- `dashboard/src/components/analytics/*` **only** as temporary copy source for migration into `features/insights/**`; active owners must not permanently depend on legacy feature trees after cutover

### Forbidden

- `deploy/**`
- `scripts/release/**`
- `backend/**`
- `alembic/**`
- `APP_RELEASE` / release lifecycle metadata mutation
- `docs/releases/S001-*remediation*`
- `docs/releases/S002-*` (except read-only reference)
- Frozen RFCs / roadmap rewrite (`docs/RFC-101-*`, `docs/RFC-102-*`, `docs/releases/1.0-rfc-101-execution-roadmap.md`)
- Any S004/S005/S006/S007/S008 implementation artifacts
- Knowledge product ownership redesign under `features/knowledge/**`

---

## 6. Component ownership

### Performance (`G5-P1`)

| Field | Content |
|-------|---------|
| Current behavior | S001 provides canonical `/insights/performance` substrate (placeholder); legacy `AnalyticsPage` still owns analytics product behavior under `/analytics` |
| Target behavior | Performance is the sole product owner for analytics / performance workflows |
| Migration strategy | Move/compose product-facing Analytics behavior into Performance owner under RFC-102 `features/insights/performance`; legacy `/analytics` becomes compatibility redirect |
| Receiver note | Performance must be capable of receiving Overview chart widgets later (`G6-P2`); S003 does **not** move Overview widgets now |
| Rollback impact | Revert S003 commit(s); runtime returns to accepted `9a7134c` baseline |
| Acceptance criteria | Performance reachable via canonical nav/route; Analytics is not a parallel product owner; redirect compatibility proven |

### Activity (`G5-P2`)

| Field | Content |
|-------|---------|
| Current behavior | S001 provides canonical `/insights/activity` substrate (placeholder); legacy `LogsPage` still owns logs/activity behavior under `/logs` |
| Target behavior | Activity is the unique product owner for past questions / request activity |
| Migration strategy | Move product-facing Logs behavior into Activity owner under `features/insights/activity`; legacy `/logs` becomes redirect-only |
| Handoff note | Activity must be ready for later Ask history One-Place handoff (`G3-P3` / S006); S003 does **not** retire Chat history modal or change Ask ownership |
| Rollback impact | Revert S003 commit(s); `9a7134c` substrate remains intact |
| Acceptance criteria | Activity owns history/activity job; ownership not duplicated at top-level Logs; redirect proven |

### Insights section shell (`G5-P3`)

| Field | Content |
|-------|---------|
| Current behavior | `InsightsLayout` is a passthrough `<Outlet />` without section navigation |
| Target behavior | Insights layout provides Performance / Activity section navigation only |
| Migration strategy | Mirror the KnowledgeLayout pattern used in S002: in-section `NavLink`s to canonical Insights owners |
| Acceptance criteria | No extra top-level Insights children; section nav is the in-Insights owner switcher |

### Legacy Analytics / Logs pages

| Field | Content |
|-------|---------|
| Target behavior | Redirect wrappers only (`Navigate` to canonical Insights owners) |
| Forbidden | Retaining independent product UX, tables, fetch orchestration, or dual ownership |

---

## 7. Routing plan

### Canonical owners (authoritative)

| Route | Owner module |
|-------|--------------|
| `/insights/performance` | `features/insights/performance/PerformanceScreen` (+ widgets) |
| `/insights/activity` | `features/insights/activity/ActivityScreen` (+ widgets) |
| `/insights` index | Navigate to `performance` (or existing S001 default) — must not invent a third Insights product owner |

### Legacy compatibility (redirects only)

| Legacy route | Destination |
|--------------|-------------|
| `/analytics` | `/knowledge`-style redirect to `/insights/performance` |
| `/logs` | `/insights/activity` |

### Requirements

- Legacy pages are redirect wrappers only
- No duplicate ownership
- No routing regressions for Knowledge, Settings, Ask, Engineering, Home
- Canonical Insights routes are the only owners for Performance/Activity jobs

---

## 8. Navigation plan

### Product sidebar (`navConfig`)

Insights children must remain:

- Performance → `/insights/performance`
- Activity → `/insights/activity`

Remove any remaining product-nav dependence on `/analytics` or `/logs` as owners (permissions/links/bridges only).

### Insights section navigation (`InsightsLayout`)

- Performance
- Activity

are the **only** Insights navigation owners inside the section shell.

### Explicit non-owners in S003 nav

- No top-level Analytics product entry
- No top-level Logs product entry
- No new Insights children beyond Performance / Activity
- Engineering Mode navigation unchanged
- Knowledge navigation unchanged (S002)

---

## 9. State management plan

- Keep existing client-local state patterns used by Analytics/Logs (React state / existing hooks)
- Do not introduce a new global Insights store, context architecture, or state library
- Do not invent new backend caching contracts
- Feature-local state lives with Performance / Activity owners
- Shared Insights state helpers only when genuinely shared between Performance and Activity (place under `features/insights/shared`)

---

## 10. UI/UX plan

- Replace S001 `MigrationPlaceholder` on Performance and Activity with real product screens
- Preserve existing Analytics/Logs UX capabilities that are product-facing (KPIs, trends, distributions, popular/problematic queries, retrieval quality, source analytics, logs/activity lists) unless a capability is explicitly engineering-only (leave engineering-only for S006)
- Loading, empty, and error states must exist for both owners
- Do not redesign the whole design system; reuse existing `ui` primitives and established patterns from migrated screens
- Do not add dashboard-of-dashboards chrome, new card systems, or marketing layouts

---

## 11. Insights layout plan (`G5-P3`)

- Implement section navigation in `InsightsLayout` analogous to S002 `KnowledgeLayout`
- Labels from i18n (`nav.performance`, `nav.activity`, `nav.insights`)
- Active-state styling consistent with existing design tokens
- Outlet renders the active Insights owner only
- No third Insights child route in S003

---

## 12. Analytics migration plan (`G5-P1`)

1. Inventory `AnalyticsPage` and `components/analytics/*` product widgets used by the page.
2. Migrate product composition into `features/insights/performance/**` (screen + feature-local widgets).
3. Ensure active Performance imports do **not** permanently depend on `pages/AnalyticsPage` or leave business ownership in `components/analytics/**` after cutover (RFC-102 / S002 precedent).
4. Convert `pages/AnalyticsPage.tsx` to redirect wrapper → `/insights/performance`.
5. Retarget product links still pointing at `/analytics` (e.g. Overview preview link) to `/insights/performance`.
6. Do **not** move Overview chart widgets into Performance in S003; only ensure receiver readiness (structure/hooks/extension points as needed without Overview emptying).

---

## 13. Logs migration plan (`G5-P2`)

1. Inventory `LogsPage` and related product widgets.
2. Migrate product composition into `features/insights/activity/**`.
3. Ensure active Activity imports do not permanently depend on `pages/LogsPage` or legacy logs feature trees after cutover.
4. Convert `pages/LogsPage.tsx` to redirect wrapper → `/insights/activity`.
5. Retarget product links still pointing at `/logs` to `/insights/activity`.
6. Do **not** retire Ask `ChatHistoryModal` or perform `G3-P3` One-Place handoff in S003; Activity must simply be the canonical product history/activity owner surface.

---

## 14. Redirect strategy (`G1-P2` S003 slice)

| From | To | Mechanism |
|------|----|-----------|
| `/analytics` | `/insights/performance` | Client `Navigate` wrapper (preserve search/hash), same pattern as S002 |
| `/logs` | `/insights/activity` | Client `Navigate` wrapper (preserve search/hash) |

Rules:

- Redirect wrappers only — no residual product UI
- Preserve query string and hash where practical
- No server nginx redirect redesign required
- Permissions must allow both legacy and canonical paths during compatibility, or map cleanly so authorized users are not locked out

---

## 15. Permissions

- Keep Insights canonical routes authorized for existing roles (`admin`, `operator`, `viewer`) as on baseline
- Ensure legacy `/analytics` and `/logs` remain reachable for redirect compatibility for the same roles, or redirect before permission denial — do not strand bookmarks
- Do not invent new role models or permission systems
- Do not change Engineering Mode permission architecture

---

## 16. Shared component policy

Acceptable:

- Generic `ui` primitives
- Truly shared Insights helpers under `features/insights/shared/**`
- Existing overview presentational helpers only when genuinely generic (same bar as S002)

Rejected as permanent S003 ownership:

- Active Performance/Activity screens importing business widgets from `components/analytics/**` or legacy logs trees after cutover
- Growing `pages/AnalyticsPage.tsx` / `pages/LogsPage.tsx` as product owners
- New cross-program shared “god” modules

Legacy `components/analytics/**` may remain on disk temporarily as inactive copy sources; they must not remain the active product owner.

---

## 17. Backend boundary

S003 must not change:

- `backend/**`
- `alembic/**`
- API contracts, auth/session, APP_RELEASE, release_status fields
- Database schema or migrations
- Deploy / provenance / identity / verify-release / smoke tooling

S003 may continue calling existing analytics/logs APIs already used by `AnalyticsPage` / `LogsPage`. New backend endpoints are out of scope.

Expected migration strategy on deploy: `post_sync_only`  
Expected Alembic head unchanged: `0020_step_063_kos_flags_default_on`

---

## 18. Testing strategy

Minimum required coverage (follow S002 cutover test precedent):

- Canonical Insights routes registered
- Legacy `/analytics` and `/logs` are redirect wrappers only
- Product nav contains Performance / Activity only under Insights
- `InsightsLayout` section nav contains only Performance / Activity
- Placeholders removed from Performance / Activity owners
- Owner modules live under `features/insights/**` and do not import legacy owner trees
- No Knowledge ownership regressions (smoke assertion or explicit non-touch proof)

Validation commands (pre-commit / pre-deploy as applicable):

- `cd dashboard && npm test`
- `cd dashboard && npx tsc --noEmit`

No headed-browser requirement beyond existing project tooling.

---

## 19. Documentation requirements

Create/maintain only S003 evidence artifacts under `docs/releases/` as needed by the review chain, for example:

- `S003-implementation-package.md` (this file — frozen contract)
- `S003-implementation-evidence.md`
- `S003-product-readiness-gate.md`
- `S003-acceptance-evidence.md`

Do not rewrite S001/S002 remediation docs, RFC-100/101/102, or the execution roadmap.

---

## 20. Previous-step protection

S003 **must not modify** or reopen:

- Phase 1 (publication/provenance remediation)
- Phase 2 (verify-release / smoke / temps / backend FE identity preserve)
- Full Remediation
- S001 (product scaffold / Engineering Mode substrate)
- S002 (Knowledge ownership cutover — Library / Update / Site)
- RFC-100
- Step 067
- Deployment architecture, provenance, identity, verify-release, smoke, backend, schema, release workflow

S003 consumes these as frozen baselines.

---

## 21. Risks

| Risk | Rating | Mitigation |
|------|--------|------------|
| Dual ownership if Analytics/Logs retain UI | controlled | Redirect wrappers only; ownership tests |
| Incomplete widget migration / import from legacy trees | controlled | RFC-102 ownership review + import contracts |
| Accidental Overview / Ask / Knowledge changes | controlled | Explicit non-goals; review against this package |
| Link bridges still pointing at `/analytics` or `/logs` | controlled | Grep/retarget product links |
| Scope creep into G6-P2 / G3-P3 | controlled | Soft deps documented; forbidden in non-goals |
| Deploy architecture touch | controlled | Forbidden path list |

Uncontrolled redesign of deploy/provenance/backend is **not authorized**.

---

## 22. Acceptance criteria

S003 is complete only when all are true:

1. `/insights/performance` is the sole product Performance/analytics owner.
2. `/insights/activity` is the sole product Activity/history owner.
3. `/analytics` and `/logs` are compatibility redirects only.
4. `InsightsLayout` provides Performance/Activity section navigation only.
5. S001 placeholders are removed from Performance and Activity.
6. Active ownership lives under `features/insights/{performance,activity,shared}/**`.
7. No permanent new product logic remains in Analytics/Logs page monoliths.
8. Product nav has no duplicate top-level Analytics/Logs owners.
9. Knowledge S002 owners remain unchanged as product owners.
10. No backend/deploy/provenance/identity/verify-release/smoke/schema/release-metadata changes.
11. Tests and TypeScript pass for the Insights cutover contracts.
12. Runtime after deploy proves canonical routes, redirects, identity chain, and health without accepting S004+.

---

## 23. Evidence requirements

Required review chain evidence:

- Implementation evidence (files, ownership, redirects)
- Commit / push scope limited to S003 frontend/tests/docs
- Deployment via `sudo bash deploy/manage_deploy.sh deploy full` only
- Runtime validation of Insights canonical routes + legacy redirects + identity/provenance/verify-release/smoke/health
- Final acceptance against this package only

Must prove:

- Package IDs `G5-P1`, `G5-P2`, `G5-P3`, `G1-P2` (S003), `G8-P2` (S003) satisfied
- No S004+ leakage
- Previous-step protection held

---

## 24. Deliverables

- Performance product owner under `/insights/performance`
- Activity product owner under `/insights/activity`
- Insights section layout with Performance/Activity nav
- `/analytics` → `/insights/performance` redirect
- `/logs` → `/insights/activity` redirect
- RFC-102 Insights feature modules + tests + S003 evidence docs
- Product readiness / acceptance evidence for Insights cutover
- Activity ready for later Ask handoff (capability present; handoff not executed)
- Performance ready as later Overview chart receiver (receiver present; Overview not emptied)

---

## 25. Explicit non-goals

S003 will **not**:

- Implement S004 Settings split
- Implement S005 Home / Ask coexistence shell
- Implement S006 Engineering isolation or Ask progressive disclosure / history modal retirement
- Implement S007 Overview redistribution or Home-as-default
- Implement S008 cleanup/tooling program
- Modify Knowledge Library / Update / Site ownership completed in S002
- Redesign deployment, publication, provenance, identity, verify-release, or smoke
- Change backend, database, Alembic, or release lifecycle metadata
- Reopen Phase 1, Phase 2, Full Remediation, S001, S002, RFC-100, or Step 067
- Add new Insights top-level children beyond Performance / Activity
- Invent new admin retrieval-tuning controls or hardcoded business knowledge

---

## Implementation contract seal

This document is the **sole implementation contract** for S003.

Nothing outside this package may be implemented under the S003 label.

**S003 IMPLEMENTATION PACKAGE COMPLETE — READY FOR IMPLEMENTATION**
