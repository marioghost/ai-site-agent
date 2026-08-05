# S006 — Implementation Package

**Step:** S006 — Engineering isolation + Ask handoff
**Program:** `docs/releases/1.0-rfc-101-master-program.md`
**Roadmap:** `docs/releases/1.0-rfc-101-execution-roadmap.md`
**Execution Strategy:** `docs/releases/1.0-rfc-101-execution-strategy.md`
**Implementation HOW:** `docs/RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md`
**Baseline:** S005 accepted state (`docs/releases/S005-*`)

**Status:** **FROZEN for implementation** — authorized, scoped, and ready for Step S006 coding
**Duration band (roadmap):** M
**Prerequisites:** S005 (Home/Ask coexistence substrate already provided)

---

## 1. Goal

S006 completes the Engineering/Product isolation RFC-101 requires by:

1. Moving Source Intelligence generate/preview product chrome out of Knowledge Update and into Engineering Knowledge (`G4-P4`).
2. Giving Engineering Advanced and Build real content — the advanced retrieval/chunking/cache knobs and the migration-flag catalog — that Product Settings never mounts (`G7-P5`).
3. Moving Ask diagnostics ownership from the product `/ask` surface to the Engineering `/engineering/ask-details` surface (`G3-P2`).
4. Retiring `ChatHistoryModal` from Ask in favor of a handoff to `/insights/activity` (`G3-P3`).
5. Keeping Ask simple after diagnostics/history removal — progressive disclosure, no engineering dump on the product surface (`G3-P4`).
6. Populating `EngStatusScreen` and `EngTensionsScreen` with real health/tension content (or lightweight links to existing full pages) instead of the S001 `MigrationPlaceholder`, and adding Engineering section navigation.

S006 is an **Engineering/Product isolation Step**. It is not a Home-as-default Step, not an Overview-retirement Step, and not a backend Step.

---

## 2. Frozen scope

### In scope

- Source Intelligence generate/preview UX relocation: `features/knowledge/update` → `features/engineering/knowledge`
- Advanced settings knobs relocation: `components/settings/SettingsAdvancedSection` + `RetrievalEnginePanel` → `features/engineering/advanced/widgets`
- Migration flag catalog relocation: `components/settings/MigrationFlagsPanel` → `features/engineering/build/widgets`
- Ask diagnostics ownership move: `ChatDiagnosticsSidebar` off `/ask`, onto `/engineering/ask-details`
- Ask history ownership move: `ChatHistoryModal` off `/ask`, replaced with a `Navigate`/`Link` handoff to `/insights/activity`
- `EngStatusScreen` real health content (`getHealth`/`getBuildInfo`/`getIndexStatus` + `SubsystemHealthPanel`)
- `EngTensionsScreen` real lightweight content linking to `/diagnostics/epistemic-health`
- `EngineeringLayout` section navigation for the 6 Engineering destinations
- Tests and evidence for the isolation cutover

### Out of scope (forbidden in this package)

| Area | Reason / Owner |
|------|----------------|
| `/` default landing change (still `/overview`) | S007 (`G6-P3`) |
| Overview widget redistribution / emptying Overview | S007 (`G6-P2`) |
| Home ownership changes | Completed in S005; frozen |
| Ask route/chat-chrome ownership (chrome itself) | Completed in S005; frozen — S006 only removes diagnostics/history chrome |
| Settings ownership (General/Models/Answers/Access) | Completed in S004; frozen — S006 only adds Engineering owners for content that was already unmounted from product Settings |
| Knowledge ownership (Library/Update/Site) structure | Completed in S002; frozen — S006 only removes the SI panel from Update and adds a Mode-gated link |
| Insights ownership (Performance/Activity) structure | Completed in S003; frozen — S006 only adds a Link target from Ask |
| Backend APIs, persistence, schema, Alembic | Forbidden |
| Deploy / provenance / verify-release / smoke architecture | Frozen by accepted remediation |
| Commit / push / deploy | Explicitly forbidden for this task — implementation only |

### Future steps (not part of S006)

- S007: Home default + Overview retirement (`G6-P2`, `G6-P3`)
- S008: cleanup, validation, tooling, remaining product evidence hygiene

