# RFC-101 — Release 1.0 Dashboard Product Specification

**Status:** Canonical **single source of truth** for Dashboard product architecture  
**Authority:** Defines what the Release 1.0 Dashboard **is** and how every screen/feature must behave  
**Constitution:** `ENGINEERING_MANIFEST.md`, `DEVELOPMENT_CHARTER.md`, `LIFECYCLE.md`, `RELEASE_ENGINEERING_WORKFLOW.md`, `RFC-100-PRODUCTION-MIGRATION-STRATEGY.md`, `RFC-PRODUCT-READINESS.md`  
**Relationship:** Complements Product Readiness (program + Gate). Does **not** replace RFC-100. Does **not** redesign Knowledge OS, deployment, or Release Engineering.  
**Enforcement:** Product Readiness Gate **MUST** evaluate Dashboard changes against **this document**. Violations are automatic Gate **FAIL** (see §28 and `RFC-PRODUCT-READINESS.md` §6).

---

## 0. How to use this document

| Audience | Obligation |
|----------|------------|
| Implementer | Build **only** what this spec defines. Do not invent nav, ownership, or screen jobs. |
| Reviewer / Gate | Reject drift from Feature Ownership, Navigation Ownership, Screen Contracts, and anti-patterns. |
| Product Owner | Material IA changes require explicit acceptance; Gate alone cannot rewrite this spec. |

| Rule | Detail |
|------|--------|
| **Ignore** | Current navigation, current screen names, current layout |
| **Obey** | This document + Product Readiness principles |
| **RFC-100** | Steps 063–067 proceed unchanged; capabilities are **integrated into the product**, never removed or delayed by UX redesign |
| **Question** | Never “Should this capability exist?” → Always “**How** should it appear?” |
| **Build test** | Two independent engineers reading only this doc must produce nearly the same Dashboard |
| **Conflict** | If another doc describes Dashboard UX differently, **RFC-101 wins** for product UI. RFC-100 wins for engineering step scope. |

### 0.1 Review findings closed by this revision

| Gap in prior RFC-101 | Resolution in this revision |
|----------------------|-----------------------------|
| Ownership implied, not matrixed | §11 Feature Ownership Matrix — exactly one owner |
| Navigation non-deterministic | §12 Navigation Ownership Matrix + redirects |
| RFC-100 → UI mapping thin | §13 Product Capability Matrix |
| Design system too brief | §14 architectural UI rules |
| Screens lacked full contracts | §15 Screen Contracts |
| Cross-screen “one place” soft | §16 One-Place Register |
| Gate criteria subjective | §28 objective FAIL rules + §29 PR checklist |
| Setup / readiness states vague | §15 Home + §8 journeys + readiness model §10 |
| Library vs Update reindex ambiguity | Ownership: Update owns refresh semantics; Library may enqueue only |
| “Why this answer” vs Eng Mode | Progressive disclosure rules in Ask contract |
| Role × route matrix missing | §2.1 |
| Component ownership missing | §14.12 |

---

## 1. Product identity

### 1.1 What the product is

**AI Site Agent** helps an organization:

1. Connect a website as a knowledge source  
2. Keep that knowledge up to date  
3. Ask questions and get trustworthy answers grounded in that knowledge  
4. See whether the agent is healthy and useful  
5. Control access and basic preferences  

It is a **Knowledge Operating System for a website**, experienced as a simple operator console.

### 1.2 What the product is not

Not a chatbot playground, vector DB admin, feature-flag console, deploy console, or memory/tension research workbench (Engineering Mode). Not dual “Chat Test” / “Chat Diagnostics”.

### 1.3 Release 1.0 acceptance identity

```
RFC-100 Engineering complete (063–067)
        ∧
Product Readiness complete (this product shipped per RFC-101)
        =
Release 1.0 Accepted Product
```

Cold demo without coaching; no temporary / ignore / testing-only / engineers-only / don’t use yet / redesign later.

### 1.4 Integration rule

**Integrate engineering into product behavior. Never expose engineering concepts when product language is sufficient. Never delete RFC-100 capability to “simplify.”**

---

## 2. Users and roles

| Role | Product name | May |
|------|--------------|-----|
| **Owner** | Site owner / admin | All product screens; Access; Engineering Mode toggle |
| **Operator** | Knowledge operator | Home, Knowledge, Ask, Insights; not Access; not Settings Models/Answers unless granted (default: Operator may use Ask/Knowledge/Insights/Home; Owner-only: Settings Models/Answers/Access/Site edit — see §2.1) |
| **Viewer** | Observer | Home (read-only), Insights (read-only) |
| **Engineer** | Same login + Engineering Mode **on** | Engineering area |

Engineering Mode is **orthogonal to role** (default **off** even for Owner).

