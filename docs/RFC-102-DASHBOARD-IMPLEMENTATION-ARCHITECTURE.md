# RFC-102 — Dashboard Implementation Architecture (Engineering)

**Status:** Canonical **implementation architecture** for the Release 1.0 Dashboard  
**Authority:** Defines **HOW** the Dashboard is built  
**Product SoT:** `docs/RFC-101-DASHBOARD-PRODUCT-SPECIFICATION.md` (WHAT)  
**Constitution:** `ENGINEERING_MANIFEST.md`, `DEVELOPMENT_CHARTER.md`, `LIFECYCLE.md`, `RELEASE_ENGINEERING_WORKFLOW.md`, `RFC-100-PRODUCTION-MIGRATION-STRATEGY.md`, `RFC-PRODUCT-READINESS.md`  

| Document | Role |
|----------|------|
| **RFC-101** | Product architecture — IA, ownership, screen contracts, Gate criteria |
| **RFC-102** | Implementation architecture — folders, components, state, routing, tests |
| **RFC-100** | Engineering capabilities / migration steps (unchanged) |

**RFC-102 MUST NOT** redefine product IA, navigation, Screen Contracts, Product Readiness, RFC-100, or Release Engineering.  
If product intent conflicts with this doc, **RFC-101 wins**. If implementation structure conflicts with this doc, **RFC-102 wins**.

**Enforcement:** Dashboard PRs must satisfy RFC-101 **and** RFC-102. Product Readiness Gate checks product rules; reviewers also check RFC-102 structure (see §12).

**Baseline:** Current tree under `dashboard/src/` is legacy engineering-console layout. Release 1.0 work **migrates toward** the structure below; new screens **must** land in the target structure.

---

## 0. Architecture diagrams

### 0.1 Document relationship

```
RFC-100 (capabilities)
        │
        ▼
RFC-101 (product WHAT)  ←── Product Readiness Gate
        │
        ▼
RFC-102 (implementation HOW)  ←── this document
        │
        ▼
dashboard/src (code)
```

### 0.2 Runtime composition

```
main.tsx
  └─ Providers (Auth, I18n, Theme, Sidebar, QueryClient, ChatSession*)
       └─ App routes
            ├─ /login → features/auth
            └─ DashboardLayout (shell)
                 ├─ AppSidebar / AppTopBar   (layouts/)
                 └─ <Outlet>
                      └─ pages/*  (thin route adapters)
                           └─ features/<feature>/*  (screen + widgets)
                                └─ shared/ui  (design system)
```

\* ChatSession context scoped to Ask (+ Engineering Ask details), not app-wide forever if avoidable; see §5.

### 0.3 Feature composition (mandatory)

```
RFC-101 Screen
    → pages/<Screen>Page.tsx          (route only)
    → features/<feature>/Screen.tsx   (composition)
    → features/<feature>/widgets/*    (feature UI)
    → shared/ui/*                     (design system)
    → api / hooks                     (data)
```

**Forbidden:**

```
Feature → random pages/*.tsx monolith with one-off components
```

---

## 1. React architecture

### 1.1 Layers (top → bottom)