---

## 3. Package IDs

| Identifier | Purpose | User-visible result | Dependencies | Completion criteria |
|------------|---------|---------------------|--------------|---------------------|
| `G4-P4` | Source Intelligence engineering isolation | `/knowledge/update` no longer hosts SI generate/preview chrome; `/engineering/knowledge` does | Soft: S002 Update ownership | UpdateScreen has no SI panel/preview-modal import; EngKnowledgeScreen hosts them; indexing job (start/stop/reindex/reprocess) unchanged |
| `G7-P5` | Advanced/build engineering isolation | `/engineering/advanced` hosts retrieval/chunking/cache/tracing knobs; `/engineering/build` hosts the migration-flag catalog | Soft: RFC-100 Step 065 (already unmounted from product Settings) | Product Settings screens (General/Models/Answers/Access) never import `SettingsAdvancedSection`/`RetrievalEnginePanel`/`MigrationFlagsPanel` |
| `G3-P2` | Ask diagnostics → Engineering | `/ask` no longer shows a diagnostics sidebar by default; `/engineering/ask-details` does, reusing the shared chat session | Hard: S005 Ask chrome | AskScreen has no `ChatDiagnosticsSidebar` import; EngAskDetailsScreen does |
| `G3-P3` | Ask history → Activity handoff | Ask's "History" action navigates to `/insights/activity` instead of opening `ChatHistoryModal` | Hard: S003 Activity ownership | AskScreen has no `ChatHistoryModal` import; toolbar history action navigates to `/insights/activity` |
| `G3-P4` | Ask progressive disclosure | Ask stays a simple conversation surface after diagnostics/history removal | Soft: G3-P2, G3-P3 | AskScreen source contains only core chat chrome (toolbar/message list/composer) |

---

## 4. Architecture impact

### Allowed layers to change

| Layer / concern | Allowed S006 impact |
|-----------------|---------------------|
| React components | `features/engineering/**` (all 6 screens + new `widgets/` subfolders), `features/ask/AskScreen.tsx`, `features/knowledge/update/UpdateScreen.tsx`, `features/knowledge/update/widgets/IndexingActionsBar.tsx` |
| Layouts | `layouts/EngineeringLayout.tsx` (section nav, mirrors `KnowledgeLayout`) |
| Styles | `ui/styles/chat.css` (single-column Ask console modifier, since the diagnostics column is gone) |
| i18n | Add `eng.*` and `indexing.intelligence.eng_link_*` keys (en/uk) |
| Tests | Isolation/ownership/no-legacy-import contracts; update the one S005 assertion that explicitly deferred history/diagnostics retirement to S006 |
| Documentation | This package, S006 evidence artifacts |

### Forbidden areas

- Deployment scripts and deploy workflow; committing, pushing, or deploying any part of this change
- Backend APIs, schema, Alembic, DB data model
- Release metadata, `APP_RELEASE`, lifecycle semantics
- RFC-100, Step 067, remediation law, or accepted evidence
- Home ownership (S005) — untouched
- `/` default route change (remains `/overview` until S007)
- Removing or emptying `OverviewPage.tsx` content
- Bundling S007 (Home-as-default / Overview retirement) into S006

### Architectural invariants

1. RFC-101 defines product/engineering ownership; S006 implements the isolation, does not reinterpret it.
2. RFC-102 defines structure and the cross-feature import ban; Engineering-owned widgets are **copied** into `features/engineering/*/widgets` with fixed relative imports, not imported from product feature internals.
3. Product Settings and Product Ask keep exactly one owner each; Engineering screens are additive, not a second product surface.
4. S002/S003/S004/S005 ownership remains unchanged except for the explicit, narrow deltas listed in §3 (SI panel removal from Update; diagnostics/history removal from Ask).

---

## 5. Expected production files

### Required (new)