### 2.1 Role × route access (product)

| Route | Viewer | Operator | Owner |
|-------|--------|----------|-------|
| `/login` | ✓ | ✓ | ✓ |
| `/home` | ✓ read | ✓ | ✓ |
| `/knowledge/*` | ✗ | ✓ | ✓ |
| `/ask` | ✗ | ✓ | ✓ |
| `/insights/*` | ✓ read | ✓ | ✓ |
| `/settings/general` | ✗ | ✗ | ✓ |
| `/settings/models` | ✗ | ✗ | ✓ |
| `/settings/answers` | ✗ | ✗ | ✓ |
| `/settings/access` | ✗ | ✗ | ✓ |
| `/engineering/*` | ✗ | ✗ | ✓ if Mode on |

*(Operator Site edit: allowed — Site is under Knowledge; Operators maintain site URL/profile for the agent.)*

---

## 3. User jobs (source of truth)

| Job ID | User job | **Owner screen** |
|--------|----------|------------------|
| J1 | Know if ready + what next | **Home** |
| J2 | Connect / identify website | **Site** |
| J3 | Refresh knowledge | **Update** |
| J4 | Browse coverage / fix gaps | **Library** |
| J5 | Ask + get answer with sources | **Ask** |
| J6 | Usage & answer quality | **Performance** |
| J7 | Past questions / requests | **Activity** |
| J8a | Language / interface | **General** |
| J8b | Models | **Models** |
| J8c | Answer quality mode | **Answers** |
| J9 | Who can access Dashboard | **Access** |
| J10 | Engineering internals | **Engineering Mode** |

Secondary access may deep-link; **never** creates a second owner.

---

## 4. Final Information Architecture

```
PRODUCT (Engineering Mode OFF)
  Home
  Knowledge
    Library | Update | Site
  Ask
  Insights
    Performance | Activity
  Settings
    General | Models | Answers | Access

ENGINEERING MODE ON (additive)
  Engineering
    System status | Ask details | Knowledge internals
    Knowledge tensions | Advanced controls | Build & flags
```

**Top-level nav (Mode off):** exactly  
`Home` · `Knowledge` · `Ask` · `Insights` · `Settings`

**Forbidden top-level:** Indexing, Sources, Chat Test, Diagnostics, Epistemic, Logs, Analytics, Users, Knowledge Profile, Agent Settings, Overview.

---

## 5. Navigation hierarchy rules

1. Top-level = job families only.  
2. Knowledge / Insights / Settings use **in-section sub-nav only** (not extra top-level items).  
3. One label per route.  
4. Engineering appears **only** when Mode on.  
5. Authenticated default = `/home`.  
6. Incomplete setup → Home Setup checklist (§8.1), not a settings dump.

---

## 6. Canonical routes

| Screen | Canonical route | Default sub-route |
|--------|-----------------|-------------------|
| Sign in | `/login` | — |
| Home | `/home` | `/` → redirect `/home` |
| Library | `/knowledge/library` | `/knowledge` → `/knowledge/library` |
| Update | `/knowledge/update` | — |
| Site | `/knowledge/site` | — |
| Ask | `/ask` | — |
| Performance | `/insights/performance` | `/insights` → `/insights/performance` |
| Activity | `/insights/activity` | — |
| General | `/settings/general` | `/settings` → `/settings/general` |
| Models | `/settings/models` | — |
| Answers | `/settings/answers` | — |
| Access | `/settings/access` | — |
| Eng System | `/engineering/status` | `/engineering` → `/engineering/status` |
| Eng Ask details | `/engineering/ask-details` | — |
| Eng Knowledge internals | `/engineering/knowledge` | — |
| Eng Tensions | `/engineering/tensions` | — |
| Eng Advanced | `/engineering/advanced` | — |
| Eng Build & flags | `/engineering/build` | — |

---

## 7. Readiness model (Home)

Home computes a single product state:

| State | Meaning | Primary CTA |
|-------|---------|-------------|
| **Needs setup** | No site URL | Go to Site |
| **Needs update** | Site set, never successfully updated / empty library | Update knowledge |
| **Updating** | Refresh in progress | View progress (Update) |
| **Ready** | Site + knowledge present + agent usable | Ask a question |
| **Needs attention** | Ready but failures/stale signal | Review library / Update |

Home may show at most **one** primary CTA and **one** secondary CTA derived from this state. No chart wall.

---

## 8. Allowed user journeys

### 8.1 First-run

`Sign in → Home (Setup) → Site → Update → Ask`

### 8.2 Daily operator

`Home → Update (if needed) → Library (spot-check) → Ask`

### 8.3 Weak answer

`Performance or Ask → sources → Library item → Update if missing`