| Layer | Responsibility | May import |
|-------|----------------|------------|
| **app** | Bootstrap, providers, router | layouts, pages, context, api setup |
| **pages** | Thin route adapters (lazy). No business UI sprawl | features, layouts |
| **layouts** | Shell: sidebar, top bar, section sub-nav | shared/ui, auth, i18n |
| **features** | RFC-101 screen owners + widgets | shared/*, api, hooks, lib |
| **shared/ui** | Design system primitives | utils, theme only |
| **api** | HTTP client + resource functions | types |
| **hooks** | Reusable data/UI hooks | api, context |
| **context** | Cross-cutting providers | api, types |
| **lib** | Pure helpers (no React) | types |
| **types** | Shared TS types | — |
| **i18n** | Dictionaries + provider | — |

### 1.2 Feature boundaries (RFC-101 aligned)

| Feature module | Owns RFC-101 screens |
|----------------|----------------------|
| `features/auth` | Sign in |
| `features/home` | Home |
| `features/knowledge/library` | Library |
| `features/knowledge/update` | Update |
| `features/knowledge/site` | Site |
| `features/ask` | Ask (product) |
| `features/insights/performance` | Performance |
| `features/insights/activity` | Activity |
| `features/settings/general` | General |
| `features/settings/models` | Models |
| `features/settings/answers` | Answers |
| `features/settings/access` | Access |
| `features/engineering/*` | Engineering Mode screens |

**Rule:** Feature A must not import Feature B’s **widgets** or **Screen**. Shared needs go to `shared/` or `hooks/` / `api/`. Cross-feature navigation = `react-router` links only (RFC-101 deep-link policy).

### 1.3 App shell

- `DashboardLayout` renders shell + `<Outlet />`.  
- Product nav config is **data** derived from RFC-101 route table (single `navConfig.ts`).  
- Engineering nav items appended only when Engineering Mode preference is on.  
- Section layouts (`KnowledgeLayout`, `InsightsLayout`, `SettingsLayout`, `EngineeringLayout`) own **sub-nav only**.

---

## 2. Folder structure (canonical)

Target under `dashboard/src/`:

```
src/
  app/                    # optional: App.tsx, providers.tsx, router.tsx
  pages/                  # thin lazy route entries only
  layouts/                # DashboardLayout, section layouts, nav
  features/
    auth/
    home/
    knowledge/
      library/
      update/
      site/
      shared/             # knowledge-only shared (NOT design system)
    ask/
    insights/
      performance/
      activity/
      shared/
    settings/
      general/
      models/
      answers/
      access/
      shared/
    engineering/
      status/
      ask-details/
      knowledge/
      tensions/
      advanced/
      build/
      shared/
  shared/
    ui/                   # design system (migrate from src/ui)
    components/           # rare cross-feature composites (prefer avoid)
  api/                    # axios client + resource modules
  hooks/
  context/
  lib/
  types/
  i18n/
  test/                   # test utils / MSW if introduced
```

### 2.1 Directory ownership

| Directory | Owner | Allowed contents | Forbidden |
|-----------|-------|------------------|-----------|
| `pages/` | Router | `*Page.tsx` that re-export/compose feature Screen | Tables, forms, fetch logic |
| `layouts/` | Shell | Layouts, `navConfig`, sidebar/topbar | Feature business widgets |
| `features/<x>/` | Feature team/owner screen | `Screen.tsx`, `widgets/`, `hooks/`, `api.ts` (feature-local), tests | Another feature’s screens |
| `features/*/shared/` | That section only | Helpers used by ≥2 siblings in section | App-wide UI kit |
| `shared/ui/` | Design system | Primitives: Button, Modal, Drawer, Table, States… | Feature domain copy/logic |
| `api/` | Data layer | `client.ts`, `resources/*.ts` | JSX |
| `hooks/` | Shared hooks | `useX` used by ≥2 features | One-off screen hooks (keep in feature) |
| `context/` | Cross-cutting | Auth, I18n, Theme, Sidebar, EngineeringMode, QueryClient | Feature server caches |
| `lib/` | Pure utils | Parsers, formatters | React components |
| `types/` | Shared types | DTOs, roles | — |
| `i18n/` | Localization | `en.ts`, `uk.ts`, keys matching RFC-101 glossary |

### 2.2 Migration from legacy tree

| Legacy | Target |
|--------|--------|
| `pages/OverviewPage.tsx` | `features/home` + `pages/HomePage.tsx` |
| `pages/IndexingPage.tsx` | `features/knowledge/update` |
| `pages/SourcesPage.tsx` | `features/knowledge/library` |
| `pages/KnowledgeProfilePage.tsx` | `features/knowledge/site` |
| `pages/ChatTestPage.tsx` | `features/ask` (+ eng details split) |
| `pages/AnalyticsPage.tsx` | `features/insights/performance` |
| `pages/LogsPage.tsx` | `features/insights/activity` |
| `pages/SettingsPage.tsx` | split into settings/* screens |
| `pages/UsersPage.tsx` | `features/settings/access` |
| `pages/EpistemicHealthPage.tsx` | `features/engineering/tensions` |
| `components/chat/*` diagnostics | `features/engineering/ask-details` and/or `features/ask` progressive disclosure |
| `components/overview/*` | mostly delete or home-only widgets per RFC-101 |
| `src/ui/*` | `shared/ui/*` |

Legacy paths may remain temporarily behind redirects (RFC-101 §12) until migrated; **new code must not grow legacy folders**.

---

## 3. Screen implementation contract

For every RFC-101 screen, implementation **must** include:

| Artifact | Location | Responsibility |
|----------|----------|----------------|
| Route entry | `pages/<Name>Page.tsx` | Lazy boundary; render feature Screen; no logic |
| Section layout (if any) | `layouts/<Section>Layout.tsx` | Sub-nav per RFC-101 |
| Screen container | `features/.../Screen.tsx` | Compose widgets; wire hooks; CTAs |
| Feature widgets | `features/.../widgets/*` | Domain UI for this owner only |
| Shared widgets | `shared/ui/*` | Primitives only |
| Data ownership | `api/resources/*` + feature hooks | Server reads/writes |
| Routing ownership | `app/router` + RFC-101 routes | Paths/redirects |

### 3.1 Per-screen mapping (RFC-101 → modules)

| RFC-101 screen | Page | Feature Screen | Layout |
|----------------|------|----------------|--------|
| Sign in | `pages/LoginPage.tsx` | `features/auth/Screen.tsx` | none |
| Home | `pages/HomePage.tsx` | `features/home/Screen.tsx` | DashboardLayout |
| Library | `pages/knowledge/LibraryPage.tsx` | `features/knowledge/library/Screen.tsx` | KnowledgeLayout |
| Update | `pages/knowledge/UpdatePage.tsx` | `features/knowledge/update/Screen.tsx` | KnowledgeLayout |
| Site | `pages/knowledge/SitePage.tsx` | `features/knowledge/site/Screen.tsx` | KnowledgeLayout |
| Ask | `pages/AskPage.tsx` | `features/ask/Screen.tsx` | DashboardLayout |
| Performance | `pages/insights/PerformancePage.tsx` | `features/insights/performance/Screen.tsx` | InsightsLayout |
| Activity | `pages/insights/ActivityPage.tsx` | `features/insights/activity/Screen.tsx` | InsightsLayout |
| General | `pages/settings/GeneralPage.tsx` | `features/settings/general/Screen.tsx` | SettingsLayout |
| Models | `pages/settings/ModelsPage.tsx` | `features/settings/models/Screen.tsx` | SettingsLayout |
| Answers | `pages/settings/AnswersPage.tsx` | `features/settings/answers/Screen.tsx` | SettingsLayout |
| Access | `pages/settings/AccessPage.tsx` | `features/settings/access/Screen.tsx` | SettingsLayout |
| Eng * | `pages/engineering/*Page.tsx` | `features/engineering/*/Screen.tsx` | EngineeringLayout |

Two engineers implementing the same row must produce the **same module boundaries**.

### 3.2 Screen.tsx obligations

Each `Screen.tsx` must:

1. Implement RFC-101 Screen Contract (CTA, empty/loading/error).  
2. Use `shared/ui` for Button/Modal/Drawer/Table/States.  
3. Own only that screen’s job (RFC-101 Forbidden list).  
4. Export a single default or named `Screen`.  
5. Colocate feature tests under `features/.../__tests__` or `*.test.tsx`.

---

## 4. Component ownership

| Kind | Location | Examples | Rules |
|------|----------|----------|-------|
| **Shared UI (Design System)** | `shared/ui` | Button, Modal, Drawer, DataTable, Pagination, PageHeader, Empty/Loading/Error, Input, Select, Tabs | No domain strings hard-coded for one feature; i18n passed in |
| **Feature UI** | `features/<f>/widgets` | `LibraryTable`, `UpdateProgress`, `AskComposer` | Used only inside owning feature (or section `shared/`) |
| **Screen UI** | `features/<f>/Screen.tsx` | Composition only | No copy-paste of another Screen |
| **Layout UI** | `layouts/` | Sidebar, SectionSubNav | Nav labels from i18n + navConfig |
| **Engineering Mode UI** | `features/engineering/**` | Traces, flag matrix, tensions | Never imported by product features except via route |

### 4.1 Duplication ban

| Symptom | Action |
|---------|--------|
| Two tables with different chrome | Use `shared/ui` DataTable |
| Two SourceIntelligence panels | One eng widget; product Library detail uses human summary only |
| MetricCard in overview + analytics + ui | One `shared/ui` Metric/Stat |
| Page-local Button CSS | Forbidden |

---

## 5. State ownership

| State kind | Owner | Examples | Forbidden |
|------------|-------|----------|-----------|
| **Server/async cache** | React Query (preferred for new fetches) via `hooks/` + `api/` | lists, settings GET, build info | Ad-hoc duplicate `useEffect` fetch of same resource in two features without shared hook |
| **Session / auth** | `context/AuthContext` | token, role | Storing auth in feature localStorage ad-hoc |
| **I18n / theme / sidebar** | respective contexts | locale, theme, collapsed | — |
| **Engineering Mode flag** | `context/EngineeringModeContext` (or settings-backed hook owned by General) | boolean | Second toggle state elsewhere |
| **Ask thread UI** | `features/ask` local state + optional ChatSession context scoped to Ask routes | messages, streaming | Global app chat state for Insights |
| **URL state** | React Router search params | `?q=`, `?bucket=`, pagination, session id | Parallel React state that drifts from URL for shareable filters |
| **Forms** | Local state or react-hook-form **inside owner screen** | Site form, Answers mode | Two screens writing same settings keys without shared mutation hook |
| **Derived state** | `useMemo` / query `select` next to owner | readiness enum on Home | Duplicating readiness computation in Library |
| **Ephemeral UI** | Local `useState` | drawer open, row selection | Context for one checkbox |

### 5.1 React Query rules

- One `QueryClientProvider` at app root.  
- Query keys: domain-oriented (`['sources', filters]`, `['settings']`, `['indexing','status']`) — document in `api/queryKeys.ts`.  
- Mutations invalidate the **owner** queries only.  
- Library “Refresh selected” mutation must invalidate Update/Home status queries (same job pipeline), not invent a second job cache.

### 5.2 Legacy note

Today much data uses manual axios + `useEffect`. New RFC-101 screens should use React Query (or a single shared `useResource` pattern). Migrating old pages is encouraged when touching them; do not add new `useEffect` fetch sprawl.

---

## 6. Routing architecture

### 6.1 Hierarchy

```
/login
/* (auth)
  DashboardLayout
    /home
    /knowledge  → KnowledgeLayout
      library | update | site
    /ask
    /insights → InsightsLayout
      performance | activity
    /settings → SettingsLayout
      general | models | answers | access
    /engineering → EngineeringLayout   (Mode on only)
      status | ask-details | knowledge | tensions | advanced | build
```

### 6.2 Redirects (implement RFC-101 §12)

Centralize in `layouts/redirects.ts` or router module — **one table**, no scattered `<Navigate>` inventions.

Examples: `/` → `/home`; `/chat` → `/ask`; `/indexing` → `/knowledge/update`; `/sources` → `/knowledge/library`; `/diagnostics/epistemic-health` → `/engineering/tensions`; etc.

### 6.3 Engineering Mode routing

- Routes registered always **or** conditionally; if always registered, `EngineeringLayout` redirects to `/home` when Mode off.  
- Prefer **guard**: `RequireEngineeringMode` wrapper.  
- Product nav must not link to eng routes when Mode off.

### 6.4 Lazy loading

- Every `pages/*Page` is `React.lazy`.  
- Section layouts may be eager (small).  
- `shared/ui` not lazy per-component.  
- Engineering feature chunk separate so Mode-off users need not download eng widgets initially (optional optimization: lazy eng routes).

### 6.5 Role guards

Reuse `RequireAuth` with RFC-101 role matrix (`permissions` aligned to RFC-101 §2.1). Single permissions module — do not hardcode roles inside feature widgets.

---

## 7. Dashboard composition rules

### 7.1 Adding functionality (only path)

1. Confirm RFC-101 owner screen / feature row.  
2. Add or extend `features/<owner>/…`.  
3. Use `shared/ui` primitives.  
4. Add API in `api/resources` + hook.  
5. Wire route only if RFC-101 already lists it (else update RFC-101 first).  
6. Tests + Gate checklist.

### 7.2 Forbidden composition

- New top-level `components/foo` for a one-off screen control that belongs in a feature.  
- Growing `pages/XPage.tsx` past ~80 lines of JSX.  
- Importing `features/engineering/*` from product features.  
- Copying widgets across features instead of promoting to `shared/ui` or section `shared/`.

---

## 8. Design System implementation

RFC-101 §14 = visual/product rules. This section = engineering ownership.

| Concern | Implementation owner | Notes |
|---------|---------------------|-------|
| Button | `shared/ui/Button` | Variants: primary/secondary/tertiary/destructive |
| Modal | `shared/ui/Modal` | Confirms only (RFC-101) |
| Drawer | `shared/ui/Drawer` | Library detail |
| Table | `shared/ui/DataTable` | Library, Activity, Access |
| Forms | `shared/ui` inputs + feature form layout | Save explicit |
| Loading | `shared/ui/LoadingState` + skeletons | |
| Error / Empty | `shared/ui/States` | Message + one CTA |
| Typography / spacing | `shared/ui` CSS tokens / foundations | No page-local type scales |
| Charts | Insights-only wrapper over shared chart helper | Not on Home |

**Token source:** existing `ui/styles/foundations.css` migrates to `shared/ui/styles`. New colors/spacing only via tokens.

---

## 9. Engineering Mode implementation

| Topic | Rule |
|-------|------|
| Preference storage | Owned by Settings → General; exposed via `useEngineeringMode()` |
| Nav | `navConfig` appends Engineering section when on |
| Isolation | All eng widgets under `features/engineering/**` |
| Ask details | Product Ask may render a slot: if Mode on, lazy-load `engineering/ask-details` panel; **no** duplicate product diagnostics sidebar |
| State | Eng queries use separate query key prefix `['eng', …]` |
| Duplication | Do not reimplement Library/Update in eng; link to product routes |

---

## 10. Testing architecture

| Layer | Where | What |
|-------|-------|------|
| Unit | `lib/*.test.ts`, feature pure helpers | Parsers, readiness derivation, permissions |
| Component | `features/**/*.test.tsx`, `shared/ui/**/*.test.tsx` | Widgets render + interactions |
| Screen/integration | Feature Screen tests with mocked API | Empty/loading/error/CTA per RFC-101 contract |
| Navigation | Router tests | Redirects, Mode off blocks eng, role guards |
| Product Readiness / regression | Checklist-driven tests optional; forbid dual nav labels via navConfig snapshot test | `navConfig` matches RFC-101 routes |
| Vitest | Existing dashboard vitest | Keep green in `release-check` |

**Rule:** New screen ⇒ at least one test for primary CTA + empty or loading state.

---

## 11. Dashboard implementation workflow

```
Design / product intent (RFC-101)
        ↓