- `dashboard/src/features/engineering/knowledge/widgets/SourceIntelligencePanel.tsx`
- `dashboard/src/features/engineering/knowledge/widgets/SourceIntelligencePreviewModal.tsx`
- `dashboard/src/features/engineering/knowledge/widgets/SourceIntelligenceProfileCard.tsx`
- `dashboard/src/features/engineering/advanced/widgets/SettingsAdvancedSection.tsx`
- `dashboard/src/features/engineering/advanced/widgets/RetrievalEnginePanel.tsx`
- `dashboard/src/features/engineering/build/widgets/MigrationFlagsPanel.tsx`
- `dashboard/src/s006EngineeringIsolation.test.ts`
- S006 evidence / gate docs under `docs/releases/`

### Required (modified)

- `dashboard/src/features/ask/AskScreen.tsx`
- `dashboard/src/features/engineering/ask-details/EngAskDetailsScreen.tsx`
- `dashboard/src/features/engineering/knowledge/EngKnowledgeScreen.tsx`
- `dashboard/src/features/engineering/advanced/EngAdvancedScreen.tsx`
- `dashboard/src/features/engineering/build/EngBuildScreen.tsx`
- `dashboard/src/features/engineering/status/EngStatusScreen.tsx`
- `dashboard/src/features/engineering/tensions/EngTensionsScreen.tsx`
- `dashboard/src/features/knowledge/update/UpdateScreen.tsx`
- `dashboard/src/features/knowledge/update/widgets/IndexingActionsBar.tsx`
- `dashboard/src/layouts/EngineeringLayout.tsx`
- `dashboard/src/i18n/en.ts`, `dashboard/src/i18n/uk.ts`
- `dashboard/src/ui/styles/chat.css`
- `dashboard/src/s005HomeAskCutover.test.ts` (one assertion updated to match the S006 handoff it explicitly deferred)

### Removed (dead after relocation)

- `dashboard/src/features/knowledge/update/widgets/SourceIntelligencePanel.tsx` (superseded by the Engineering copy)
- `dashboard/src/features/knowledge/update/widgets/SourceIntelligencePreviewModal.tsx` (superseded by the Engineering copy)

### Forbidden

- `deploy/**`, `backend/**`, `alembic/**`
- `APP_RELEASE` / release lifecycle metadata mutation
- `docs/releases/S001-*` … `S005-*` (except read-only reference)
- Frozen RFCs / roadmap rewrite
- Any S007/S008 implementation artifacts
- `dashboard/src/pages/OverviewPage.tsx` content removal
- `dashboard/src/features/home/HomeScreen.tsx` changes
- Any `git commit` / `git push` / deploy invocation

---

## 6. Component ownership

### Engineering Knowledge (`G4-P4`)

| Field | Content |
|-------|---------|
| Current behavior | S001 `MigrationPlaceholder`; SI generate/preview UX lived on product `/knowledge/update` |
| Target behavior | `EngKnowledgeScreen` hosts SI stats/generate/dry-run/preview UX; Update keeps only the indexing job (start/stop/reindex/reprocess) and a Mode-gated link to Engineering Knowledge |
| Migration strategy | Copy `SourceIntelligencePanel`/`SourceIntelligencePreviewModal`/(profile display component) into `features/engineering/knowledge/widgets`, fix relative imports, replicate the status-polling + generate/dry-run handlers already used by Update (same shared index job status) |
| Acceptance criteria | `EngKnowledgeScreen` has no `MigrationPlaceholder`; `UpdateScreen` has no SI panel/preview-modal import; indexing start/stop/reindex/reprocess unaffected |

### Engineering Advanced / Build (`G7-P5`)

| Field | Content |
|-------|---------|
| Current behavior | `SettingsAdvancedSection`/`RetrievalEnginePanel`/`MigrationFlagsPanel` existed only as unmounted components (RFC-100 Step 065) or mounted on the dead legacy `pages/SettingsPage.tsx` |
| Target behavior | `EngAdvancedScreen` mounts a copy of the advanced knobs with its own settings load/save; `EngBuildScreen` mounts a copy of the flag catalog |
| Migration strategy | Copy into `features/engineering/{advanced,build}/widgets`, fix relative imports; original `components/settings/*` files remain untouched (still referenced by existing tests) |
| Acceptance criteria | Product Settings screens (General/Models/Answers/Access) never import these; Engineering screens do |