### 8.4 Owner weekly

`Home → Performance → Settings (Answers/Models) → Access`

### 8.5 Forbidden

Flag-first journeys; triple reindex paths; Chat Test vs Diagnostics; Epistemic as product health.

---

## 9. Engineering Mode

| Property | Rule |
|----------|------|
| Default | **Off** |
| Toggle location | **Settings → General** (single owner for the preference) |
| Effect | Adds **Engineering** nav + unlocks Ask “Details” eng panel |
| Demo | Mode **off** |
| Does not | Create duplicate product homes for J1–J9 |

---

## 10. Cross-screen One-Place Register (normative)

| Concern | Exactly one owner | Secondary access only |
|---------|-------------------|------------------------|
| Readiness / next action | Home | — |
| Site identity + URL | Site | Setup checklist link |
| Knowledge refresh (full/pending run) | Update | Home CTA; Library enqueue |
| Browse / filter items | Library | — |
| Ask / answer / sources UI | Ask | Performance deep-link prefill |
| Usage & quality trends | Performance | Home must **not** embed charts |
| History of questions | Activity | Ask “Recent” → Activity (same data) |
| Language / UI prefs | General | — |
| Model selection / pull | Models | — |
| Answer quality mode | Answers | — |
| Users & roles | Access | — |
| Engineering Mode toggle | General | — |
| Raw traces / flags / SI controls / tensions | Engineering * | — |

**Library enqueue rule:** Library bulk/row “Refresh” calls the **same update job API** as Update; copy = “Refresh selected”; progress ownership remains Update/Home readiness — **not** a second Indexing product.

---

## 11. Feature Ownership Matrix

| Feature | Primary screen | Secondary access | Engineering Mode | **Owner screen** | Status | Notes |
|---------|----------------|------------------|------------------|------------------|--------|-------|
| Authenticate | Sign in | — | — | Sign in | Spec | — |
| Readiness summary | Home | — | Status detail | **Home** | Spec | Eng may show raw probes |
| Setup checklist | Home | — | — | **Home** | Spec | Not a separate route |
| Next-action CTAs | Home | — | — | **Home** | Spec | ≤2 CTAs |
| Site URL | Site | Setup link | — | **Site** | Spec | — |
| Site identity/topics | Site | — | Raw JSON | **Site** | Spec | — |
| Generate site profile (guided) | Site | — | — | **Site** | Spec | Optional wizard |
| Start full update | Update | Home CTA | — | **Update** | Spec | Primary CTA |
| Start pending-only update | Update | — | — | **Update** | Spec | Plain-language mode |
| Monitor update progress | Update | Home state | — | **Update** | Spec | — |
| Cancel/stop update | Update | — | — | **Update** | Spec | If supported |
| Browse knowledge items | Library | — | — | **Library** | Spec | — |
| Filter failed/pending | Library | — | — | **Library** | Spec | — |
| Item detail (human) | Library | — | Raw SI | **Library** | Spec | Drawer preferred |
| Enqueue refresh selected | Library | — | — | **Update** (semantics) | Spec | Library is trigger only |
| Delete items | Library | — | — | **Library** | Spec | Confirm required |
| Ask question | Ask | Perf deep-link | — | **Ask** | Spec | — |
| Show answer + sources | Ask | — | — | **Ask** | Spec | — |
| New / clear thread | Ask | — | — | **Ask** | Spec | — |
| Why this answer (customer) | Ask | — | — | **Ask** | Spec | No eng jargon |
| Raw ask traces/export | — | — | Ask details | **Eng Ask details** | Spec | — |
| Usage KPIs/trends | Performance | — | — | **Performance** | Spec | — |
| Problematic queries | Performance | → Ask | — | **Performance** | Spec | — |
| Request/session history | Activity | Ask→Activity | — | **Activity** | Spec | Sole history SoT |
| UI language | General | — | — | **General** | Spec | — |
| Engineering Mode toggle | General | — | — | **General** | Spec | — |
| Chat model select | Models | — | — | **Models** | Spec | — |
| Embedding model select | Models | — | — | **Models** | Spec | — |
| Pull/install model | Models | — | Benchmarks | **Models** | Spec | — |
| Answers mode (4) | Answers | — | Raw retrieval | **Answers** | Spec | Modes only |
| User list/create/roles | Access | — | — | **Access** | Spec | — |
| Deactivate user | Access | — | — | **Access** | Spec | Confirm |
| SI generate/reprocess | — | Auto in Update | Knowledge internals | **Eng Knowledge** | Spec | Product: automatic |
| Epistemic tensions | — | — | Tensions | **Eng Tensions** | Spec | — |
| Chunk/retrieval knobs | — | — | Advanced | **Eng Advanced** | Spec | — |
| Caches/tracing/timeouts | — | — | Advanced | **Eng Advanced** | Spec | — |
| System prompt | — | — | Advanced | **Eng Advanced** | Spec | — |
| Build identity | — | — | Build & flags | **Eng Build** | Spec | — |
| Feature/migration flags | — | — | Build & flags | **Eng Build** | Spec | Not product Settings |
| Deploy/backup/migrate | — | — | — | **Ops CLI** | N/A | Not Dashboard |
| Load test / rollback drill | — | — | — | **Ops** | N/A | RFC-100 066 |

