# S005 — Implementation Package

**Step:** S005 — Home shell + Ask coexistence
**Program:** `docs/releases/1.0-rfc-101-master-program.md`
**Roadmap:** `docs/releases/1.0-rfc-101-execution-roadmap.md`
**Execution Strategy:** `docs/releases/1.0-rfc-101-execution-strategy.md`
**Implementation HOW:** `docs/RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md`
**Baseline:** S004 accepted state (`docs/releases/S004-*`)

**Status:** **FROZEN for implementation** — authorized, scoped, and ready for Step S005 coding
**Duration band (roadmap):** M
**Prerequisites:** S001 ACCEPTED · CLOSED (Home/Ask route substrate already provided)

---

## 1. Goal

S005 implements the **Home readiness shell** and the **Ask product-chrome coexistence shell** for Release 1.0 Dashboard Product Completion.

The exact product goal is:

1. Replace the S001 `MigrationPlaceholder` on `/home` with a real Home readiness shell per RFC-101 §7 (readiness model) and §15.2 (Home screen contract) (`G6-P1`).
2. Migrate the Chat Test product chrome (`pages/ChatTestPage.tsx`) into the canonical `/ask` product owner, keeping `ChatHistoryModal` / `ChatDiagnosticsSidebar` mounted for coexistence (`G3-P1`).
3. Convert legacy `/chat` into a compatibility redirect to `/ask` (preserving search/hash), matching the S002/S003/S004 redirect precedent.
4. Migrate touched Home/Ask product code into RFC-102 target structure (`G8-P2`).

S005 is a **product ownership migration Step**, not a deploy/remediation Step, not an Engineering Mode isolation Step, and not a backend Step.

---

## 2. Frozen scope

### In scope

- Home screen product ownership only: readiness state, checklist, primary/secondary CTA
- Ask screen product ownership only: chat product chrome migrated from `ChatTestPage`
- Redirect compatibility for the legacy `/chat` entrypoint
- Retargeting `ProblematicQueriesSection` deep links from `/chat` to `/ask`
- Route guard parity so `/ask` is gated the same as `/chat` (admin/operator)
- RFC-102 migration of touched Home/Ask product code into `features/home/*` and `features/ask/*`
- Tests and evidence for the Home/Ask cutover

### Out of scope (forbidden in this package)

| Area | Reason / Owner |
|------|----------------|
| Overview widget redistribution / emptying Overview | S006/S007 (`G6-P2`) |
| `/` default landing change (still `/overview`) | S007 (`G6-P3`) |
| `ChatHistoryModal` retirement / history ownership move to Activity | S006 (`G3-P2`–`G3-P4`) |
| Ask progressive disclosure / Eng ask-details population | S006 |
| Settings ownership (General/Models/Answers/Access) | Completed in S004; frozen |
| Knowledge ownership (Library/Update/Site) | Completed in S002; frozen |
| Insights ownership (Performance/Activity) structure | Completed in S003; frozen — only its `/chat` deep link is retargeted |
| Backend APIs, persistence, schema, Alembic | Forbidden |
| Deploy / provenance / verify-release / smoke architecture | Frozen by accepted remediation |
| Bundling S006/S007 into S005 | Explicitly forbidden |

### Future steps (not part of S005)

- S006: Engineering isolation (`G4-P4`, `G7-P5`) + Ask progressive disclosure / history modal retirement (`G3-P2`–`G3-P4`)
- S007: Home default + Overview retirement (`G6-P2`, `G6-P3`)
- S008: cleanup, validation, tooling, remaining product evidence hygiene

---

## 3. Package IDs