### Ask diagnostics → Engineering (`G3-P2`)

| Field | Content |
|-------|---------|
| Current behavior | `AskScreen` mounted `ChatDiagnosticsSidebar` unconditionally (S005 coexistence) |
| Target behavior | `AskScreen` no longer imports `ChatDiagnosticsSidebar`; `EngAskDetailsScreen` reuses the app-wide `ChatSessionContext` to show the same diagnostics for the currently active session, or guidance + a link to `/ask` if no session/turns exist yet |
| Migration strategy | `ChatSessionProvider` already wraps the whole app (`main.tsx`), so `useChatSession()` works identically on `/engineering/ask-details` |
| Acceptance criteria | AskScreen source has no `ChatDiagnosticsSidebar` reference; EngAskDetailsScreen source does and reuses `useChatSession` |

### Ask history → Activity handoff (`G3-P3`)

| Field | Content |
|-------|---------|
| Current behavior | `AskScreen` mounted `ChatHistoryModal`; the toolbar "History" button called `setHistoryOpen(true)` |
| Target behavior | Ask's "History" toolbar action navigates to `/insights/activity` instead |
| Migration strategy | `ChatToolbar` already delegates history-open behavior to an `onOpenHistory` callback prop (it does not own history-modal state itself, confirmed by inspection); `AskScreen` now passes `() => navigate("/insights/activity")` instead of `() => setHistoryOpen(true)` |
| Acceptance criteria | AskScreen source has no `ChatHistoryModal` reference; the toolbar's history action navigates to `/insights/activity` |

### Ask progressive disclosure (`G3-P4`)

| Field | Content |
|-------|---------|
| Target behavior | Ask keeps `ChatToolbar` + `ChatMessageList` + `ChatComposer` only; no engineering panels, no history table |
| Acceptance criteria | AskScreen renders only core chat chrome |

---

## 7. Routing plan

No route paths change in S006 — all 6 `/engineering/*` routes and `/ask` already exist from S001/S005. `EngineeringLayout` gains section navigation (`NavLink`s) for the 6 existing children routes, mirroring `KnowledgeLayout`.

---

## 8. Navigation plan

No `navConfig.ts` changes — `ENGINEERING_NAV` already lists the 6 Engineering destinations from S001; `EngineeringLayout` now renders that same list as in-page section navigation.

---

## 9. State management plan

- `EngKnowledgeScreen`: local `useState`/`useEffect` polling of `getIndexStatus`, matching the pattern already used by `UpdateScreen`
- `EngAdvancedScreen`: local `useState` settings snapshot + explicit Save button, matching `pages/SettingsPage.tsx`/`AnswersScreen` pattern
- `EngStatusScreen`: local `useState`/`useEffect` `Promise.all` fetch, matching `OverviewScreen`/`HomeScreen` pattern
- `EngAskDetailsScreen`: reuses the existing app-wide `ChatSessionContext` — no new chat state
- No new global store introduced

---

## 10. UI/UX plan

- `EngKnowledgeScreen`: `PageHeader` + the relocated SI stats/actions `SectionCard` + preview `Modal`
- `EngAdvancedScreen`: `PageHeader` with a Save action + the relocated advanced knobs `SectionCard`
- `EngBuildScreen`: `PageHeader` + the relocated flag-catalog `SectionCard`/table
- `EngStatusScreen`: `PageHeader` with a Refresh action + `SubsystemHealthPanel` (backend/db/ollama/qdrant/indexing)
- `EngTensionsScreen`: `PageHeader` + a small `MetricGrid` summary + a `SectionCard` link to the full `/diagnostics/epistemic-health` explorer
- `EngAskDetailsScreen`: `PageHeader` + explainer `Alert` + either guidance/link-to-Ask, or the relocated `ChatDiagnosticsSidebar`
- `AskScreen`: unchanged core chat chrome, single-column console (diagnostics column removed)
- `UpdateScreen`: unchanged indexing job UI; SI panel replaced with a small Mode-gated `SectionCard` link to `/engineering/knowledge` (hidden entirely when Engineering Mode is off)
- `EngineeringLayout`: `nav` bar of 6 `NavLink`s, styled like `KnowledgeLayout`

