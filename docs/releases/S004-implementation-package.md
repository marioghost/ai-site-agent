# S004 — Implementation Package

**Step:** S004 — Settings product split (except Eng Advanced move)
**Program:** `docs/releases/1.0-rfc-101-master-program.md`
**Roadmap:** `docs/releases/1.0-rfc-101-execution-roadmap.md`
**Execution Strategy:** `docs/releases/1.0-rfc-101-execution-strategy.md`
**Implementation HOW:** `docs/RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md`
**Baseline commit:** `9a7134c05e2e9348baf65b59c2d75f4fcfdb1ac9`

**Status:** **FROZEN for implementation** — authorized, scoped, and ready for Step S004 coding
**Duration band (roadmap):** L
**Prerequisites:** S001 ACCEPTED · CLOSED (Settings routes + General substrate already provided)

---

## 1. Goal

S004 completes the **Settings product split** for Release 1.0 Dashboard Product Completion, excluding the Engineering Advanced/Build move (`G7-P5`, deferred to S006).

The exact product goal is:

1. Finish General beyond its Mode-toggle host role (`G7-P1`).
2. Give Models sole ownership of chat/embedding model selection and pull/install (`G7-P2`).
3. Give Answers sole ownership of the four answer-quality modes plus the minimal answer-facing toggles, with no retrieval engine panel and no advanced knobs (`G7-P3`).
4. Migrate Users into Access under Settings and turn `/users` into a compatibility redirect (`G7-P4`, `G1-P2` slice).
5. Migrate touched Settings product code into RFC-102 target structure (`G8-P2`).

S004 is a **product ownership migration Step**, not a deploy/remediation Step, not an Engineering Mode isolation Step, and not a backend Step.

---

## 2. Frozen scope

### In scope

- Settings section product ownership only: General / Models / Answers / Access
- Canonical route ownership for the four Settings children
- Redirect compatibility for the legacy `/users` entrypoint
- Settings navigation, labels, section shell, and screen ownership
- RFC-102 migration of touched Settings product code into `features/settings/*`
- Tests and acceptance evidence for the Settings cutover

### Out of scope (forbidden in this package)

| Area | Reason / Owner |
|------|----------------|
| Knowledge ownership / Library / Update / Site | Completed in S002; frozen |
| Insights ownership / Performance / Activity | Completed in S003; frozen |
| Advanced knobs/prompt → Eng Advanced; flag catalogs → Eng Build (`G7-P5`) | S006 |
| Home shell / Ask coexistence (`G6-P1`, `G3-P1`) | S005 |
| Ask history modal retirement / Eng ask-details (`G3-P2`–`G3-P4`) | S006 |
| Overview widget redistribution / Home default (`G6-P2`, `G6-P3`) | S007 |
| Structure polish / cleanup / validation tooling | S008 |
| Backend APIs, persistence, schema, Alembic | Forbidden |
| Deploy / provenance / verify-release / smoke architecture | Frozen by accepted remediation |
| Bundling S005+ into S004 | Explicitly forbidden |

### Future steps (not part of S004)

- S005: Home shell + Ask coexistence shell
- S006: Engineering isolation (includes `G7-P5` Advanced/Build move) + Ask progressive disclosure / history handoff
- S007: Home default + Overview retirement
- S008: cleanup, validation, tooling, remaining product evidence hygiene

---

## 3. Package IDs