| Identifier | Purpose | User-visible result | Dependencies | Completion criteria |
|------------|---------|---------------------|--------------|---------------------|
| `G6-P1` | Home readiness screen | `/home` computes a single readiness state (§7) with a checklist and ≤2 CTAs | Soft: `G1-P1`. Hard for emptying Overview: `G6-P2` (deferred) | Home contract for readiness/CTA met; Overview widgets not yet required to move |
| `G3-P1` | Ask route & product chrome | `/ask` hosts the migrated chat product chrome; `/chat` becomes a compatibility redirect | Hard: `G1-P1` | Ask reachable via canonical nav/route; `/chat` bookmarks keep working |
| `G8-P2` (S005 slice) | Migrate touched Home/Ask product code into RFC-102 target structure | New/updated Home/Ask screens live in `features/home/*` and `features/ask/*` | Standing authority: RFC-102 | All new/migrated S005 owners land in RFC-102-compliant locations |

---

## 4. Architecture impact

### Allowed layers to change

| Layer / concern | Allowed S005 impact |
|-----------------|---------------------|
| Routing | `/ask` gains the same `RequireAuth roles={["admin","operator"]}` guard as `/chat`; `/chat` becomes a redirect element |
| React components | `features/home/HomeScreen.tsx`, `features/ask/AskScreen.tsx`, `pages/ChatTestPage.tsx` (redirect only) |
| Navigation | No nav changes required — Home/Ask nav entries already exist from S001 |
| Placeholders | Replace S001 `MigrationPlaceholder` on Home and Ask |
| Deep links | `ProblematicQueriesSection` (`features/insights/performance/widgets` and `components/analytics`) retargeted from `/chat` to `/ask` |
| i18n | Add `home.*` and `ask.subtitle` keys (en/uk) |
| Tests | Ownership, redirect, nav, permission, no-legacy-import, no-placeholder contracts |
| Documentation | This package, S005 evidence artifacts, review records directly tied to S005 |

### Forbidden areas

- Deployment scripts and deploy workflow
- Backend APIs, schema, Alembic, DB data model
- Release metadata, `APP_RELEASE`, lifecycle semantics
- RFC-100, Step 067, remediation law, or accepted evidence
- Settings (S004), Knowledge (S002), Insights (S003) ownership/structure — only the single Ask deep link in `ProblematicQueriesSection` is retargeted
- `/` default route change (remains `/overview` until S007)
- Removing or emptying `OverviewPage.tsx` content
- Retiring `ChatHistoryModal` / `ChatDiagnosticsSidebar` (S006 scope)
- Starting S006/S007 or bundling those packages into S005

### Architectural invariants

1. RFC-101 defines product ownership; S005 implements it, does not reinterpret it.
2. RFC-102 defines structure; migrated Home/Ask owners must land in target feature layers.
3. Legacy and final may coexist only as **redirect + final owner**, not as dual product owners.
4. S002/S003/S004 ownership remains unchanged; S005 must not regress it.
5. Home shows **at most one primary CTA and one secondary CTA** derived from the readiness state (RFC-101 §7); it must not become a chart wall or a second Overview.

---

## 5. Expected production files

### Required

- `dashboard/src/features/home/HomeScreen.tsx`
- `dashboard/src/features/ask/AskScreen.tsx`
- `dashboard/src/pages/ChatTestPage.tsx` → redirect wrapper only
- `dashboard/src/App.tsx` (route guard parity for `/ask`)
- `dashboard/src/i18n/en.ts`, `dashboard/src/i18n/uk.ts` (Home/Ask keys)
- `dashboard/src/features/insights/performance/widgets/ProblematicQueriesSection.tsx` (link retarget only)
- `dashboard/src/components/analytics/ProblematicQueriesSection.tsx` (link retarget only)
- Home/Ask-related tests under `dashboard/src/**/*test.ts*`
- S005 evidence / gate docs under `docs/releases/`

### Forbidden

- `deploy/**`
- `backend/**`
- `alembic/**`
- `APP_RELEASE` / release lifecycle metadata mutation
- `docs/releases/S001-*remediation*`
- `docs/releases/S002-*`, `docs/releases/S003-*`, `docs/releases/S004-*` (except read-only reference)
- Frozen RFCs / roadmap rewrite (`docs/RFC-101-*`, `docs/RFC-102-*`, `docs/releases/1.0-rfc-101-execution-roadmap.md`)
- Any S006/S007/S008 implementation artifacts
- `dashboard/src/pages/OverviewPage.tsx` content removal
- `dashboard/src/components/chat/ChatHistoryModal.tsx` / `ChatDiagnosticsSidebar.tsx` retirement

