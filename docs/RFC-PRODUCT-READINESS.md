# RFC — Product Readiness Program

**Status:** Architecture accepted for planning — Product Readiness Gate defined (docs); implementation of Dashboard workstreams not started  
**Nature:** Cross-cutting product quality program (not a release number)  
**Enforcement:** Product Readiness Gate (§6) — mandatory before Feature Acceptance  
**Runs:** **In parallel with Release 1.0 engineering** (RFC-100 Steps 063–067)  
**Baseline:** Release 0.9 engineering complete and deployed (`APP_RELEASE=0.9`)  
**Authority:** Mandatory acceptance layer for Release 1.0 Accepted Product  
**Companion execution roadmap:** `docs/RFC-100-PRODUCTION-MIGRATION-STRATEGY.md`  
**Lifecycle:** `docs/LIFECYCLE.md`  
**Dashboard product SoT (WHAT):** `docs/RFC-101-DASHBOARD-PRODUCT-SPECIFICATION.md`  
**Dashboard implementation SoT (HOW):** `docs/RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md`

### Document ownership (normative)

| Document | Owns | Does not own |
|----------|------|--------------|
| **This RFC (Product Readiness)** | Program, Gate, Product Debt, Feature/Release product acceptance policy | Dashboard IA, navigation, screen contracts, terminology, feature modules |
| **RFC-101** | Dashboard architecture, navigation, IA, terminology, screen inventory, Screen Contracts, ownership matrices | Gate process mechanics; folder/state implementation |
| **RFC-102** | Dashboard implementation architecture (folders, routing, state, shared UI, tests) | Product IA or Gate policy |
| **RFC-100** | Engineering migration steps and capabilities | Dashboard product UX redesign |

This RFC **may reference** RFC-101. It **must not** redefine Dashboard architecture.

---

## Executive framing

Release 0.9 engineering is complete. The platform architecture is stable. Deployment and maintenance architectures are complete.

The Dashboard, however, still behaves as an **engineering console**. That gap is **not** fixed by delaying RFC-100 Step 063, inventing “Release 0.95,” or treating UX as Phase 0.

**Product Readiness does not replace Release 1.0.**

```
Release 1.0 Engineering  +  Product Readiness  =  Release 1.0 Accepted Product
```

Every Release 1.0 feature must satisfy **both**:

1. **Functional Acceptance** (RFC-100 engineering Definition of Done)
2. **Product Readiness Acceptance** via the **Product Readiness Gate** (`PASS`, `PASS WITH DEBT`, or `N/A`)

A feature is **not complete** until both are satisfied.  
Release 1.0 is **not accepted** until both programs are complete **and** Gate debt policy is satisfied.

This is **not**:

- a separate release
- a pause between 0.9 and 1.0
- work that starts only after 1.0 engineering ends
- a substitute for RFC-100 Steps 063–067

This **is**:

- a permanent product quality acceptance layer
- executed **in parallel** with Release 1.0 implementation
- required for Release 1.0 Definition of Accepted

---

## 1. Product Readiness Program (permanent architecture section)

### 1.1 Definition

**Product Readiness Program** is a cross-cutting product quality program that runs alongside Release 1.0 implementation.

Its purpose is to ensure Release 1.0 is not only **technically complete**, but also **production-ready from the user’s perspective**.

### 1.2 Scope

| In scope | Out of scope |
|----------|--------------|
| Dashboard UX | Backend cognitive architecture redesign |
| Navigation & Information Architecture | Retrieval / Memory / Maintenance engines |
| Design system & terminology | Deployment architecture changes |
| Engineering Mode isolation | Changing RFC-100 step order or Step 063+ functional intent |
| Simplicity audits & product validation | Rewriting historical Release 0.9 acceptance docs |
| Product acceptance of Release 1.0 surfaces | Setting `staging_validated` / `production_ready` without ops gates |

### 1.3 Parallel architecture

```
Release 0.9 (Engineering Ready + deployed)
      │
      ▼
────────────────────────────
Product Readiness Program
────────────────────────────
        │
        ├── Dashboard UX
        ├── Navigation
        ├── Information Architecture
        ├── Design System
        ├── Engineering Mode
        ├── Simplicity Audit
        └── Product Validation
        │
        ├───────────────┐
        │               │
        ▼               ▼
Release 1.0 work   Product refinement
(RFC-100 063–067)  (this program)
        │               │
        └───────────────┘
                │
                ▼
     Release 1.0 Accepted Product
     (Functional + Product Readiness)
```