| Identifier | Purpose | User-visible result | Dependencies | Completion criteria |
|------------|---------|---------------------|--------------|---------------------|
| `G7-P1` | General finishes beyond toggle host | `/settings/general` owns language + Engineering Mode toggle per contract | Soft: G2-P1 (already done) | General owns only its jobs; no retrieval/flags leak in |
| `G7-P2` | Models owns model selection | Users select/pull LLM and embedding models under `/settings/models` | Hard: S001 Settings routes | Models is the sole owner; no Home model lab |
| `G7-P3` | Answers owns four modes only | Users pick automatic/fast/balanced/high-precision answer quality under `/settings/answers` plus minimal answer-facing toggles | Hard: S001 Settings routes. Soft: G7-P5 for full knob removal timing | No retrieval engine panel, no chunk/temperature/boost controls in Answers |
| `G7-P4` | Access owns user management | Users manage accounts/roles under `/settings/access`; `/users` no longer a top-level owner | Hard: S001 Settings routes | Access is sole owner; no top-level Users |
| `G1-P2` (S004 slice) | Redirect increment for retired `/users` path | Legacy `/users` bookmarks keep working while `/settings/access` becomes authoritative | Hard: `G7-P4` | `/users` → `/settings/access` resolves via redirect without duplicate ownership |
| `G8-P2` (S004 slice) | Migrate touched Settings product code into RFC-102 target structure | New/updated Settings screens live in `features/settings/*`, thin pages, layout | Standing authority: RFC-102 | All new/migrated S004 owners land in RFC-102-compliant locations |

---

## 4. Architecture impact

### Allowed layers to change

| Layer / concern | Allowed S004 impact |
|-----------------|---------------------|
| Routing | Canonical Settings children routes remain authoritative; legacy `/users` entrypoint becomes a redirect |
| Navigation | Sidebar / section navigation labels, ordering, and destinations for Settings only |
| React components | Settings screens, Settings widgets, thin route adapters, Settings layout |
| Page ownership | Transfer Users product ownership to Access |
| Placeholders | Replace S001 scaffold placeholders for Models / Answers / Access |
| Settings screens | General / Models / Answers / Access product screens and their feature-local widgets |
| Legacy Users entrypoint | Compat redirect and owner cutover only |
| Tests | Ownership, redirect, nav, permission, no-legacy-import contracts |
| Documentation | This package, S004 evidence artifacts, review records directly tied to S004 |

### Forbidden areas

- Deployment scripts and deploy workflow
- Backend APIs, schema, Alembic, DB data model
- Release metadata, `APP_RELEASE`, lifecycle semantics
- RFC-100, Step 067, remediation law, or accepted evidence
- Knowledge owners completed in S002 and Insights owners completed in S003
- `SettingsAdvancedSection` / `RetrievalEnginePanel` / `MigrationFlagsPanel` content moving into product Models/Answers/Access (these remain out of product Settings until/unless `G7-P5` in S006 relocates them to Engineering)
- Starting S005+ or bundling those packages into S004

### Architectural invariants

1. RFC-101 defines product ownership; S004 implements it, does not reinterpret it.
2. RFC-102 defines structure; migrated Settings owners must land in target feature/layout/page layers.
3. Legacy and final may coexist only as **redirect + final owner**, not as dual product owners.
4. Engineering Mode isolates complexity; S004 must not leak engineering surfaces (advanced knobs, flag catalogs) into default product Settings.
5. S002/S003 ownership remains unchanged; S004 must not regress it.

---

## 5. Expected production files

Paths are expected from baseline `9a7134c` plus RFC-102 Settings targets. Final filenames may vary slightly but must remain inside these boundaries.

### Required

- `dashboard/src/features/settings/general/GeneralScreen.tsx`
- `dashboard/src/features/settings/models/ModelsScreen.tsx`
- `dashboard/src/features/settings/models/widgets/*`
- `dashboard/src/features/settings/answers/AnswersScreen.tsx`
- `dashboard/src/features/settings/access/AccessScreen.tsx`
- `dashboard/src/layouts/SettingsLayout.tsx`
- `dashboard/src/pages/UsersPage.tsx` → redirect wrapper only
- `dashboard/src/components/LanguageSwitcher.tsx` (additive `onChange` hook for General persistence only)
- Settings-related tests under `dashboard/src/**/*test.ts*`
- S004 evidence / gate docs under `docs/releases/`

### Optional

- `dashboard/src/shared/ui/*` if Settings product screens need already-authorized primitive reuse
- `dashboard/src/pages/SettingsPage.tsx` as a redirect wrapper, only if something still links it (baseline shows it is unrouted; left untouched in this package to avoid reopening frozen Step 065 / S001 contract tests that assert its legacy content)

