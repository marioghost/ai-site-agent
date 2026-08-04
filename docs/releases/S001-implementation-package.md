# S001 — Implementation Package

**Step:** S001 — Bootstrap + IA substrate + Engineering Mode unlock  
**Program:** `docs/releases/1.0-rfc-101-master-program.md`  
**Roadmap:** `docs/releases/1.0-rfc-101-execution-roadmap.md`  
**Execution Strategy:** `docs/releases/1.0-rfc-101-execution-strategy.md`  
**Inventory:** `docs/releases/1.0-rfc-101-product-completion-master-audit.md`  
**Product / HOW:** RFC-101 · RFC-102 · RFC-PRODUCT-READINESS  

**Status:** **FROZEN for implementation** — Open Questions closed; ready for Step S001 coding  
**Duration band (roadmap):** XL  

---

## 1. Objective

Deliver the Product Completion **substrate** so later Steps can migrate surfaces lawfully:

1. Bootstrap program process artifacts (SoT pointer, engineering-vs-product clarification, Gate template, debt register, G11 exclusion, status seed).  
2. Establish RFC-102 `features/*` (and related) **skeleton**.  
3. Introduce RFC-101 **canonical routes** alongside legacy routes (**coexistence**).  
4. Establish **product nav baseline** + **initial glossary** labels (job-shaped; Eng appended only when Mode on).  
5. Unlock **Engineering Mode**: General hosts the toggle; Mode context + route guard; six Eng **scaffolds** ready to receive moves in later Steps.

**Unlocks:** S002–S005 parallel cutovers and S006 isolation destinations.  
**Does not:** migrate Knowledge/Insights/Ask/Home product content; strip diagnostics/SI/Advanced; change authenticated default landing away from Overview; touch RFC-100 / Step 067 / ops gates; implement G11 backend work; fix G10 verify-release (optional S00T).

---

## 2. Scope

### In scope

| Area | Included |
|------|----------|
| Docs bootstrap | G12-P1, G12-P2, G9-P1, G11-P0, program status seed |
| Frontend structure | G8-P1 skeleton folders/modules |
| Routing | G1-P1 canonical routes + thin page adapters / placeholders |
| Navigation | G1-P3 navConfig + role matrix baseline; Eng nav only when Mode on |
| Terminology | G1-P4 initial glossary for claimed chrome labels (en/uk) |
| Settings General slice | G2-P1 `/settings/general` as Mode toggle host (+ language if moved without inventing new prefs) |
| Engineering Mode | G2-P2 context/guard; G2-P3 six Eng destination scaffolds |
| Tests | Per §7 |
| Gate | Product-facing General + Mode UX |

### Explicitly out of scope (later Steps)

| Deferred | Owner Step |
|----------|------------|
| Full redirects map for all legacy paths | G1-P2 increments in S002+ / finalize S007 |
| Knowledge/Insights/Ask/Home content migration | S002–S005 |
| SI / diagnostics / Advanced knobs moves | S006 |
| Overview retirement; `/` → `/home` as default | S007 |
| G8-P3/P4 polish & dead-code sweep | S008 |
| G9-P2/P3 validation **execution** | S008 (protocol templates may be referenced; full evidence packs not required for S001) |
| G10 verify-release | S00T (optional parallel) |
| G11 backend deferred implementation | Excluded |

### Coexistence rules (S001)

- Legacy routes (`/overview`, `/chat`, `/sources`, …) **remain functional** (except `/settings` — see Resolved Decisions Q2).  
- Canonical routes **exist** and are reachable.  
- **`/settings` MUST redirect immediately to `/settings/general`** (single Settings home).  
- Authenticated default remains **`/` → `/overview`** until S007 (do not invent early default change).  
- Catch-all may remain Overview-bound until S007.  
- Product nav **baseline** uses RFC-101 job labels pointing at canonical routes (scaffolds only — Resolved Decisions Q3).  
- Legacy URLs (other than `/settings`) remain bookmarkable without requiring full G1-P2 completion for every path in S001.

---

## 3. Package IDs covered

Exact set (nothing else):