---

## 6. Component ownership

### Home (`G6-P1`)

| Field | Content |
|-------|---------|
| Current behavior | S001 provides canonical `/home` substrate (`MigrationPlaceholder`) |
| Target behavior | Home computes readiness state (needs_setup / needs_update / updating / ready / needs_attention per §7), shows a checklist, and ≤2 CTAs |
| Migration strategy | New feature-local screen using existing lightweight APIs (`getHealth`, `getOverview`, `getIndexStatus`, `listSources`, `getSettings`) — not the full `OverviewPage` widget set |
| Acceptance criteria | No charts, no analytics preview, no SI panels, no flags/tensions; ≤2 CTAs; loading/error states present |

### Ask (`G3-P1`)

| Field | Content |
|-------|---------|
| Current behavior | S001 provides canonical `/ask` substrate (`MigrationPlaceholder`); `ChatTestPage` still owns the chat product chrome at `/chat` |
| Target behavior | Ask is the product owner for chat product chrome; `ChatHistoryModal`/`ChatDiagnosticsSidebar` remain mounted (retirement is S006) |
| Migration strategy | Copy `ChatTestPage` body into `features/ask/AskScreen.tsx` with imports fixed to the new depth (`../../`); reuse `ChatSessionContext` unchanged |
| Acceptance criteria | Ask reachable via canonical nav/route; `/chat` is a redirect wrapper only; title uses `nav.ask`/`ask.subtitle` |

### Legacy Chat Test redirect (`G3-P1` slice)

| Field | Content |
|-------|---------|
| Current behavior | `pages/ChatTestPage.tsx` owns the chat product UI |
| Target behavior | `pages/ChatTestPage.tsx` is a redirect wrapper to `/ask`, preserving search/hash |
| Migration strategy | Mirror the `UsersPage` → `/settings/access` redirect pattern from S004 |
| Acceptance criteria | `/chat` bookmarks (including `?q=` deep links) keep working via redirect; no residual product UI |

---

## 7. Routing plan

### Canonical owners (authoritative)

| Route | Owner module |
|-------|--------------|
| `/home` | `features/home/HomeScreen` |
| `/ask` | `features/ask/AskScreen` |

### Legacy compatibility (redirects only)

| Legacy route | Destination |
|--------------|-------------|
| `/chat` | `/ask` (preserve search/hash) |

### Requirements

- `/ask` gains the same `RequireAuth roles={["admin","operator"]}` guard already applied to `/chat` in `App.tsx` (closing a pre-existing gap where `/ask` was reachable without a role guard at the route-element level)
- No duplicate ownership
- No routing regressions for Knowledge, Insights, Settings, Engineering
- `/` remains `Navigate to="/overview"` (S007 changes this, not S005)
- `/overview` remains fully populated (S006/S007 redistributes its widgets, not S005)

---

## 8. Navigation plan

No `navConfig.ts` changes required — `Home` (`/home`) and `Ask` (`/ask`) top-level nav entries already exist from the S001 scaffold and are unchanged by S005.

### Explicit non-owners in S005 nav

- No new top-level nav entries
- No Settings/Knowledge/Insights nav changes
- Engineering Mode navigation unchanged

---

## 9. State management plan

- Home: local `useState`/`useEffect` data loading (parallel `Promise.all` fetch), matching the existing `OverviewScreen`/`UpdateScreen` pattern — no new global store
- Ask: reuse `ChatSessionContext` exactly as `ChatTestPage` did; no new chat state architecture
- Do not invent a new global Home/Ask store or state library

---

## 10. UI/UX plan