RFC-101 compliance check (owner, route, contract)
        ↓
RFC-102 architecture (feature folder, state, ui kit)
        ↓
Implementation
        ↓
Tests
        ↓
Product Readiness Gate (+ rfc101_compliance)
        ↓
RFC-102 PR checklist
        ↓
Acceptance / merge
```

Does **not** delay RFC-100 Step 063 start. Backend steps may proceed with Gate `N/A` when no Dashboard diff.

---

## 12. PR Checklist (RFC-102)

In addition to RFC-101 §29:

- [ ] Change lives under correct `features/<owner>/` (or shared/ui / api)  
- [ ] `pages/*` remains thin  
- [ ] No import from another feature’s widgets  
- [ ] No new duplicate shared widget (checked against `shared/ui`)  
- [ ] State owned per §5 (URL vs Query vs context vs local)  
- [ ] Routes/redirects only via central router + RFC-101 table  
- [ ] Design system components used for Button/Modal/Drawer/Table/States  
- [ ] Engineering UI isolated under `features/engineering` if eng  
- [ ] Tests added/updated  
- [ ] Product Readiness Gate record attached for user-facing changes  

---

## 13. Anti-patterns (implementation FAIL)

1. Business UI in `pages/`  
2. Feature importing another feature’s internals  
3. Second design-system Button  
4. Parallel fetch hooks for the same query key without sharing  
5. Eng components shipped in product bundle path without Mode guard  
6. New route outside RFC-101 without product doc update  
7. “Temporary” folder `components/legacy-fix` grown with new features  

---

## 14. Out of scope

- Changing RFC-101 product decisions  
- Backend/API redesign  
- Deploy / Release Engineering  
- Pixel mock tooling  
- Mandating a rewrite of all legacy pages on day one (migrate on touch + for RFC-101 screens)

---

## 15. Document control

| Item | Value |
|------|--------|
| Path | `docs/RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md` |
| Complements | RFC-101 |
| Does not supersede | RFC-101, RFC-100, Product Readiness |
| Change process | Engineering review; must not silently alter product IA |

---

**End of RFC-102**

*RFC-101 decides the product. RFC-102 decides the boxes the code lives in. Neither invents the other.*