**Invariant:** No feature may list two different **Owner screen** values.

---

## 12. Navigation Ownership Matrix

| Route | Owner screen | Responsibility | Allowed entry points | Forbidden duplicates | Deep-link policy | Redirects |
|-------|--------------|----------------|----------------------|----------------------|------------------|-----------|
| `/login` | Sign in | Auth | Direct, session expiry | Second login page | — | — |
| `/` | — | — | — | Content page | — | → `/home` |
| `/home` | Home | J1 | Nav, post-login, logo | Overview, Dashboard home clone | — | — |
| `/knowledge` | — | — | — | — | — | → `/knowledge/library` |
| `/knowledge/library` | Library | J4 | Knowledge sub-nav, Home secondary | `/sources`, top-level Sources | `?bucket=failed` ok | Legacy `/sources` → here |
| `/knowledge/update` | Update | J3 | Sub-nav, Home primary, Setup | `/indexing`, second Start CTA elsewhere | — | Legacy `/indexing` → here |
| `/knowledge/site` | Site | J2 | Sub-nav, Setup | `/knowledge-profile` as product | — | Legacy `/knowledge-profile` → here |
| `/ask` | Ask | J5 | Nav, Home, Perf | `/chat`, Chat Test, Chat Diagnostics nav | `?q=` prefill ok | Legacy `/chat` → here |
| `/insights` | — | — | — | — | — | → `/insights/performance` |
| `/insights/performance` | Performance | J6 | Sub-nav | `/analytics` as product name in nav | — | Legacy `/analytics` → here |
| `/insights/activity` | Activity | J7 | Sub-nav, Ask Recent | `/logs`, chat-history-as-home | `?session=` ok | Legacy `/logs` → here |
| `/settings` | — | — | — | — | — | → `/settings/general` |
| `/settings/general` | General | J8a + Mode toggle | Settings sub-nav | — | — | — |
| `/settings/models` | Models | J8b | Sub-nav | Model UI on Home | — | — |
| `/settings/answers` | Answers | J8c | Sub-nav | Retrieval panels in product | — | — |
| `/settings/access` | Access | J9 | Sub-nav | `/users` top-level | — | Legacy `/users` → here |
| `/engineering` | — | — | Mode on only | Visible when Mode off | — | → `/engineering/status` |
| `/engineering/*` | Eng * | J10 | Eng nav | Any product top-level | — | Legacy `/diagnostics/*`, `/understanding` → eng routes |
| `*` unknown | — | — | — | Soft 404 content | — | → `/home` |

**Determinism:** Adding a new product route without updating this matrix = Gate **FAIL**.

---

## 13. Product Capability Matrix (RFC-100 → RFC-101)

| RFC-100 / platform capability | Appears where | User discovery | Complexity hidden how | Eng Mode? | Duplication risk |
|------------------------------|---------------|----------------|----------------------|-----------|------------------|
| 063 Flags default ON (KOS path) | Ask works | Ask nav / Home CTA | No enable toggles in product | Build shows status only | Flag grid in Settings |
| 064 Remove legacy Rag path | Ask only path | Invisible | No “legacy chat” UI | Emergency docs/eng if any | Dual chat engines UI |
| 065 Remove hybrid flag registry | — | — | Gone from product | Build if residual status | Reintroducing flag UI |
| 066 Load test / rollback | Ops only | Runbooks | Not in Dashboard | No | Fake “ops” Dashboard page |
| 067 GA / runbook | Product demo-ready | Whole product | — | — | Eng chrome left on |
| Executive / Reasoning / Evidence / Speech | Ask answers | Ask | Behavior, not labels | Ask details traces | Naming engines in UI |
| Memory assist / shadow | Better answers / eng compare | Invisible in product | Automatic | Tensions / Ask details | “Memory” product nav |
| Epistemic maintenance (0.9) | Fresher knowledge over time | Update/Library outcomes | Automatic | Tensions / internals | Maintenance console |
| Source Intelligence | Enrichment during Update | Automatic | No SI product tool | Knowledge internals | SI panels on Update |
| Knowledge Profile data | Site | Site / Setup | Guided fields | Raw JSON | Preset marketplace |
| Indexing jobs | Update | Update / Home | Progress in product words | Internals | Indexing + Sources starts |
| Chat streaming | Ask | Ask | — | — | Non-stream second chat |
| Analytics APIs | Performance | Insights | Customer metrics | — | Charts on Home |
| Chat logs/sessions | Activity | Insights / Ask→Activity | One history | — | Logs + modal homes |
| Settings language | General | Settings | — | — | Scattered language toggles |
| Ollama/models | Models | Settings | Simple list/select | Benchmarks eng | Home model lab |
| Answer quality presets | Answers | Settings | 4 modes only | Advanced retrieval | Dual preset systems |
| Users/roles | Access | Settings | — | — | Top-level Users |
| Feature flags | — | — | Not product | Build & flags | MigrationFlags in Settings |
| Deploy/backup | CLI | Ops | — | — | Dashboard deploy button |
| Golden/smoke | CI/ops | — | — | — | — |