Release 1.0 engineering **continues exactly as planned** in RFC-100.  
Product Readiness **does not block starting** Step 063.  
Product Readiness **does block accepting** Release 1.0 (and accepting any 1.0 feature that violates product rules).

---

## 2. Product Readiness principles (normative)

| # | Principle | Meaning |
|---|-----------|---------|
| 1 | **Simplicity Outside** | Users see a calm, obvious product. |
| 2 | **Engineering Inside** | Complexity stays in architecture and Engineering Mode. |
| 3 | **One Job = One Screen** | Every screen solves exactly one user problem. |
| 4 | **No Duplicate Functionality** | One obvious place for each action. |
| 5 | **Navigation by User Intent** | Nav follows tasks, not modules/services. |
| 6 | **Progressive Disclosure** | Advanced detail appears only when needed. |
| 7 | **Consistent Visual Language** | One design system across the app. |
| 8 | **Consistent Terminology** | One customer vocabulary; no dual labels for one surface. |
| 9 | **Predictable User Flows** | Same job always follows the same path. |
| 10 | **Discoverability** | Primary jobs are findable without coaching. |
| 11 | **Minimal Cognitive Load** | No experimental/lab chrome in the default product. |
| 12 | **Product Before Engineering** | When UX and eng convenience conflict, product wins. |

Core slogan: **Simplicity Outside. Complexity Inside.**

---

## 3. Mandatory acceptance rules

No Release 1.0 feature may be **accepted** if it:

1. Creates **duplicated functionality**
2. Introduces **duplicated navigation** (two entries → one job)
3. **Exposes engineering concepts** to normal users (pipelines, retrieval knobs, shadow mode, migration flags, etc.)
4. **Breaks Information Architecture** (module-shaped nav, orphan screens, conflicting homes for one job)
5. **Increases dashboard complexity** without a corresponding simplification elsewhere
6. Violates any Product Readiness principle in §2
7. Requires demo language such as: “temporary”, “ignore this”, “testing only”, “engineers only”, “don’t use yet”, “redesign later”
8. Leaves **invisible product debt** (undeclared debt)

**Enforcement:** The **Product Readiness Gate** (§6) is the official enforcement mechanism. Informal assertion is insufficient. Engineering green alone is insufficient for Release 1.0 feature Done.

---

## 4. Engineering Mode (permanent architectural concept)

Engineering functionality is **not removed**.

It becomes:

- **isolated** from the default product chrome
- **optional**
- **hidden** from standard users
- **enabled intentionally** (admin preference / explicit toggle)

### Rules

| Rule | Detail |
|------|--------|
| Default | **Off** for all roles, including Owner (RFC-101: Mode is orthogonal to role) |
| Ownership | **RFC-101** owns Engineering Mode placement, routes, and screen contracts. Toggle owner = **Settings → General**. Engineering destinations = **`/engineering/*`** |
| When off | No Engineering nav; no pipeline/retrieval dumps in product chrome; no epistemic experimental page in primary nav; no migration/flag matrices in product Settings |
| When on | **Engineering** area appears (RFC-101). Ask may expose progressive “Details” only as RFC-101 allows; eng internals stay under Engineering — **not** under product Settings as an “Advanced” product destination |
| Capability | Mode **reveals** existing capabilities — it does **not** invent new backend powers by itself |
| Demo bar | A customer demo must succeed with Engineering Mode **off** |

Normal product users interact only with the simplified product interface defined in **RFC-101**.

The Gate (§6) must verify Engineering Mode isolation whenever a change touches eng-facing UI, using **RFC-101** as the product rule source.

---

## 5. Dashboard product architecture — reference only (not SoT)

**This section is not a second Dashboard specification.**

| Concern | Authority |
|---------|-----------|
| Information Architecture, navigation, routes, terminology | **RFC-101** |
| Screen Contracts, ownership matrices, capability disposition | **RFC-101** |
| Folder structure, React Query, shared UI, feature modules | **RFC-102** |
| Product Readiness principles, Gate, debt, acceptance | **This RFC** |