- Replace the S001 `MigrationPlaceholder` on Home and Ask with real product screens
- Home: `PageHeader` + one readiness `SectionCard` (state title/description + ≤2 CTA buttons) + one checklist `SectionCard` (status badges) + one quick-access `SectionCard` (role-filtered links to `/ask`, `/knowledge/update`, `/insights/performance`, `/settings/general`)
- Home must not render charts, analytics previews, model benchmarks, flags, tensions, or SI panels (RFC-101 §15.2 Forbidden list)
- Ask: preserve the existing Chat Test UX exactly (`ChatToolbar`, `ChatMessageList`, `ChatComposer`, `ChatDiagnosticsSidebar`, `ChatHistoryModal`) — S005 is chrome relocation, not a UX redesign
- Loading and error states present on Home (`LoadingState`, `ErrorState` with retry); Ask keeps its existing `initializing` loading branch
- Reuse existing `ui` primitives; no new design-system components introduced

---

## 11. Permissions

- `/ask` and `/chat` remain `["admin", "operator"]` in `lib/permissions.ts` (already correct from the S001 baseline — no table change required)
- Close the enforcement gap: `/ask` route element in `App.tsx` now sits inside the same `RequireAuth roles={["admin","operator"]}` wrapper as `/chat`, so a `viewer` navigating directly to `/ask` is redirected to `/overview` instead of rendering the screen
- `/home` remains `["admin", "operator", "viewer"]` — unchanged
- Do not invent new role models or permission systems

---

## 12. Shared component policy

Acceptable:

- Generic `ui` primitives
- `context/ChatSessionContext` (already shared, non-page-local)
- `components/chat/**` (already shared chat UI components, reused as-is by Ask)

Rejected as permanent S005 ownership:

- Active Home/Ask screens importing business widgets from `components/overview/**` (Home) beyond simple, already-shared primitives
- Growing `pages/ChatTestPage.tsx` as a product owner
- New cross-program shared "god" modules

---

## 13. Backend boundary

S005 must not change:

- `backend/**`
- `alembic/**`
- API contracts, auth/session, `APP_RELEASE`, release_status fields
- Database schema or migrations
- Deploy / provenance / identity / verify-release / smoke tooling

S005 only calls existing `getHealth`, `getOverview`, `getIndexStatus`, `listSources`, `getSettings`, and existing chat/session APIs already used by `OverviewPage`/`ChatTestPage`. No new backend endpoints are in scope.

Expected migration strategy on deploy: `post_sync_only`
Expected Alembic head unchanged from S004 baseline.

---

## 14. Testing strategy

Minimum required coverage (follow S002/S003/S004 cutover test precedent):

- `MigrationPlaceholder` removed from Home and Ask
- Home readiness model states present; Home uses lightweight APIs, not the full Overview widget set
- Home CTA destinations include `/ask`, `/knowledge/update`, `/insights/performance`, `/settings/general` as appropriate
- Overview is not emptied; `/` still redirects to `/overview`
- Ask migrates chat product chrome and keeps `ChatHistoryModal`/`ChatDiagnosticsSidebar` mounted
- `/chat` is a redirect wrapper only, preserving search/hash
- `/ask` and `/chat` both gated to admin/operator (`lib/permissions.ts` + `App.tsx` `RequireAuth` wrapper)
- `ProblematicQueriesSection` deep links retargeted from `/chat` to `/ask` in both locations
- Home/Ask ownership lives under `features/home/**` / `features/ask/**`
- No Settings (S004) / Knowledge (S002) / Insights (S003) ownership regressions

Validation commands:

- `cd dashboard && npm test`
- `cd dashboard && npx tsc --noEmit`

No headed-browser requirement beyond existing project tooling.

---

## 15. Documentation requirements

Create/maintain only S005 evidence artifacts under `docs/releases/`:

- `S005-implementation-package.md` (this file — frozen contract)
- `S005-implementation-evidence.md`
- `S005-product-readiness-gate.md`
- `S005-acceptance-evidence.md`

Do not rewrite S001–S004 evidence, RFC-100/101/102, or the execution roadmap.

---

## 16. Previous-step protection

S005 **must not modify** or reopen:

- Phase 1/2 remediation, Full Remediation
- S001 (product scaffold / Engineering Mode substrate)
- S002 (Knowledge ownership cutover)
- S003 (Insights ownership cutover)
- S004 (Settings ownership cutover)
- RFC-100, Step 067
- Deployment architecture, provenance, identity, verify-release, smoke, backend, schema, release workflow

S005 consumes these as frozen baselines.

---

## 17. Risks

| Risk | Rating | Mitigation |
|------|--------|------------|
| Home readiness logic drifting into hardcoded business/domain rules | controlled | Readiness states are generic product UX states from RFC-101 §7, not KB domain heuristics; no industry rules or URL-pattern logic added |
| Home CTA sprawl / becoming a second Overview | controlled | ≤2 CTAs enforced by state-driven `ctasForState`; quick-access row is plain navigation, not chart/metric widgets |
| Ask/`ChatTestPage` duplicate ownership | controlled | Redirect wrapper only; ownership test asserts no chat logic remains in `ChatTestPage` |
| Broken `/chat?q=` deep links from Performance | controlled | Redirect preserves `search`/`hash`; explicit test coverage |
| Accidental Overview emptying (S006/S007 scope creep) | controlled | Explicit non-goals; test asserts `OverviewPage` still contains `AnalyticsPreviewRow` |
| Accidental Settings/Knowledge/Insights regressions | controlled | Explicit non-goals; review against this package; regression test included |

Uncontrolled redesign of deploy/backend is **not authorized**.

---

## 18. Acceptance criteria

S005 is complete only when all are true:

1. `/home` computes a readiness state per RFC-101 §7 with a checklist and ≤2 CTAs; no S001 placeholder remains.
2. `/ask` is the sole product Ask owner hosting the migrated chat product chrome; no S001 placeholder remains.
3. `/chat` is a compatibility redirect to `/ask` only, preserving search/hash.
4. `/ask` and `/chat` are both gated to admin/operator at the route-guard level.
5. `ProblematicQueriesSection` deep links (Insights widget + legacy analytics component) point to `/ask`, not `/chat`.
6. Active ownership lives under `features/home/**` and `features/ask/**`.
7. Overview is not emptied; `/` still redirects to `/overview`.
8. `ChatHistoryModal`/`ChatDiagnosticsSidebar` remain mounted in Ask (not retired).
9. Settings (S004), Knowledge (S002), Insights (S003) owners remain unchanged as product owners.
10. No backend/deploy/provenance/identity/verify-release/smoke/schema/release-metadata changes.
11. Tests and TypeScript pass for the Home/Ask cutover contracts.

---

## 19. Deliverables

- Home readiness product owner under `/home`
- Ask product owner under `/ask` hosting migrated chat chrome
- `/chat` → `/ask` redirect
- `ProblematicQueriesSection` deep links retargeted to `/ask`
- RFC-102 Home/Ask feature modules + tests + S005 evidence docs

---

## 20. Explicit non-goals

S005 will **not**:

- Empty or redistribute `OverviewPage` widgets (S006/S007, `G6-P2`)
- Change the `/` default landing route (S007, `G6-P3`)
- Retire `ChatHistoryModal` or move history ownership to Activity (S006, `G3-P2`–`G3-P4`)
- Implement Ask progressive disclosure or populate Eng ask-details (S006)
- Modify Settings ownership completed in S004
- Modify Knowledge Library/Update/Site ownership completed in S002
- Modify Insights Performance/Activity ownership/structure completed in S003 (only the single deep link is retargeted)
- Redesign deployment, publication, provenance, identity, verify-release, or smoke
- Change backend, database, Alembic, or release lifecycle metadata
- Reopen Phase 1, Phase 2, Full Remediation, S001–S004, RFC-100, or Step 067
- Invent new admin retrieval-tuning controls or hardcoded business/domain knowledge

---

## Implementation contract seal

This document is the **sole implementation contract** for S005.

Nothing outside this package may be implemented under the S005 label.

**S005 IMPLEMENTATION PACKAGE COMPLETE — READY FOR IMPLEMENTATION**