| ID | Title |
|----|--------|
| G12-P1 | Engineering vs Product Accepted Product clarification |
| G12-P2 | Program SoT pointer |
| G9-P1 | Gate record template + debt register |
| G8-P1 | Feature module skeleton |
| G11-P0 | Backend deferred boundary record only |
| G1-P1 | Canonical route table substrate |
| G1-P3 | navConfig + role matrix (product baseline; Eng append when Mode on) |
| G1-P4 | Terminology / i18n glossary application (initial) |
| G2-P1 | General toggle host (G7 first slice) |
| G2-P2 | EngineeringMode context + route guard |
| G2-P3 | Six Eng destination scaffolds |

---

## 4. Files expected to change

Paths are **expected** from current tree + RFC-102 targets. Exact filenames may vary slightly if implementers place thin adapters under `pages/` vs `features/*/Screen`—structure must obey RFC-102.

### Frontend

| Area | Expected paths |
|------|----------------|
| App / router | `dashboard/src/App.tsx` (and/or `dashboard/src/app/router.tsx` if introduced) |
| Providers | `dashboard/src/main.tsx` and/or `dashboard/src/app/providers.tsx` |
| Nav | `dashboard/src/components/layout/AppSidebar.tsx` → migrate toward `layouts/` + `navConfig.ts` (e.g. `dashboard/src/lib/navConfig.ts` or `dashboard/src/layouts/navConfig.ts`) |
| Permissions | `dashboard/src/lib/permissions.ts` |
| Layout shell | `dashboard/src/components/layout/*` and/or new `dashboard/src/layouts/*` |
| Context | **New** `dashboard/src/context/EngineeringModeContext.tsx` (or settings-owned hook module per RFC-102) |
| Guard | **New** `RequireEngineeringMode` (alongside `RequireAuth`) |
| Feature skeleton | **New** tree under `dashboard/src/features/{auth,home,knowledge/{library,update,site},ask,insights/{performance,activity},settings/{general,models,answers,access},engineering/{status,ask-details,knowledge,tensions,advanced,build}}` (+ `shared/` stubs as needed) |
| Layouts skeleton | **New** `dashboard/src/layouts/` section layout stubs (Knowledge/Insights/Settings/Engineering) as needed for nested routes |
| Shared skeleton | **New** `dashboard/src/shared/ui/` placeholder barrel if required by RFC-102 (may re-export existing `ui/` temporarily—must not invent design system) |
| Thin pages | **New/updated** `dashboard/src/pages/*` thin adapters for canonical routes |
| General screen | **New** `features/settings/general/*` |
| Eng scaffolds | **New** `features/engineering/{status,ask-details,knowledge,tensions,advanced,build}/*` |
| i18n | `dashboard/src/i18n/en.ts`, `dashboard/src/i18n/uk.ts` (nav/glossary keys) |
| Settings | `features/settings/general/*` is Mode toggle host; router: `/settings` → `/settings/general`; legacy `SettingsPage.tsx` must **not** remain a second canonical home at `/settings` (content migration to Models/Answers/Access is S004; scaffolds for those routes in S001) |
| Mode storage | Client `localStorage` key `engineering.mode.enabled` only (Resolved Decisions Q1/Q7) |

### Backend

| Area | Expected |
|------|----------|
| Runtime / APIs | **None** for Engineering Mode — no settings API, no backend persistence (Q1) |
| build-info / release metadata | **Do not change** |

### Shared

| Area | Expected |
|------|----------|
| Cross-package shared backend libs | **None** |

### Tests

| Area | Expected paths |
|------|----------------|
| Ownership / Mode | **New** S001-oriented tests (e.g. `dashboard/src/s001EngineeringMode.test.ts` or feature tests) |
| Nav / permissions | Update `dashboard/src/lib/permissions` tests; navConfig snapshot if used |
| Historical Step 065 | `dashboard/src/step065Ownership.test.ts` — **must be updated** (Strategy §6.8): assertions that forbade `/engineering` are historical RFC-100 constraints and cannot remain as false authority |
| Understanding/permissions samples | `dashboard/src/lib/understandingTensions.test.ts` may need route allowlist updates if it asserts legacy-only maps |

### Documentation