**Conceptual illustration (non-normative — names must match RFC-101):**

Product (Mode off): Home · Knowledge (Library / Update / Site) · Ask · Insights (Performance / Activity) · Settings (General / Models / Answers / Access).  
Engineering Mode on: additive **Engineering** destinations per RFC-101 (status, ask-details, knowledge internals, tensions, advanced, build & flags).

Do **not** implement Dashboard UX from this sketch or from Appendices alone. Implement from **RFC-101** (+ **RFC-102** for structure).

Historical Release 0.9 as-built inventory remains in **Appendix A–C** (audit input only). Appendices do **not** redefine target IA.

---

## 6. Product Readiness Gate (official enforcement mechanism)

### 6.1 Architectural rationale

Principles (this RFC), Dashboard IA/ownership (**RFC-101**), Engineering Mode (**RFC-101**), and dual DoD/Accepted define **WHAT** product acceptance requires.

Without a per-change process, Release 1.0 can remain RFC-100-compliant while the Dashboard slowly regresses into an engineering console.

The **Product Readiness Gate** is the missing **HOW**: a lightweight, mandatory checkpoint on every Release 1.0 change that could affect the product surface.

| The Gate is | The Gate is not |
|-------------|-----------------|
| Process inside Product Readiness | A new release / RFC number / 0.95 |
| Enforcement joint with RFC-100 | A redesign of RFC-100 Steps 063–067 |
| Human checklist + short record | A new eng subsystem, deploy stage, or CI bot |
| Scoped to **this change** (+ global product impact of **this** change) | A mandate to redesign unrelated Dashboard areas |

### 6.2 Architecture diagram

```
Release 0.9
      │
      ▼
┌─────────────────────────────────────┐
│     Product Readiness Program       │
│  principles · Gate · debt policy    │
│  (Dashboard IA owned by RFC-101)    │
│           ┌─────────────────┐       │
│           │  PR Gate (§6)   │       │  ← enforcement mechanism
│           └────────┬────────┘       │
└────────────────────┼────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
Release 1.0 engineering    Product refinement
(RFC-100 063–067)          (per RFC-101 / workstreams)
        │                         │
        └────────────┬────────────┘
                     ▼
        Feature Acceptance requires:
          Functional ∧ Gate ∈ {PASS, PASS WITH DEBT, N/A}
                     │
                     ▼
          Release 1.0 Accepted Product
          (Program complete ∧ no open must-resolve debt)
```

### 6.3 Responsibilities

| Does | Does not |
|------|----------|
| Classify surface impact | Redesign IA or RFC-100 |
| Evaluate five areas (§6.5) | Replace `make release-check` |
| Emit PASS / PASS WITH DEBT / FAIL / N/A | Become a deploy stage |
| Record Product Debt explicitly | Require unrelated screen redesigns |
| Block Feature Acceptance on FAIL | Block **starting** Step 063 |
| Verify product state **after** the change | Invent new Knowledge OS / deploy architecture |

### 6.4 Execution point

```
Draft → Implementation → Tests / Review / Fixes
                              │
                              ▼
                    Product Readiness Gate   ← before Feature Acceptance
                              │
                              ▼
         Engineering Ready / Feature Done (if Gate allows)
                              │
                              ▼
              Workflow step 6 Acceptance → merge → …
```

| Timing | Rule |
|--------|------|
| Before Feature Acceptance | **Mandatory** for every Release 1.0 change |
| Workflow | Release Engineering Workflow **step 6** = Functional Acceptance **∧** Gate result |
| Lifecycle | Required to exit Implementation → Engineering Ready when surfaces are user-facing (or record N/A) |
| Start Step 063 | **Not blocked** by incomplete Product Readiness Program work |

**Cost target:** backend-only **N/A** &lt; 1 minute; user-facing Gate ≈ effort of a good PR description.

### 6.5 Five evaluation areas

The Gate evaluates **only the current change**, but area 3 judges the **product after applying that change**.

#### 1. Feature Review

- Is the feature implemented correctly for its stated job?
- Does it solve **exactly one** user job?