---

## 14. Dashboard Design System Rules (architectural)

### 14.1 Layout principles

- App shell: left nav (collapsible) + main canvas + optional right drawer.  
- One page title = job name from glossary.  
- Max content width comfortable for tables/conversation; no dashboard widget mosaic on Home.  
- Section pages (Knowledge/Insights/Settings) share sub-nav pattern.

### 14.2 Page hierarchy

1. Product name / brand in shell  
2. Section (if any)  
3. Screen title (job)  
4. Primary CTA  
5. Content  
6. Secondary actions  

### 14.3 Spacing philosophy

- Consistent scale (e.g. 4/8-based).  
- Product: generous whitespace; Eng Mode: denser allowed.  
- Do not invent per-page spacing systems.

### 14.4 Card usage

- **Allowed:** metric group on Performance; readiness block on Home; settings section grouping.  
- **Forbidden:** card-per-subsystem on Home; cards as default list containers when a table is correct; decorative cards.

### 14.5 Table usage

- **Required:** Library, Activity, Access user list.  
- Sort/filter in-toolbar; bulk actions in a single bulk bar.

### 14.6 Chart usage

- **Only** Performance (and Eng status if needed).  
- **Forbidden** on Home, Ask, Update, Library, Settings product screens.

### 14.7 Form behavior

- Explicit Save (except Mode toggle may save immediately with toast).  
- Site URL and Answers mode never autosave silently from two screens.  
- Validation inline; block Save on error.

### 14.8 CTA hierarchy

- **One** primary button per screen (brand/accent).  
- Secondary = outline/ghost.  
- Tertiary = text links.  
- Destructive = confirm modal.

### 14.9 Progress indicators

- Update: determinate if known, else indeterminate + status text.  
- Home reflects Updating state.  
- No raw stage machine labels (“chunk embed”).

### 14.10 Empty / loading / error

| State | Pattern |
|-------|---------|
| Empty | Message + **one** CTA to owner action |
| Loading | Skeleton or spinner in content region; nav usable |
| Error | Message + retry if safe; no stack traces in product |

### 14.11 Confirmation dialogs

- Required: delete knowledge items, delete/deactivate users, stop update if destructive.  
- Modal for confirm; not drawer.

### 14.12 Drawer vs modal

| Use drawer | Use modal |
|------------|-----------|
| Library item detail | Confirm destroy |
| Optional filters (if needed) | Engineering Mode “are you sure” if needed |
| | |

Ask does **not** use a permanent diagnostics drawer in product mode.

### 14.13 Density

- Product: comfortable.  
- Engineering: compact ok.

### 14.14 Responsive behavior

- Nav collapses to icons/drawer on narrow viewports.  
- Tables scroll horizontally if needed; Ask stacks composer.  
- No separate “mobile app” IA.

### 14.15 Navigation behavior

- Active route highlighted.  
- Sub-nav visible only inside section.  
- Engineering nav hidden when Mode off (routes may 404 or redirect Home).

### 14.16 Component ownership

| UI need | Own in | Forbidden |
|---------|--------|-----------|
| Buttons, inputs, modal, drawer, table, pagination | `dashboard` design-system / `ui` kit | Page-local forks |
| PageHeader / empty/error | Shared | One-off headers |
| Ask conversation | Ask feature components | Reuse as “test lab” elsewhere |
| Metric/chart | Insights | Home copies |

---

## 15. Screen Contracts

Each contract is binding. **Forbidden responsibilities** are Gate FAIL if implemented on that screen.

### 15.1 Sign in — `/login`

| Field | Contract |
|-------|----------|
| Purpose | Authenticate |
| Primary job | Auth |
| Owner | Sign in |
| Entry | Unauthenticated |
| Exit | `/home` |
| Primary CTA | Sign in |
| Secondary CTA | — |
| Success | Session + Home |
| Empty | — |
| Loading | Button busy |
| Error | Invalid credentials message |
| Eng Mode | N/A |
| Related | Home |
| Forbidden | Setup forms, model config |