---

## 11. Permissions

No permission table changes. All `/engineering/*` routes remain `admin`-only behind `RequireEngineeringMode` (Mode on + `admin` role); `/ask` remains `admin`/`operator`; `/insights/activity` remains `admin`/`operator`/`viewer` — all unchanged from S001–S005.

---

## 12. Shared component policy

Acceptable:

- Generic `ui` primitives
- `context/ChatSessionContext` (already shared, non-page-local) reused by both `AskScreen` and `EngAskDetailsScreen`
- `components/chat/**`, `components/overview/SubsystemHealthPanel`, `components/overview/icons` (already-shared, non-feature components, reused as-is — same precedent as S005's Ask reusing `components/chat/**`)

Rejected as permanent S006 ownership:

- Engineering features importing another feature's internals directly (e.g. `features/knowledge/update/widgets/*`, `components/settings/*`) — these are **copied** with fixed imports instead, per RFC-102 §4.1's duplication-ban exception for cross-feature/cross-layer isolation
- Reintroducing `MigrationPlaceholder` on any of the 6 Engineering screens

---

## 13. Backend boundary

S006 must not change:

- `backend/**`, `alembic/**`
- API contracts, auth/session, `APP_RELEASE`, release_status fields
- Database schema or migrations

S006 only calls existing `getHealth`, `getBuildInfo`, `getIndexStatus`, `getSettings`, `updateSettings`, `clearAllCaches`, `clearRetrievalCache`, `generateSourceIntelligence`, `getSourceIntelligenceStats`, `getEpistemicHealthSummary`, and the existing chat/session APIs. No new backend endpoints are in scope.

Expected migration strategy on deploy: `post_sync_only` (not exercised — this task does not deploy).
Expected Alembic head unchanged from S005 baseline.

---

## 14. Testing strategy

- `dashboard/src/s006EngineeringIsolation.test.ts` covering:
  - AskScreen has no `ChatDiagnosticsSidebar`/`ChatHistoryModal`/`MigrationPlaceholder` imports; keeps core chat chrome; hands history off to `/insights/activity`
  - `ChatToolbar` does not itself own history-modal state
  - `EngAskDetailsScreen` hosts diagnostics ownership, reusing `useChatSession`
  - All 6 Engineering screens are free of `MigrationPlaceholder`
  - `UpdateScreen` has no SI panel/preview-modal/`generateSourceIntelligence` import, keeps the indexing job intact, and links to Engineering Knowledge only when Engineering Mode is on
  - `EngKnowledgeScreen` hosts the SI generate/preview UX
  - `EngAdvancedScreen`/`EngBuildScreen` host the relocated advanced knobs / flag catalog
  - Product Settings screens never mount advanced knobs or the flag catalog
  - `EngStatusScreen` is a real health screen using `getHealth`/`getBuildInfo`
  - `EngTensionsScreen` links to `/diagnostics/epistemic-health`
  - `EngineeringLayout` renders section nav for all 6 Engineering destinations
- Update the one `s005HomeAskCutover.test.ts` assertion that explicitly deferred history/diagnostics retirement to S006 (comment said "S006 retires these")
- Full regression: `cd dashboard && npm test`
- Full type-check: `cd dashboard && npx tsc --noEmit`

---

## 15. Documentation requirements

Create/maintain only S006 evidence artifacts under `docs/releases/`:

- `S006-implementation-package.md` (this file — frozen contract)
- `S006-implementation-evidence.md`
- `S006-product-readiness-gate.md`
- `S006-acceptance-evidence.md`

Do not rewrite S001–S005 evidence, RFC-100/101/102, or the execution roadmap.

---

## 16. Previous-step protection

S006 **must not modify** or reopen:

- S001 (product scaffold / Engineering Mode substrate)
- S002 (Knowledge ownership cutover) — except the narrow SI-panel removal from Update explicitly authorized here
- S003 (Insights ownership cutover) — except linking to it from Ask/EngTensions
- S004 (Settings ownership cutover) — except adding Engineering owners for already-unmounted content
- S005 (Home/Ask coexistence) — except the narrow diagnostics/history removal from Ask explicitly authorized here
- RFC-100, Step 067
- Deployment architecture, provenance, identity, verify-release, smoke, backend, schema, release workflow

---

## 17. Risks

| Risk | Rating | Mitigation |
|------|--------|------------|
| Duplicating SI/advanced/flags widgets creates drift between product-frozen originals and Engineering copies | controlled | Copies are isolated to Engineering-only concerns (product originals for SI were deleted since fully superseded; Settings/flags originals are kept since still referenced by S001/Step-065 tests) |
| Ask regression from removing diagnostics/history | controlled | Explicit test coverage that Ask keeps its core chat chrome; diagnostics/history remain reachable via Engineering/Activity |
| EngAskDetailsScreen depending on shared `ChatSessionContext` could leak session state across users/tabs | none (pre-existing) | `ChatSessionContext` was already app-wide since S001/S005; S006 does not change its scope, only which screen renders its diagnostics view |
| Update's SI removal breaking the shared indexing job status semantics | controlled | `running`/`Stop` continue to derive from the shared job `status.status`, not from an Update-local “SI running” flag |
| Accidental Home/Overview/S007 scope creep | controlled | Explicit non-goals section; no changes to `HomeScreen.tsx` or `OverviewPage.tsx` |

---

## 18. Acceptance criteria

S006 is complete only when all are true:

1. `/knowledge/update` no longer hosts the Source Intelligence generate/preview UX; `/engineering/knowledge` does; the indexing job itself (start/stop/reindex/reprocess) is unaffected.
2. `/engineering/advanced` hosts the advanced retrieval/chunking/cache/tracing knobs; `/engineering/build` hosts the migration-flag catalog; Product Settings never mounts either.
3. `/ask` no longer shows a diagnostics sidebar by default; `/engineering/ask-details` does (reusing the shared chat session, or showing guidance + a link to Ask).
4. `/ask` no longer opens a history modal; its history action navigates to `/insights/activity`.
5. Ask remains a simple, product-only chat surface (core chrome only) after diagnostics/history removal.
6. `EngStatusScreen` and `EngTensionsScreen` are free of the S001 `MigrationPlaceholder` and provide real (or link-based) content.
7. `EngineeringLayout` provides section navigation for all 6 Engineering destinations.
8. No Home/Overview/S007 scope leakage; `/` still redirects to `/overview`.
9. Settings (S004), Knowledge (S002)/Insights (S003) structural ownership remain unchanged beyond the narrow deltas in §3.
10. No backend/deploy/provenance/identity/verify-release/smoke/schema/release-metadata changes; no commit/push/deploy performed.
11. `npm test` and `npx tsc --noEmit` pass, including the updated S005 assertion.

---

## 19. Deliverables

- Engineering-owned Source Intelligence generate/preview UX under `/engineering/knowledge`
- Engineering-owned advanced knobs and flag catalog under `/engineering/advanced` and `/engineering/build`
- Ask diagnostics ownership relocated to `/engineering/ask-details`
- Ask history handoff to `/insights/activity`
- Real `EngStatusScreen`/`EngTensionsScreen` content
- `EngineeringLayout` section navigation
- Tests + S006 evidence docs

---

## 20. Explicit non-goals

S006 will **not**:

- Change the `/` default landing route or redistribute Overview widgets (S007, `G6-P2`/`G6-P3`)
- Modify Home ownership completed in S005
- Modify Ask's core chat product chrome (toolbar/message list/composer) beyond removing diagnostics/history
- Modify Settings ownership completed in S004 beyond adding Engineering owners for already-unmounted content
- Modify Knowledge Library/Site ownership completed in S002, or Update's indexing job semantics
- Modify Insights Performance/Activity ownership/structure completed in S003
- Commit, push, or deploy any part of this change
- Invent new admin retrieval-tuning controls or hardcoded business/domain knowledge

---

## Implementation contract seal

This document is the **sole implementation contract** for S006.

Nothing outside this package may be implemented under the S006 label.

**S006 IMPLEMENTATION PACKAGE COMPLETE — READY FOR IMPLEMENTATION**