#### 2. Architecture Review

- Does the change follow the approved Dashboard IA in **`RFC-101`** (this RFC does not own IA)?
- Does it respect Product Readiness principles (§2)?
- Does it belong **exactly** where the **RFC-101 owner screen** says it belongs (or Engineering Mode only per RFC-101)?
- **Mandatory:** Does this change move the Dashboard **closer to RFC-101**, or away from it? Away ⇒ **FAIL**.

#### 3. Global Product Impact

After applying this change, is the overall Dashboard **better or worse**?

Verify at least:

- navigation complexity
- duplicated functionality
- duplicated terminology
- additional cognitive load
- Engineering Mode isolation
- Simplicity Outside
- **RFC-101** One-Place Register and anti-patterns

#### 4. Product Debt Assessment

Every change must declare Product Debt (§6.7). Invisible debt is forbidden.

#### 5. Decision

Record exactly one result: **PASS** | **PASS WITH DEBT** | **FAIL** | **N/A**.

### 6.5a Automatic FAIL (Dashboard / RFC-101)

For any change that touches Dashboard routes, nav, copy, or settings chrome, Gate **MUST FAIL** if it:

1. Introduces **new duplication** of an Owner screen (`RFC-101` Feature Ownership Matrix)  
2. Adds a product route/nav item **not** listed in `RFC-101` Navigation Ownership Matrix (without accepted RFC-101 update first)  
3. Reintroduces **removed product vocabulary** into default chrome  
4. Violates a Screen Contract **Forbidden** list in `RFC-101`  
5. Exposes engineering terminology in the **default** product  
6. Pollutes navigation (extra top-level items, dual labels for one route)  
7. Creates **undeclared** product debt  
8. Puts charts on Home, a second model manager, a second history home, answer knobs outside Answers, or update ownership outside Update  
9. Deletes or delays an RFC-100 capability instead of integrating it into product behavior  

Use the **Product Acceptance Checklist** in `RFC-101` §29 in the Gate record for Dashboard PRs.

### 6.6 Decision definitions

| Result | Meaning | Feature Acceptance |
|--------|---------|--------------------|
| **PASS** | All five areas compliant; Product Debt = **none** | Allowed |
| **PASS WITH DEBT** | Compliant enough to accept the change; Product Debt recorded as **accepted** or **must be resolved before Release 1.0 Acceptance** | Allowed (debt tracked) |
| **FAIL** | Violates mandatory rules, worsens the product without mitigation, or hides debt | **Blocked** |
| **N/A** | Backend-only / non-user-facing; no Dashboard nav, chrome, copy, settings UX, or customer-facing docs flows | Allowed (functional track only) |

**N/A** requires a one-line justification (e.g. “backend flag default only; no Dashboard diff”).

**FAIL** examples: second nav entry for an existing job; eng flags in default Settings; “temporary” demo language required; global impact clearly worse with no compensating simplification.

### 6.7 Product Debt policy

| Debt class | Meaning |
|------------|---------|
| **none** | No residual product debt from this change |
| **accepted** | Known debt, explicitly accepted for now; does **not** by itself block Release 1.0 Acceptance (still visible) |
| **must be resolved before Release 1.0 Acceptance** | Debt that **blocks** Release 1.0 Accepted Product until cleared |

Rules:

1. Every Gate record must state Product Debt (including **none**).
2. **Invisible product debt is not allowed.**
3. **PASS** ⇒ debt class **none**.
4. **PASS WITH DEBT** ⇒ debt class **accepted** or **must be resolved…**, with a one-line description and owner/workstream if known.
5. Open items of class **must be resolved before Release 1.0 Acceptance** block release Acceptance until resolved or reclassified with justification.
6. Debt does **not** excuse FAIL conditions (duplication, eng leak into default product, etc.).

### 6.8 Gate record (output)

Minimal durable record (PR body, step note, or acceptance appendix):

```text
Product Readiness Gate
  change: <id / PR / step slice>
  surface: none | engineering_mode | primary_product
  1_feature: …
  2_architecture: …
  3_global_impact: better | worse | neutral — …
  4_product_debt: none | accepted | must_resolve_before_1_0_acceptance — …
  5_decision: PASS | PASS WITH DEBT | FAIL | N/A
  rfc101_compliance: pass | fail | n/a
  owner_screen: <from RFC-101 §11 or n/a>
```