| Artifact | Expected path |
|----------|----------------|
| Engineering vs Product Accepted clarification | e.g. `docs/releases/1.0-product-completion-lifecycle-clarification.md` **or** a clearly titled section under Product Completion docs (G12-P1) — **new file preferred to avoid editing frozen planning authorities** |
| Program SoT pointer | e.g. `docs/releases/1.0-rfc-101-program-entry.md` (G12-P2) |
| Gate template | e.g. `docs/releases/templates/product-readiness-gate-record.md` (G9-P1) |
| Debt register | e.g. `docs/releases/1.0-rfc-101-product-debt-register.md` (G9-P1) |
| G11 exclusion | Record in program status / debt register (G11-P0) |
| Program status seed | e.g. `docs/releases/1.0-rfc-101-program-status.md` (Master Program §8) |
| S001 Gate record | e.g. `docs/releases/S001-product-readiness-gate.md` |
| S001 evidence / migration note | e.g. `docs/releases/S001-implementation-evidence.md` |

**Do not modify:** Inventory, Execution Strategy, Master Program, Execution Roadmap, RFC-101, RFC-102, RFC-100, Step 067 evidence.

---

## 5. Architecture impact

| Concern | Impact |
|---------|--------|
| RFC-101 IA | Canonical routes introduced; product nav baseline job-shaped; Eng additive when Mode on |
| RFC-102 structure | Skeleton + General + Eng feature modules begin real ownership; legacy pages remain for coexistence |
| Engineering Mode | localStorage preference; General toggle; guard; Eng nav; six scaffolds; reset OFF on logout |
| Settings | Canonical `/settings/general`; `/settings` redirects to General; Models/Answers/Access scaffolds only until S004 |
| Default landing | **Unchanged** (`/overview`) — intentional S001 boundary |
| Backend / deploy / lifecycle | No impact intended |
| Step 065 tests | Historical “no Eng routes” contracts superseded for Product Completion |

**Non-impacts:** No capability deletion; no Eng content moves from Chat/Indexing/Settings Advanced; no G11 backend.

---

## 6. Detailed implementation tasks

Task IDs are for implementation tracking inside S001 only.

### T01 — G12-P1 Lifecycle clarification doc

| Field | Content |
|-------|---------|
| Purpose | Durable wording: engineering closure (`accepted=1.0` / Step 067) ≠ Product Accepted Product; Product Completion owns remainder |
| Owner | Release documentation |
| Expected files | New clarification doc under `docs/releases/` (not editing Step 067 artifacts) |
| Dependencies | None |

### T02 — G12-P2 Program SoT pointer

| Field | Content |
|-------|---------|
| Purpose | Single entry pointing to Inventory + Strategy + Master Program + Roadmap + this package |
| Owner | Release documentation |
| Expected files | `docs/releases/1.0-rfc-101-program-entry.md` (or equivalent) |
| Dependencies | Soft: T01 |

### T03 — G9-P1 Gate template + debt register

| Field | Content |
|-------|---------|
| Purpose | Operable Gate record format (RFC-PRODUCT-READINESS §6.8 fields) + product debt register |
| Owner | Product Readiness |
| Expected files | Gate template; debt register markdown |
| Dependencies | None |

### T04 — G11-P0 Exclusion record

| Field | Content |
|-------|---------|
| Purpose | Explicitly exclude dual-read / kos_tension_resolved_total / pipeline deferred adapters from Dashboard S001+ packages |
| Owner | Program tracking |
| Expected files | Status seed + debt/exclusion row |
| Dependencies | Soft: T03, T05 |

### T05 — Program status seed

| Field | Content |
|-------|---------|
| Purpose | Initialize package/cluster status tracking per Master Program §8 |
| Owner | Program tracking |
| Expected files | `docs/releases/1.0-rfc-101-program-status.md` |
| Dependencies | Soft: T02 |

### T06 — G8-P1 Feature / layouts / shared skeleton

| Field | Content |
|-------|---------|
| Purpose | Create RFC-102 folder skeleton with placeholder barrels so migrate-on-touch has a home |
| Owner | Dashboard architecture |
| Expected files | `dashboard/src/features/**`, `layouts/**` stubs, optional `shared/ui` barrel; no big-bang page moves |
| Dependencies | None |

### T07 — G1-P1 Canonical route substrate

| Field | Content |
|-------|---------|
| Purpose | Register RFC-101 routes: `/home`, `/knowledge/*`, `/ask`, `/insights/*`, `/settings/general` (+ other settings children stubs if needed for nav), `/engineering/*`; keep legacy routes |
| Owner | Dashboard IA |
| Expected files | Router; thin page adapters; placeholder Screens in features |
| Dependencies | Soft: T06 |