### Forbidden

- `deploy/**`
- `backend/**`
- `alembic/**`
- `APP_RELEASE` / release lifecycle metadata mutation
- `docs/releases/S001-*remediation*`
- `docs/releases/S002-*`, `docs/releases/S003-*` (except read-only reference)
- Frozen RFCs / roadmap rewrite (`docs/RFC-101-*`, `docs/RFC-102-*`, `docs/releases/1.0-rfc-101-execution-roadmap.md`)
- Any S005/S006/S007/S008 implementation artifacts
- Knowledge/Insights product ownership redesign under `features/knowledge/**`, `features/insights/**`

---

## 6. Component ownership

### General (`G7-P1`)

| Field | Content |
|-------|---------|
| Current behavior | S001 provides `/settings/general` hosting language switcher (UI-local only) + Engineering Mode toggle |
| Target behavior | General additionally persists `dashboard_language` server-side on change, completing J8a beyond a bare toggle host |
| Migration strategy | Add an optional `onChange` hook to the shared `LanguageSwitcher` and wire General to call `updateSettings({ dashboard_language })`; Mode toggle unchanged |
| Rollback impact | Revert S004 commit(s); runtime returns to accepted `9a7134c` baseline |
| Acceptance criteria | General owns only language + Mode; no retrieval/flags leak in |

### Models (`G7-P2`)

| Field | Content |
|-------|---------|
| Current behavior | S001 provides canonical `/settings/models` substrate (placeholder); legacy `SettingsPage` (unrouted) still contains model selection UI |
| Target behavior | Models is the sole product owner for chat/embedding model selection and Ollama pull/install |
| Migration strategy | Copy `OllamaModelsPanel` into `features/settings/models/widgets/` with fixed relative imports; compose with llm/embedding Select+Input fields and a Save action |
| Acceptance criteria | Models reachable via canonical nav/route; no `SettingsAdvancedSection`/`RetrievalEnginePanel` present |

### Answers (`G7-P3`)

| Field | Content |
|-------|---------|
| Current behavior | S001 provides canonical `/settings/answers` substrate (placeholder); legacy `SettingsPage` (unrouted) contains agent presets + toggles |
| Target behavior | Answers owns the four agent presets (automatic/fast/balanced/high_precision), smart search, fallback answer, source/link toggle, chat-log toggle, and default response language |
| Migration strategy | Reuse `lib/settingsPresets` helpers (already outside `components/settings`); compose Answers screen with preset cards + toggles; clear retrieval cache on save when retrieval-affecting fields changed (parity with legacy save behavior) |
| Acceptance criteria | No retrieval engine panel, no chunk/temperature/boost controls in Answers |

### Access (`G7-P4`)

| Field | Content |
|-------|---------|
| Current behavior | S001 provides canonical `/settings/access` substrate (placeholder); `UsersPage` still owns user management at top-level `/users` |
| Target behavior | Access is the sole product owner for user management under Settings |
| Migration strategy | Move `UsersPage` body into `features/settings/access/AccessScreen.tsx` with fixed relative imports; convert `pages/UsersPage.tsx` to a redirect wrapper |
| Acceptance criteria | Access owns user management; `/users` is redirect-only; no top-level Users |

### Settings section shell (`G8-P2` slice)

| Field | Content |
|-------|---------|
| Current behavior | `SettingsLayout` is a passthrough `<Outlet />` without section navigation |
| Target behavior | Settings layout provides General / Models / Answers / Access section navigation only |
| Migration strategy | Mirror the `KnowledgeLayout`/`InsightsLayout` pattern used in S002/S003: in-section `NavLink`s to canonical Settings owners |
| Acceptance criteria | No extra top-level Settings children; section nav is the in-Settings owner switcher |

---

## 7. Routing plan

### Canonical owners (authoritative)