### 6.9 Migration from prior Product Readiness architecture

| Before | After |
|--------|-------|
| Principles + DoD + “record acceptance” (unspecified) | Same principles + **Gate** as named enforcement |
| Informal Product Readiness claims | Gate record required |
| End-of-release audit only | Continuous Gate **and** end-of-release Program completion |
| No debt vocabulary | Explicit Product Debt classes |

No change to RFC-100 step order, deploy architecture, or Release 0.9 history.

---

## 7. Definition of Done (Release 1.0 features)

A Release 1.0 feature is **DONE** only if **all** of the following are true:

### Functional (RFC-100)

- [ ] Engineering complete per step/ADR scope
- [ ] Tests pass (`make release-check` / required gates)
- [ ] Documentation updated for functional change
- [ ] Flags/rollback/observability per RFC-100 and charter

### Product Readiness (this RFC)

- [ ] **Product Readiness Gate** recorded with result **PASS**, **PASS WITH DEBT**, or **N/A**
- [ ] If not N/A: principles (§2) and **RFC-101** IA/ownership/Screen Contracts satisfied for touched surfaces — or Engineering Mode only per RFC-101
- [ ] Visual consistency verified for touched surfaces
- [ ] No duplicated functionality or navigation introduced (or Gate FAIL)
- [ ] No new engineering concepts exposed to normal users
- [ ] Product Debt declared (§6.7); none invisible

**Incomplete if:** only the functional checklist is green, or Gate is missing / FAIL.

---

## 8. Definition of Accepted (Release 1.0)

Release 1.0 **cannot be accepted** until:

- [ ] All RFC-100 Release 1.0 functionality completed (Steps 063–067 intent)
- [ ] **AND** Product Readiness Program completed (IA finalized, simplicity principles satisfied, Engineering Mode isolation complete, product validation passed)
- [ ] **AND** Dashboard satisfies simplicity principles without developer coaching
- [ ] **AND** Information Architecture is finalized
- [ ] **AND** Engineering functionality is properly isolated
- [ ] **AND** every included user-facing change has Gate **PASS**, **PASS WITH DEBT**, or **N/A** (no open **FAIL**)
- [ ] **AND** no open Product Debt of class **must be resolved before Release 1.0 Acceptance**

```
RFC-100 Functional Acceptance
        ∧
Product Readiness Program complete
        ∧
Gate compliance (no FAIL; must-resolve debt cleared)
        =
Release 1.0 Accepted Product
```

**Engineering Ready** for individual 1.0 slices: functional gates pass **and** Gate ∈ {PASS, PASS WITH DEBT, N/A}.  
Ops gates (`staging_validated`, `production_ready`) remain separate per `LIFECYCLE.md`.

---

## 9. Workstreams (parallel with Release 1.0)

| Workstream | Purpose |
|------------|---------|
| Dashboard UX | Rebuild screens to one-job surfaces |
| Navigation | Intent-based nav; remove duplicate entries |
| Information Architecture | Execute **RFC-101** IA; redirects from legacy routes per RFC-101 |
| Design System | One visual language; shared empty/loading/error |
| Engineering Mode | Permanent isolation mechanism |
| **Product Readiness Gate** | Continuous enforcement on each change |
| Simplicity Audit | Feeds Gate area 3 / Program completion |
| Product Validation | First-time user / cold demo without coaching |

These run **alongside** Steps 063–067 — not as Phase 0, not as 0.95, not after GA engineering.

---

## 10. Relationship to RFC-100

| Topic | Rule |
|-------|------|
| Step order 063–067 | Unchanged |
| Starting Step 063 | **Allowed** while Product Readiness is in progress |
| Accepting a 1.0 feature | Requires Gate ∈ {PASS, PASS WITH DEBT, N/A} |
| Accepting Release 1.0 | Requires §8 |
| Cognitive / Memory / Retrieval redesign | Still ADR + RFC-100 — not this program |
| Historical 0.9 docs | Not rewritten by this RFC |

---

## 11. Current product readiness assessment (audit baseline)