**Canonical routes required (RFC-101 §6):**  
`/home` · `/knowledge/library` · `/knowledge/update` · `/knowledge/site` · `/ask` · `/insights/performance` · `/insights/activity` · `/settings/general` · `/settings/models` · `/settings/answers` · `/settings/access` · `/engineering/status` · `/engineering/ask-details` · `/engineering/knowledge` · `/engineering/tensions` · `/engineering/advanced` · `/engineering/build`  

Section default redirects **required in S001:** `/knowledge`→library, `/insights`→performance, **`/settings`→`/settings/general` (Q2 FINAL)**, `/engineering`→status (when Mode on; when Mode off Eng paths follow Q6). Full **legacy** redirect map (`/sources`→library, etc.) is **not** required for S001 DoD (G1-P2 later)—optional if zero-risk.

### T08 — G2-P1 General toggle host

| Field | Content |
|-------|---------|
| Purpose | `/settings/general` owns Engineering Mode toggle (and language if relocated without new preference invention) |
| Owner | Dashboard Settings |
| Expected files | `features/settings/general/*`; route wired; toggle bound to `useEngineeringMode()` / localStorage key `engineering.mode.enabled` |
| Dependencies | Hard: T07 (`/settings/general` route) |

### T09 — G2-P2 EngineeringMode context + guard

| Field | Content |
|-------|---------|
| Purpose | Mode default **off**; persist only via `localStorage` key `engineering.mode.enabled`; `useEngineeringMode()`; on **logout** force Mode **OFF** and clear leak (Q5); `RequireEngineeringMode`: if Mode off and path is `/engineering/*`, **redirect to `/settings/general`** (Q6)—never 403/blank/hidden scaffold; Owner-only Eng per RFC-101 §2.1 |
| Owner | Dashboard Engineering Mode |
| Expected files | Context/hook; guard component; provider wiring; logout integration |
| Dependencies | Hard: T08 |

### T10 — G2-P3 Six Eng scaffolds

| Field | Content |
|-------|---------|
| Purpose | Scaffold Screens for six Eng destinations meeting shared Eng contract pattern (purpose J10; **placeholder policy Q3 only**; no invented backend powers) |
| Owner | Dashboard Engineering Mode |
| Expected files | `features/engineering/{status,ask-details,knowledge,tensions,advanced,build}/*` |
| Dependencies | Hard: T09 |

### T11 — G1-P3 navConfig + role matrix baseline

| Field | Content |
|-------|---------|
| Purpose | Central nav data: product top-level Home · Knowledge · Ask · Insights · Settings; Eng section **only** when Mode on; permissions for new paths per RFC-101 §2.1 |
| Owner | Dashboard IA |
| Expected files | `navConfig.ts`; `AppSidebar`/layout consumers; `permissions.ts` updates |
| Dependencies | Soft: T07; Hard for Eng-nav-complete claim: T09 |

### T12 — G1-P4 Initial glossary i18n

| Field | Content |
|-------|---------|
| Purpose | Apply RFC-101 glossary labels to claimed nav chrome (en/uk); avoid product dependence on forbidden top-level names in the **new** nav baseline |
| Owner | Dashboard IA / i18n |
| Expected files | `i18n/en.ts`, `i18n/uk.ts` |
| Dependencies | Soft: T11 |

### T13 — Update historical ownership tests

| Field | Content |
|-------|---------|
| Purpose | Replace Step 065 “no `/engineering`” false authority with S001 assertions (Mode isolation + General toggle owner) |
| Owner | Dashboard QA |
| Expected files | `step065Ownership.test.ts` and/or successor S001 tests |
| Dependencies | Hard: T09–T11 |

### T14 — S001 Product Readiness Gate record

| Field | Content |
|-------|---------|
| Purpose | Record Gate for General + Mode UX; N/A justified for docs/skeleton/G11 boundary |
| Owner | Product Readiness |
| Expected files | `docs/releases/S001-product-readiness-gate.md` (+ debt rows if any) |
| Dependencies | Hard: T03 template; Soft: T08–T11 implemented |