### 15.2 Home — `/home`

| Field | Contract |
|-------|----------|
| Purpose | Ready? What next? |
| Primary job | J1 |
| Owner | Home |
| Entry | Default, logo |
| Exit | Site / Update / Ask / Insights via CTAs |
| Primary CTA | From readiness (§7) |
| Secondary CTA | At most one (e.g. Review library) |
| Success | Clear state + CTA |
| Empty | = Needs setup checklist |
| Loading | Skeleton readiness |
| Error | “Can’t determine status” + retry |
| Eng Mode | Link to Engineering only; no dumps |
| Related | Site, Update, Ask, Performance |
| Forbidden | Charts, model benchmarks, flags, tensions, SI panels, analytics preview as product |

### 15.3 Library — `/knowledge/library`

| Field | Contract |
|-------|----------|
| Purpose | Browse / filter knowledge items |
| Primary job | J4 |
| Owner | Library |
| Entry | Knowledge sub-nav; Home |
| Exit | Detail drawer; Update |
| Primary CTA | None global — or “Refresh selected” when selection (enqueue) |
| Secondary CTA | Filters |
| Success | Table populated |
| Empty | CTA → Update |
| Loading | Table skeleton |
| Error | Retry load |
| Eng Mode | Raw profile in drawer extra section |
| Related | Update, Ask |
| Forbidden | Primary “Update all knowledge” competing with Update screen; SI control center |

### 15.4 Update — `/knowledge/update`

| Field | Contract |
|-------|----------|
| Purpose | Run + monitor knowledge refresh |
| Primary job | J3 |
| Owner | Update |
| Entry | Sub-nav; Home; Setup |
| Exit | Library; Ask |
| Primary CTA | Update knowledge |
| Secondary CTA | Mode (full / pending) if needed |
| Success | Completed + summary |
| Empty | Before first run: explain + CTA |
| Loading | Progress region |
| Error | Failed run message + retry |
| Eng Mode | Link to Knowledge internals |
| Related | Library, Home, Site |
| Forbidden | Retrieval settings; flag toggles; SI as main chrome |

### 15.5 Site — `/knowledge/site`

| Field | Contract |
|-------|----------|
| Purpose | Site identity for the agent |
| Primary job | J2 |
| Owner | Site |
| Entry | Sub-nav; Setup |
| Exit | Update; Ask |
| Primary CTA | Save |
| Secondary CTA | Generate profile (optional) |
| Success | Saved toast; checklist advances |
| Empty | URL required prompt |
| Loading | Form skeleton |
| Error | Validation / save error |
| Eng Mode | Advanced JSON |
| Related | Update, Home |
| Forbidden | Industry preset marketplace; migration banners as normal UI |

### 15.6 Ask — `/ask`

| Field | Contract |
|-------|----------|
| Purpose | Q&A with sources |
| Primary job | J5 |
| Owner | Ask |
| Entry | Nav; Home; `?q=` |
| Exit | Activity link; stay in thread |
| Primary CTA | Send |
| Secondary CTA | New thread; Recent→Activity |
| Success | Answer + sources |
| Empty | Composer hint |
| Loading | Streaming / pending indicator |
| Error | Retry send |
| Eng Mode | Details panel / export |
| Related | Activity, Library, Performance |
| Forbidden | Default diagnostics drawer; dual product name; eng jargon in default “why” |

### 15.7 Performance — `/insights/performance`

| Field | Contract |
|-------|----------|
| Purpose | Usage & quality |
| Primary job | J6 |
| Owner | Performance |
| Entry | Insights sub-nav |
| Exit | Ask prefill; Activity |
| Primary CTA | — or “Open in Ask” on row |
| Secondary CTA | Time range |
| Success | KPIs + charts |
| Empty | Not enough data yet |
| Loading | Chart skeletons |
| Error | Retry |
| Eng Mode | Unchanged |
| Related | Ask, Activity |
| Forbidden | Becoming Home; eng score dumps |

### 15.8 Activity — `/insights/activity`

| Field | Contract |
|-------|----------|
| Purpose | History SoT |
| Primary job | J7 |
| Owner | Activity |
| Entry | Sub-nav; Ask Recent |
| Exit | Ask |
| Primary CTA | Open in Ask |
| Secondary CTA | Search/filter |
| Success | Paginated history |
| Empty | No activity yet → Ask |
| Loading | Table skeleton |
| Error | Retry |
| Eng Mode | Unchanged |
| Related | Ask, Performance |
| Forbidden | Second history store/UI as product home |