| Criterion | Status |
|-----------|--------|
| Engineering 0.9 deployed | Pass |
| Product IA customer-ready | Fail |
| Zero duplication | Fail |
| Engineering isolated | Fail |
| First-time usability without coaching | Fail |
| Visual consistency | Partial / Fail |
| Product Readiness Gate (process) | **Defined** — ready for architecture review / adoption in 1.0 practice |

**Verdict:** Release 1.0 engineering may proceed per RFC-100. Release 1.0 **Accepted Product** remains blocked until Product Readiness Program completes; continuous enforcement is via the Gate.

---

## 12. Next planning actions (architecture only)

1. Architecture-review this Gate definition.  
2. Treat **RFC-101** as locked Dashboard product SoT (no parallel IA in this RFC).  
3. Use Gate records on every Release 1.0 PR / step slice once 1.0 work starts.  
4. Run Product Readiness workstreams **in parallel** with Step 063 — Gate does not delay *starting* engineering.

---

# Appendix A — Historical Dashboard audit (Release 0.9 as-built)

**Historical only.** Does not define target IA. Target homes use **RFC-101** product vocabulary.

Source inventory: `dashboard/src/App.tsx`, `AppSidebar.tsx`, `pages/*` (Release 0.9 tree).

### Decision legend

| Decision | Meaning |
|----------|---------|
| **Keep** | Remains a first-class product screen (may still need polish) |
| **Redesign** | Same job, new IA/UX per RFC-101 |
| **Merge** | Absorb into another RFC-101 owner screen |
| **Engineering Mode** | Available only when Engineering Mode is on (RFC-101 `/engineering/*`) |
| **Remove** | Delete from product chrome |

### Summary

| Current screen (historical) | Decision | Target home (RFC-101) |
|-----------------------------|----------|------------------------|
| Login | Keep | Auth / Sign in |
| Overview | Redesign | **Home** |
| Indexing | Merge | **Knowledge → Update** |
| Sources | Merge | **Knowledge → Library** |
| Chat Test | Redesign | **Ask** |
| Chat Diagnostics (nav) | Remove / Engineering | **Engineering → Ask details** (not product nav) |
| Analytics | Redesign | **Insights → Performance** |
| Logs | Merge | **Insights → Activity** |
| Epistemic Health | Engineering Mode | **Engineering → Knowledge tensions** |
| Understanding alias | Remove | — |
| Knowledge Profile | Redesign | **Knowledge → Site** |
| Agent Settings | Redesign | **Settings** (General / Models / Answers) + **Engineering** for eng controls |
| Users | Keep (place) | **Settings → Access** |

---

# Appendix B — Historical duplication report (Release 0.9)

**Historical only.** Resolutions name **RFC-101** owners.

| Duplicate | Instances | Resolution (RFC-101) |
|-----------|-----------|----------------------|
| Chat product vs Chat diagnostics | Two nav items → one route | Single **Ask**; diagnostics in **Engineering** |
| Start / pending index | Overview, Indexing, Sources | One **Update** action |
| Reindex | Indexing, Sources, KP, Settings hints | Owned by **Update** |
| Source Intelligence generate | Indexing + Sources panels + Settings | **Engineering** surfaces |
| Quality presets vs retrieval profiles | Settings simple + eng | Customer modes on **Answers** only |
| LLM/model management | Overview + Settings | **Settings → Models** |
| Build / migration identity | Settings + Overview + Epistemic | **Engineering → Build & flags** |
| Conversation history | Logs + Chat history + Analytics | **Insights → Activity** |

---

# Appendix C — Historical as-built nav & roles (Release 0.9)

**Historical nav (as-built):** Overview · Indexing · Sources · Chat Test · Analytics · Logs · Diagnostics{Epistemic Health, Chat Diagnostics} · Users · Knowledge Profile · Agent Settings

| Role (historical) | Sees |
|-------------------|------|
| viewer | Overview, Analytics, Logs |
| operator | + Indexing, Sources, Chat |
| admin | + Users, Knowledge Profile, Epistemic Health, Settings |

**Target roles/routes:** Owner / Operator / Viewer with Engineering Mode orthogonal to role — **RFC-101** §2 / §2.1 (not this appendix).