### T15 — S001 evidence + inventory/program closure update

| Field | Content |
|-------|---------|
| Purpose | Evidence index; mark S001 packages Completed in status; close claimed inventory findings in tracking |
| Owner | Program tracking |
| Expected files | Evidence note; updated `1.0-rfc-101-program-status.md` |
| Dependencies | Hard: T01–T14 acceptance criteria met |

---

## 7. Testing plan

### Unit

- Permissions: role × canonical path matrix matches RFC-101 §2.1 (Viewer/Operator/Owner; Eng Owner+Mode).  
- Mode preference defaults **off**; storage key is exactly `engineering.mode.enabled` (Q7).  
- No backend settings calls for Mode.  
- navConfig: product top-level set exact; Eng items absent when Mode off.  
- Pure helpers if any (no invented readiness logic beyond stubs).

### Integration / screen

- General screen renders Mode toggle.  
- Each Eng scaffold mounts under guard when Mode on (smoke).  
- Canonical placeholder screens render **only** neutral scaffold copy (Q3)—no CTAs/fake stats.

### Navigation

- Product nav labels use glossary terms.  
- Mode off: no Engineering nav; direct `/engineering/*` → **redirect `/settings/general`** (Q6).  
- Mode on (Owner): Engineering nav appears; Eng routes reachable.  
- **`/settings` → `/settings/general`** always (Q2).  
- Legacy routes (except `/settings`) still resolve (coexistence).  
- Default `/` still lands Overview (regression).

### Engineering Mode

- Default off for all roles.  
- Toggle only on General.  
- Persist only in localStorage under frozen key (Q1/Q7).  
- **Logout resets Mode to OFF**; no cross-user leak (Q5).  
- Guard + nav coupling.  
- No eng widgets mounted into product Overview/Chat as part of S001 (scaffolds live only under Eng routes).

### Regression

- Login + existing legacy pages still load (except `/settings` redirect).  
- Step 065 product Settings still does not remount `MigrationFlagsPanel`.  
- No RFC-100 / build-info / backend behavior changes.  
- `release-check` / dashboard vitest green.

### Product Readiness Gate

- Gate record using G9-P1 template.  
- Areas: IA/nav baseline, Eng Mode isolation start, General toggle ownership, `/settings` single home.  
- Debt: declare **none** or explicit items (e.g. Models/Answers/Access still scaffolds until S004; legacy module URLs still bookmarkable).  
- Result target: **PASS** or **PASS WITH DEBT** for user-facing slices; **N/A** lines for pure docs/G11/skeleton as justified.

---

## 8. Acceptance checklist

- [ ] Only listed package IDs implemented; no S002–S008 scope creep  
- [ ] G12-P1 clarification published (Step 067 untouched)  
- [ ] G12-P2 SoT pointer published  
- [ ] G9-P1 Gate template + debt register exist  
- [ ] G11-P0 exclusion recorded  
- [ ] G8-P1 skeleton exists per RFC-102 feature map  
- [ ] G1-P1 all canonical routes reachable; legacy routes still work  
- [ ] Default landing still Overview  
- [ ] G1-P3 product nav baseline job-shaped; Eng nav only when Mode on  
- [ ] G1-P4 en/uk glossary applied to claimed nav labels  
- [ ] G2-P1 General owns Mode toggle; storage key `engineering.mode.enabled` only  
- [ ] G2-P2 Mode default off; logout resets OFF; `/engineering/*` when off → `/settings/general`  
- [ ] G2-P3 six Eng scaffolds exist with **Q3-only** placeholder copy (no fake backends/CTAs)  
- [ ] `/settings` redirects to `/settings/general` (no second Settings home)  
- [ ] Historical “no engineering routes” tests updated  
- [ ] Automated tests green  
- [ ] S001 Gate recorded  
- [ ] Program status updated; S001 packages → Completed  
- [ ] No backend/lifecycle/ops-gate/RFC-100 changes  
- [ ] No Mode settings API / backend persistence 

---

## 9. Evidence required