| Route | Owner module |
|-------|--------------|
| `/settings/general` | `features/settings/general/GeneralScreen` |
| `/settings/models` | `features/settings/models/ModelsScreen` (+ widgets) |
| `/settings/answers` | `features/settings/answers/AnswersScreen` |
| `/settings/access` | `features/settings/access/AccessScreen` |
| `/settings` index | Navigate to `general` (existing S001 default) — must not invent a fifth Settings child |

### Legacy compatibility (redirects only)

| Legacy route | Destination |
|--------------|-------------|
| `/users` | `/settings/access` |

### Requirements

- Legacy `/users` page is a redirect wrapper only
- No duplicate ownership
- No routing regressions for Knowledge, Insights, Ask, Engineering, Home
- `pages/SettingsPage.tsx` remains unrouted (baseline state); left untouched because Step 065 / S001 frozen tests assert its legacy content and nothing in the live app links to it

---

## 8. Navigation plan

### Product sidebar (`navConfig`)

Settings children must remain (already correct on baseline):

- General → `/settings/general`
- Models → `/settings/models`
- Answers → `/settings/answers`
- Access → `/settings/access`

No top-level product-nav entry for `/users`.

### Settings section navigation (`SettingsLayout`)

- General
- Models
- Answers
- Access

are the **only** Settings navigation owners inside the section shell.

### Explicit non-owners in S004 nav

- No top-level Users product entry
- No new Settings children beyond General / Models / Answers / Access
- Engineering Mode navigation unchanged
- Knowledge / Insights navigation unchanged (S002 / S003)

---

## 9. State management plan

- Keep existing client-local state patterns used by the legacy Settings/Users UI (React state / existing hooks)
- Do not introduce a new global Settings store, context architecture, or state library
- Do not invent new backend caching contracts
- Feature-local state lives with General / Models / Answers / Access owners
- Reuse `lib/settingsPresets` as the shared preset/smart-search logic (already outside `components/settings`)

---

## 10. UI/UX plan

- Replace S001 `MigrationPlaceholder` on Models, Answers, and Access with real product screens
- Preserve existing model-selection, agent-preset, and user-management UX capabilities that are product-facing
- Do not carry over `SettingsAdvancedSection`, `RetrievalEnginePanel`, or `MigrationFlagsPanel` into product Models/Answers/Access
- Loading, empty, and error states must exist for all four owners
- Do not redesign the whole design system; reuse existing `ui` primitives and established patterns from migrated screens (S002/S003 precedent)

---

## 11. Settings layout plan (`G8-P2` slice)

- Implement section navigation in `SettingsLayout` analogous to S002 `KnowledgeLayout` / S003 `InsightsLayout`
- Labels from i18n (`nav.general`, `nav.models`, `nav.answers`, `nav.access`, `nav.settings`)
- Active-state styling consistent with existing design tokens
- Outlet renders the active Settings owner only
- No fifth Settings child in S004

---

## 12. Models migration plan (`G7-P2`)

1. Inventory `SettingsPage` and `components/settings/OllamaModelsPanel.tsx` product widgets used for model selection.
2. Copy `OllamaModelsPanel` into `features/settings/models/widgets/OllamaModelsPanel.tsx` with imports fixed to the new depth (`../../../../`).
3. Compose Models screen with llm/embedding model fields + `OllamaModelsPanel` + Save.
4. Ensure active Models imports do **not** permanently depend on `components/settings/**` after cutover.
5. Do **not** include `SettingsAdvancedSection` or `RetrievalEnginePanel` knobs.

---

## 13. Answers migration plan (`G7-P3`)

1. Inventory `SettingsPage` agent-preset and toggle sections.
2. Migrate product composition into `features/settings/answers/AnswersScreen.tsx`, reusing `lib/settingsPresets` (already a shared, non-`components/settings` module).
3. Include: four agent presets, smart search toggle, fallback answer, `enable_sources`/`enable_source_links` toggle, `enable_chat_logs` toggle, `default_response_language`.
4. Exclude: retrieval engine panel, chunk/temperature/boost/advanced knobs, retrieval debug toggle.
5. Preserve retrieval-cache-refresh-on-save parity for retrieval-affecting preset fields.

---