### 15.9 General — `/settings/general`

| Field | Contract |
|-------|----------|
| Purpose | Language + Engineering Mode toggle |
| Primary job | J8a |
| Owner | General |
| Entry | Settings sub-nav |
| Exit | — |
| Primary CTA | Save (if needed) |
| Secondary CTA | — |
| Success | Preferences applied |
| Empty | — |
| Loading | — |
| Error | Save error |
| Eng Mode | Toggle lives here |
| Related | — |
| Forbidden | Retrieval; flags |

### 15.10 Models — `/settings/models`

| Field | Contract |
|-------|----------|
| Purpose | Select/pull models |
| Primary job | J8b |
| Owner | Models |
| Entry | Sub-nav |
| Exit | — |
| Primary CTA | Save selection / Pull |
| Secondary CTA | — |
| Success | Models ready |
| Empty | No models — pull CTA |
| Loading | List load |
| Error | Pull/save error |
| Eng Mode | Benchmarks elsewhere |
| Related | Ask (uses models) |
| Forbidden | Home model lab |

### 15.11 Answers — `/settings/answers`

| Field | Contract |
|-------|----------|
| Purpose | Quality mode only |
| Primary job | J8c |
| Owner | Answers |
| Entry | Sub-nav |
| Exit | — |
| Primary CTA | Save |
| Secondary CTA | — |
| Success | Mode saved |
| Empty | — |
| Loading | — |
| Error | Save error |
| Eng Mode | Raw retrieval in Advanced |
| Related | Ask |
| Forbidden | Any retrieval/chunk/temperature/boost control |

**Modes (exact product set):** Automatic · Fast · Balanced · High precision

### 15.12 Access — `/settings/access`

| Field | Contract |
|-------|----------|
| Purpose | Users & roles |
| Primary job | J9 |
| Owner | Access |
| Entry | Sub-nav |
| Exit | — |
| Primary CTA | Add user |
| Secondary CTA | — |
| Success | User list |
| Empty | Add first user |
| Loading | Table skeleton |
| Error | Retry |
| Eng Mode | N/A |
| Related | — |
| Forbidden | Top-level Users nav |

### 15.13 Engineering screens (shared contract pattern)

| Field | Contract |
|-------|----------|
| Purpose | J10 only |
| Entry | Engineering nav when Mode on |
| Exit | Product screens |
| Primary CTA | Screen-specific |
| Forbidden | Appearing in default nav; replacing product jobs |

Individual eng screens own rows in §11; UI may be denser; eng terminology allowed **inside Engineering only**.

---

## 16. Cross-Screen Responsibility Review (pass criteria)

| Rule | Owner | Pass if |
|------|-------|---------|
| One Job = One Screen | Jobs J1–J10 | Each job has one owner screen |
| One Function = One Place | §10 | Matrix has unique Owner |
| One History | Activity | No Logs+modal homes |
| One Model Manager | Models | No Home LLM lab |
| One Knowledge Update | Update | Library only enqueues |
| One Settings chrome | Settings section | No scattered settings pages |
| One User Management | Access | No `/users` product nav |
| One Answer Configuration | Answers | Modes only in product |
| One Site Owner | Site | No KP duplicate |
| One Library Owner | Library | No Sources duplicate |
| One Ask Owner | Ask | No Chat Test/Diagnostics dual |

---

## 17. Terminology + glossary

### 17.1 Standardization

| Use | Do not use (product) |
|-----|----------------------|
| Ask | Chat Test, Chat Diagnostics, Playground |
| Update knowledge | Indexing (nav), crawl (primary CTA) |
| Library | Sources (nav) |
| Site | Knowledge Profile, KP |
| Performance | Analytics (nav label) |
| Activity | Logs (nav) |
| Answers mode | Retrieval profile, hybrid |
| Sources (on answer) | Chunks, hits |
| Ready / Needs attention | Subsystem soup |
| Engineering Mode | Debug/god mode |

### 17.2 Glossary

Agent · Site · Knowledge · Library · Update · Ask · Sources (citations) · Insights · Activity · Answers mode · Engineering Mode · Ready — as defined in prior RFC-101 sense (user-facing meanings unchanged).

---

## 18. Removed / merged concepts

See Feature Ownership + Capability matrices. Product vocabulary removals remain binding (§11–§13 prior intent): Chat Test/Diagnostics, Indexing/Sources nav, Epistemic product nav, flag matrices in Settings, etc.

---

## 19. Design principles & simplicity rules

**Primary:** Simplicity Outside. Complexity Inside.

Also: One Job = One Screen; One Function = One Place; Nav by intent; Product before eng convenience; RFC-100 as behavior not toggles; Gate against this spec.