| Evidence | Artifact |
|----------|----------|
| Documentation | G12 clarification; SoT pointer; Gate template; debt register; G11 exclusion; status seed |
| Architecture delta | Routes added; Mode/guard; navConfig; feature skeleton tree list |
| Migration notes | Coexistence statement: legacy kept; default Overview retained; no content moves |
| Tests | Vitest output / CI reference |
| Screenshots | General + Mode toggle; Mode off nav; Mode on Eng nav + one Eng scaffold (minimal) |
| Gate result | `S001-product-readiness-gate.md` |
| Inventory/program closure | Status rows for package IDs; findings closed pointers |
| Non-evidence | No cold-demo full pack (S008); no verify-release fix (S00T) |

---

## 10. Definition of Done

S001 is **Done** only when:

1. All §3 package IDs meet Master Program acceptance boundaries for those packages.  
2. §8 checklist is complete.  
3. §7 tests pass.  
4. §9 evidence is filed.  
5. Execution Strategy rules held: no duplicate final owners claimed prematurely; no eng chrome deleted; no intermediate ownership parking; Mode isolation started correctly.  
6. Roadmap S001 expected deliverables met: Eng Mode operable; canonical routes coexist; Gate template live; later Waves unblocked.  
7. Milestone **M1** conditions attributable to S001 are satisfied.

Compiling alone is not Done.

---

## 11. Resolved Decisions (FINAL)

All former Open Questions are **closed**. These decisions are **project law** for S001 and subsequent Product Completion Steps unless a frozen architecture authority is formally amended.

### Q1 — Engineering Mode persistence — FINAL

| Field | Decision |
|-------|----------|
| Medium | **localStorage only** |
| Backend persistence | **Forbidden** |
| Settings API for Mode | **Forbidden** |
| Reason | Engineering Mode is a **local UI preference**, not business data |
| Canonical key | `engineering.mode.enabled` |

### Q2 — `/settings` behavior — FINAL

| Field | Decision |
|-------|----------|
| Canonical Settings home | **`/settings/general`** |
| Legacy `/settings` | **MUST immediately redirect** to `/settings/general` |
| Dual Settings homes | **Forbidden** — there must never be two canonical Settings homes |
| Models / Answers / Access | Canonical child routes exist as scaffolds in S001; full content migration remains S004 |

### Q3 — Placeholder policy — FINAL (project law)

| Field | Decision |
|-------|----------|
| Allowed copy | Neutral scaffold only: **"This section has not been migrated yet."** or localized equivalent |
| Forbidden | “Coming Soon”, “Beta”, “Future”, “Try”, CTA buttons, fake actions, fake statistics, marketing copy, feature promises |

### Q5 — Logout resets Mode — FINAL

| Field | Decision |
|-------|----------|
| On logout | Engineering Mode **MUST** reset to **OFF** |
| Cross-user leak | **Forbidden** — no Engineering Mode state may leak between users |
| Implementation note | Clear or overwrite `engineering.mode.enabled` appropriately so the next session defaults off |

### Q6 — Direct Eng navigation while Mode OFF — FINAL

| Field | Decision |
|-------|----------|
| When Mode OFF and path is `/engineering/*` | **MUST redirect to `/settings/general`** |
| Forbidden responses | **403**, blank page, or hidden scaffold |

### Q7 — Storage key freeze — FINAL

| Field | Decision |
|-------|----------|
| Key | **`engineering.mode.enabled`** — permanently frozen |
| Aliases / variants | **Forbidden** |

### Former Q4 — Operator Eng access

Not an open question: RFC-101 §2.1 remains authoritative (Owner + Mode on only). No invention.

---

## 12. Stop conditions

Stop implementation and escalate (do not invent) if:

- Any task requires changing Inventory / Strategy / Program / Roadmap / RFC-101 / RFC-102.  
- Pressure to migrate S002–S006 content inside S001.  
- Pressure to flip default landing to Home early.  
- Pressure to implement G11 or G10 inside S001.  
- Pressure to remount flag catalogs into product Settings.  
- Pressure to add backend/settings-API Mode persistence (violates Q1).  
- Pressure to keep `/settings` as a second home (violates Q2).  
- Pressure to use non-neutral placeholder copy (violates Q3).  

**Not stop conditions:** Q1–Q3/Q5–Q7 — **resolved**. Implementation blockers from Open Questions are **removed**.

---

**End of S001 Implementation Package**

*S001 IMPLEMENTATION PACKAGE FROZEN — READY FOR STEP 068 IMPLEMENTATION*