## 14. Access migration plan (`G7-P4`, `G1-P2` slice)

1. Inventory `UsersPage` product widgets and API calls.
2. Migrate product composition into `features/settings/access/AccessScreen.tsx` with imports fixed to the new depth (`../../../`).
3. Convert `pages/UsersPage.tsx` to a redirect wrapper → `/settings/access` (preserve search/hash), matching the S002/S003 redirect pattern.
4. Ensure active Access imports do not permanently depend on `pages/UsersPage`.

---

## 15. Redirect strategy (`G1-P2` S004 slice)

| From | To | Mechanism |
|------|----|-----------|
| `/users` | `/settings/access` | Client `Navigate` wrapper (preserve search/hash), same pattern as S002/S003 |

Rules:

- Redirect wrapper only — no residual product UI
- Preserve query string and hash where practical
- No server nginx redirect redesign required
- Permissions must allow both legacy and canonical paths during compatibility, or map cleanly so authorized users are not locked out

---

## 16. Permissions

- Keep Settings canonical routes authorized for `admin` only (baseline already correct in `lib/permissions.ts`)
- Ensure legacy `/users` remains reachable for redirect compatibility for `admin`, or redirect before permission denial — do not strand bookmarks
- Do not invent new role models or permission systems
- Do not change Engineering Mode permission architecture

---

## 17. Shared component policy

Acceptable:

- Generic `ui` primitives
- `lib/settingsPresets` (already shared, non-`components/settings`)
- Feature-local widgets under `features/settings/*/widgets/**`

Rejected as permanent S004 ownership:

- Active Models/Answers/Access screens importing business widgets from `components/settings/**` after cutover
- Growing `pages/UsersPage.tsx` as a product owner
- Advanced/flag-catalog content inside product Models/Answers/Access
- New cross-program shared "god" modules

Legacy `components/settings/**` (`SettingsAdvancedSection`, `RetrievalEnginePanel`, `LlmRuntimePanel`, `MigrationFlagsPanel`, `SettingsHelpAccordion`) remain on disk temporarily; only `OllamaModelsPanel` is copied forward into a feature-local widget. The rest are Engineering-destined (`G7-P5`, S006) or already product-unmounted (`MigrationFlagsPanel`, frozen by Step 065).

---

## 18. Backend boundary

S004 must not change:

- `backend/**`
- `alembic/**`
- API contracts, auth/session, `APP_RELEASE`, release_status fields
- Database schema or migrations
- Deploy / provenance / identity / verify-release / smoke tooling

S004 may continue calling existing settings/users APIs already used by `SettingsPage`/`UsersPage`. New backend endpoints are out of scope.

Expected migration strategy on deploy: `post_sync_only`
Expected Alembic head unchanged from S003 baseline.

---

## 19. Testing strategy

Minimum required coverage (follow S002/S003 cutover test precedent):

- Canonical Settings routes registered
- Legacy `/users` is a redirect wrapper only
- Product nav contains General/Models/Answers/Access only under Settings
- `SettingsLayout` section nav contains only General/Models/Answers/Access
- Placeholders removed from Models/Answers/Access owners
- Owner modules live under `features/settings/**` and do not import legacy `components/settings/**` or `pages/UsersPage`
- Access route permissions enforced (`admin` only)
- No Knowledge/Insights ownership regressions (smoke assertion or explicit non-touch proof)

Validation commands (pre-commit / pre-deploy as applicable):

- `cd dashboard && npm test`
- `cd dashboard && npx tsc --noEmit`

No headed-browser requirement beyond existing project tooling.

---

## 20. Documentation requirements

Create/maintain only S004 evidence artifacts under `docs/releases/` as needed by the review chain:

- `S004-implementation-package.md` (this file — frozen contract)
- `S004-implementation-evidence.md`
- `S004-product-readiness-gate.md`
- `S004-acceptance-evidence.md`

Do not rewrite S001/S002/S003 remediation docs, RFC-100/101/102, or the execution roadmap.

---

## 21. Previous-step protection

S004 **must not modify** or reopen:

- Phase 1 (publication/provenance remediation)
- Phase 2 (verify-release / smoke / temps / backend FE identity preserve)
- Full Remediation
- S001 (product scaffold / Engineering Mode substrate)
- S002 (Knowledge ownership cutover — Library / Update / Site)
- S003 (Insights ownership cutover — Performance / Activity)
- RFC-100
- Step 067
- Deployment architecture, provenance, identity, verify-release, smoke, backend, schema, release workflow

S004 consumes these as frozen baselines.

---

## 22. Risks

| Risk | Rating | Mitigation |
|------|--------|------------|
| Dual ownership if Users page retains UI | controlled | Redirect wrapper only; ownership tests |
| Incomplete widget migration / import from `components/settings/**` | controlled | RFC-102 ownership review + import contracts (no `components/settings` imports in owner screens) |
| Accidental Engineering-knob leakage into Answers/Models | controlled | Explicit non-goals; test asserts absence of `SettingsAdvancedSection`/`RetrievalEnginePanel`/`MigrationFlagsPanel` |
| Reopening frozen Step 065 / S001 `SettingsPage` contract tests | controlled | `pages/SettingsPage.tsx` left untouched (unrouted, dead code; optional step not exercised) |
| Accidental Knowledge/Insights changes | controlled | Explicit non-goals; review against this package |
| Deploy architecture touch | controlled | Forbidden path list |

Uncontrolled redesign of deploy/backend is **not authorized**.

---

## 23. Acceptance criteria

S004 is complete only when all are true:

1. `/settings/general` finishes General beyond a bare toggle host (language persistence + Mode toggle).
2. `/settings/models` is the sole product Models owner (selection + pull/install), no advanced knobs.
3. `/settings/answers` is the sole product Answers owner (four modes + minimal answer toggles), no retrieval engine panel.
4. `/settings/access` is the sole product Access owner (user management); `/users` is a compatibility redirect only.
5. `SettingsLayout` provides General/Models/Answers/Access section navigation only.
6. S001 placeholders are removed from Models, Answers, and Access.
7. Active ownership lives under `features/settings/{general,models,answers,access}/**`.
8. No permanent new product logic remains in `pages/UsersPage.tsx`.
9. Product nav has no top-level Users owner.
10. Knowledge (S002) and Insights (S003) owners remain unchanged as product owners.
11. No backend/deploy/provenance/identity/verify-release/smoke/schema/release-metadata changes.
12. Tests and TypeScript pass for the Settings cutover contracts.

---

## 24. Deliverables

- General product owner finishing J8a under `/settings/general`
- Models product owner under `/settings/models`
- Answers product owner under `/settings/answers`
- Access product owner under `/settings/access`
- Settings section layout with General/Models/Answers/Access nav
- `/users` → `/settings/access` redirect
- RFC-102 Settings feature modules + tests + S004 evidence docs

---

## 25. Explicit non-goals

S004 will **not**:

- Implement `G7-P5` Advanced knobs/prompt → Eng Advanced; flag catalogs → Eng Build (S006)
- Implement S005 Home / Ask coexistence shell
- Implement S006 Engineering isolation or Ask progressive disclosure / history modal retirement
- Implement S007 Overview redistribution or Home-as-default
- Implement S008 cleanup/tooling program
- Modify Knowledge Library/Update/Site ownership completed in S002
- Modify Insights Performance/Activity ownership completed in S003
- Redesign deployment, publication, provenance, identity, verify-release, or smoke
- Change backend, database, Alembic, or release lifecycle metadata
- Reopen Phase 1, Phase 2, Full Remediation, S001, S002, S003, RFC-100, or Step 067
- Add new Settings top-level children beyond General / Models / Answers / Access
- Invent new admin retrieval-tuning controls or hardcoded business knowledge

---

## Implementation contract seal

This document is the **sole implementation contract** for S004.

Nothing outside this package may be implemented under the S004 label.

**S004 IMPLEMENTATION PACKAGE COMPLETE — READY FOR IMPLEMENTATION**