Simplicity caps: ≤5 top-level nav; ≤4 Settings sections; ≤4 Answers modes; ≤2 Home CTAs; Setup→Update→Ask ≤3 steps; no second history/models/update owners.

---

## 20. Anti-patterns (automatic Gate FAIL if in default product)

1. Dual nav labels for one route  
2. Module-shaped nav  
3. Eng concepts in default UI (retrieval, memory, pipelines, SI-as-tool, flags, deploy)  
4. Multiple update starts without Update owner  
5. Home junk drawer / charts / benchmarks  
6. Ask as default lab  
7. Settings encyclopedia  
8. Experimental/temporary badges as normal  
9. Industry presets as happy path  
10. Teaching eng vocabulary for a job  
11. New page for an owned job  
12. Stripping RFC-100 capability instead of integrating  
13. Invisible product debt  
14. Gate rubber-stamp without RFC-101 check  
15. New route absent from §12  
16. Feature with two Owner screens  

---

## 21–27. (Reserved summary pointers)

Detailed inventories live in §9–§15. Do not fork parallel “lite” specs.

---

## 28. Product Readiness Gate — RFC-101 enforcement

### 28.1 Automatic FAIL

Gate **MUST FAIL** if the change:

- Introduces **new duplication** of an Owner in §11  
- Adds nav/route **not** in §12 (without updating RFC-101 first via product acceptance)  
- Reintroduces **removed product vocabulary** in default chrome  
- Violates a Screen Contract **Forbidden** list  
- Exposes eng terminology in default product copy  
- Pollutes navigation (extra top-level, dual labels)  
- Creates **undeclared** product debt  
- Moves Dashboard **away** from RFC-101 IA  
- Puts charts on Home, model manager outside Models, history outside Activity, modes outside Answers, etc.

### 28.2 Architecture Review question (mandatory)

> Does this change move the Dashboard closer to RFC-101, or away from it?

Away ⇒ **FAIL**.

### 28.3 Gate record addition

```text
  rfc101_compliance: pass | fail
  owner_screen: <from §11>
  new_route: yes|no
```

---

## 29. Product Acceptance Checklist (every Dashboard PR)

Copy into PR / Gate record:

- [ ] RFC-101 consulted  
- [ ] Feature maps to **one** Owner screen (§11)  
- [ ] No second product home for this function  
- [ ] Routes/nav match §12 (or RFC-101 updated + accepted first)  
- [ ] Screen Contract Forbidden list not violated  
- [ ] No eng concepts in default UI  
- [ ] Belongs in Engineering Mode? If yes, Mode-gated only  
- [ ] One Job = One Screen preserved  
- [ ] No new duplication (update/history/models/settings/ask/site/library)  
- [ ] Terminology matches §17  
- [ ] Design system rules §14 followed (no page-local system)  
- [ ] Does not violate simplicity caps §19  
- [ ] Product Debt declared (none / accepted / must-resolve)  
- [ ] Global product impact: better or neutral after change  
- [ ] RFC-100 capability integrated, not deleted  

Any unchecked without justification ⇒ Gate **FAIL**.

---

## 30. Release 1.0 readiness review (architecture)

| Question | Verdict |
|----------|---------|
| Can engineers build the Dashboard from RFC-101 alone? | **Yes**, with this revision |
| Are ownership/nav deterministic? | **Yes** (§11–§12) |
| Is Gate objectively enforceable? | **Yes** (§28–§29 + Product Readiness §6) |
| Does this block Steps 063–067? | **No** |
| Remaining gaps (non-blocking for start) | Pixel mockups; exact API field mapping; i18n key rename plan; visual brand tokens file — **implementation details**, not product-architecture blockers |

**Remaining architectural gaps:** none that prevent starting Dashboard implementation aligned to RFC-101 in parallel with RFC-100. Optional follow-ups (not required to unlock 063): published Figma/token sheet; redirect map in code comments generated from §12.

---

## 31. Out of scope

Backend engines, deploy tooling, RFC-100 step code, pixel-perfect mockups, ops promotion flags.

---

## 32. Document control

| Item | Value |
|------|--------|
| Path | `docs/RFC-101-DASHBOARD-PRODUCT-SPECIFICATION.md` |
| Role | **Single source of truth** for Dashboard product architecture |
| Supersedes | Ad-hoc Dashboard UX decisions; engineering-console IA |
| Does not supersede | RFC-100 engineering scope; Knowledge OS architecture; deploy architecture |
| Implementation companion | `docs/RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md` (HOW) |
| Changes to IA/ownership | Product Owner acceptance + RFC-101 edit **before** implementing drift |

---

**End of RFC-101**

*If it is not in RFC-101, it is not the Release 1.0 Dashboard. If it contradicts RFC-101, the Gate fails it.*
