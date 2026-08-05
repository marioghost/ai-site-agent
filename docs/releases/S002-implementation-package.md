# S002 — Implementation Package

**Step:** S002 — Knowledge product cutover  
**Program:** `docs/releases/1.0-rfc-101-master-program.md`  
**Roadmap:** `docs/releases/1.0-rfc-101-execution-roadmap.md`  
**Execution Strategy:** `docs/releases/1.0-rfc-101-execution-strategy.md`  
**Implementation HOW:** `docs/RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md`  
**Baseline commit:** `bc50607af8939092de94a7624bc0b9a66d7e3ea8`  

**Status:** **FROZEN for implementation** — authorized, scoped, and ready for Step S002 coding  
**Duration band (roadmap):** L  

---

## 1. Goal

S002 completes the **Knowledge product cutover** for Release 1.0 Dashboard Product Completion.

The exact product goal is:

1. Move the product-facing Knowledge surfaces to their RFC-101 owners:
   - Library under `/knowledge/library`
   - Update under `/knowledge/update`
   - Site under `/knowledge/site`
2. Make those canonical Knowledge screens the **sole product owners** for their jobs.
3. Convert legacy top-level entrypoints (`/sources`, `/indexing`, Knowledge Profile entrypoints) into compatibility redirects rather than parallel owners.
4. Keep Engineering Mode isolation intact by **not** moving engineering-only capabilities in this Step.

S002 is a **product ownership migration Step**, not a deploy/remediation Step, not an Engineering Mode isolation Step, and not a backend Step.

---

## 2. Scope

### In scope package IDs

| Identifier | Purpose | User-visible result | Dependencies | Completion criteria |
|------------|---------|---------------------|--------------|---------------------|
| `G4-P1` | Library becomes the product owner for browse/coverage knowledge workflows | Users navigate to a real Library screen under `/knowledge/library`; old Sources surface no longer acts as a parallel top-level owner | Hard: S001 canonical Knowledge routes/layout substrate; soft: `G8-P2` | `/knowledge/library` is the product browse owner, legacy `/sources` redirects compatibly, and no second product-level Sources owner remains |
| `G4-P2` | Update becomes the product owner for refresh/indexing workflows | Users manage refresh/update work under `/knowledge/update`; old Indexing surface no longer owns the product job | Hard: S001 Knowledge routes; soft: `G4-P1` | `/knowledge/update` is the unique product refresh owner, `/indexing` redirects compatibly, and refresh ownership is not duplicated |
| `G4-P3` | Site becomes the product owner for site identity / knowledge profile workflows | Users manage site-level identity under `/knowledge/site`; Knowledge Profile legacy entrypoints no longer remain as top-level product owners | Hard: S001 Knowledge routes; soft: `G4-P1` | `/knowledge/site` is the canonical owner, Knowledge Profile routes redirect compatibly, and no top-level KP owner remains |
| `G1-P2` (S002 slice) | Apply redirect increments for retired Knowledge legacy paths | Legacy bookmarks keep working while canonical Knowledge routes become authoritative | Hard: `G4-P1/P2/P3` ownership decisions | Legacy Knowledge paths resolve via redirects to canonical owners without duplicate product ownership |
| `G8-P2` (S002 slice) | Migrate touched Knowledge product code into RFC-102 target structure | New/updated Knowledge screens live in `features/knowledge/*`, thin pages, layouts, and shared modules instead of growing legacy monoliths | Standing authority: RFC-102 | All new or migrated S002 owners land in RFC-102-compliant locations; no permanent new product logic is added to legacy page monoliths |

### In scope contracts

- Knowledge section product ownership only
- Canonical route ownership for Library / Update / Site
- Redirect compatibility for legacy Knowledge entrypoints
- Knowledge navigation, labels, section shell, and screen ownership
- Tests and acceptance evidence for the Knowledge cutover
- Documentation directly required by S002 evidence/review flow

### Out of scope

| Area | Reason / Owner |
|------|----------------|
| `G4-P4` Source Intelligence move to Engineering Knowledge | S006 owns engineering isolation moves |
| Insights migration (`G5-*`) | S003 |
| Settings split (`G7-*`) | S004 |
| Ask/Home migrations (`G3-*`, `G6-*`) | S005/S007 |
| Engineering content isolation | S006 |
| Overview retirement / `/` default change | S007 |
| Structure polish / cleanup / validation tooling | S008 |
| Backend APIs, persistence, schema, Alembic | Not part of S002; forbidden by product-boundary rules |
| Deploy / provenance / verify-release / smoke architecture | Frozen by accepted remediation |
| Release metadata / lifecycle semantics | Frozen |
| S003 parallel execution | Explicitly forbidden by this package request |

### Future steps (not part of S002)

- S003: Insights product cutover
- S004: Settings product split
- S005: Home shell + Ask coexistence shell
- S006: Engineering isolation moves
- S007: Home default + Overview retirement
- S008: cleanup, validation, tooling, remaining product evidence hygiene

---

## 3. Architecture impact

### Allowed layers to change

| Layer / concern | Allowed S002 impact |
|-----------------|---------------------|
| Routing | Canonical Knowledge routes remain authoritative; legacy Knowledge entrypoints become redirects |
| Navigation | Sidebar / section navigation labels, ordering, and destinations for Knowledge only |
| React components | Knowledge screens, Knowledge widgets, thin route adapters, layouts touched by Knowledge ownership |
| Page ownership | Transfer Sources/Indexing/KP product ownership to Library/Update/Site |
| Menus / sidebar | Remove duplicate top-level Knowledge owners; point users to canonical owners |
| Placeholders | Replace S001 scaffold-level placeholders only for S002-owned Knowledge destinations |
| Knowledge screens | Library / Update / Site product screens and their feature-local widgets |
| Source / indexing entrypoints | Compat redirects and owner cutover only |
| Tests | Ownership, redirect, nav, compatibility, runtime evidence support |
| Documentation | This package, S002 evidence artifacts, review records directly tied to S002 |

### Forbidden areas

- Deployment scripts and deploy workflow
- Provenance generation or verification logic
- `verify_release.sh`, `smoke-staging.sh`, release-check remediation behavior
- Backend APIs, schema, Alembic, DB data model
- Release metadata, `APP_RELEASE`, lifecycle semantics
- RFC-100, Step 067, remediation law, or accepted evidence
- Engineering Mode destinations outside what is needed to preserve current behavior
- Moving Source Intelligence / diagnostics / advanced controls into or out of Engineering Mode
- Starting S003 or bundling S003 work into S002

### Architectural invariants

1. RFC-101 defines product ownership; S002 implements it, does not reinterpret it.
2. RFC-102 defines structure; migrated Knowledge owners must land in target feature/layout/page layers.
3. Legacy and final may coexist only as **redirect + final owner**, not as dual product owners.
4. Engineering Mode isolates complexity; S002 must not leak engineering surfaces into default product.

---

## 4. Files expected to change

Paths are expected from the accepted S001 baseline plus RFC-102 targets. Final implementation may vary slightly in filenames, but must remain inside these boundaries.

### Required

- `dashboard/src/App.tsx`
- `dashboard/src/layouts/KnowledgeLayout.tsx`
- `dashboard/src/lib/navConfig.ts`
- `dashboard/src/lib/permissions.ts` if route/nav permissions require explicit Knowledge owner updates
- `dashboard/src/features/knowledge/library/*`
- `dashboard/src/features/knowledge/update/*`
- `dashboard/src/features/knowledge/site/*`
- `dashboard/src/features/knowledge/shared/*` if sibling-sharing is needed
- `dashboard/src/pages/*` only for thin Knowledge route adapters if those pages exist
- `dashboard/src/i18n/en.ts`
- `dashboard/src/i18n/uk.ts`
- Knowledge-related tests under `dashboard/src/**/*test.ts*`
- S002 evidence / gate docs under `docs/releases/`

### Optional

- `dashboard/src/shared/ui/*` if Knowledge product screens need already-authorized primitive reuse or extraction
- `dashboard/src/hooks/*` if a reusable hook is used by more than one Knowledge feature
- `dashboard/src/api/resources/*` or feature-local Knowledge API modules if current fetch ownership needs clean RFC-102 placement
- `dashboard/src/types/*` for shared Knowledge DTO typing only
- `dashboard/src/context/*` only if already-existing cross-cutting context wiring must be consumed, not expanded into new product architecture

### Forbidden

- `deploy/**`
- `scripts/release/**`
- `backend/**`
- `alembic/**`
- `APP_RELEASE`
- `docs/releases/S001-*remediation*`
- `docs/RFC-101-DASHBOARD-PRODUCT-SPECIFICATION.md`
- `docs/RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md`
- `docs/releases/1.0-rfc-101-execution-roadmap.md`
- Any S003/S004/S005/S006 implementation artifacts

---

## 5. Component-by-component implementation plan

### Library (`G4-P1`)

| Field | Content |
|-------|---------|
| Current behavior | S001 provides canonical `/knowledge/library` substrate and legacy Sources still represents the browse owner behavior |
| Target behavior | Library is the sole product owner for knowledge browse/coverage workflows |
| Migration strategy | Move/compose product-facing Sources behavior into Library owner screen under RFC-102 `features/knowledge/library`; legacy `/sources` becomes compatibility redirect |
| Rollback impact | Revert S002 commit(s); runtime returns to accepted S001 baseline with scaffold/canonical substrate only |
| Acceptance criteria | Library reachable via canonical nav and route; old Sources does not remain a parallel product owner; redirect compatibility proven |

### Update (`G4-P2`)

| Field | Content |
|-------|---------|
| Current behavior | S001 provides canonical `/knowledge/update` substrate while legacy Indexing still carries refresh/indexing ownership |
| Target behavior | Update is the unique product owner for refresh/update workflows |
| Migration strategy | Move product-facing indexing/refresh UX into Update owner screen; legacy `/indexing` becomes redirect-only compatibility path |
| Rollback impact | Revert S002 commit(s); accepted S001 substrate remains intact |
| Acceptance criteria | Update owns refresh job; refresh ownership is not duplicated in another top-level product surface; redirect behavior proven |

### Site (`G4-P3`)

| Field | Content |
|-------|---------|
| Current behavior | S001 provides canonical `/knowledge/site` substrate while Knowledge Profile legacy surface remains user-facing |
| Target behavior | Site becomes the sole product owner for site identity / knowledge profile responsibilities |
| Migration strategy | Move KP product-facing content into Site owner screen; convert Knowledge Profile entrypoints to compatibility redirects |
| Rollback impact | Revert S002 commit(s); S001 substrate remains the fallback baseline |
| Acceptance criteria | Site screen is the canonical owner; no top-level Knowledge Profile owner remains; compatibility redirects proven |

### Knowledge section shell

| Field | Content |
|-------|---------|
| Current behavior | S001 Knowledge layout/nav substrate exists but may still expose legacy naming or placeholder ownership |
| Target behavior | Knowledge section shell consistently points to Library / Update / Site as the section owners |
| Migration strategy | Update section sub-nav, sidebar references, labels, and route wiring to canonical Knowledge owners only |
| Rollback impact | Shell can revert without affecting deploy/remediation/runtime law |
| Acceptance criteria | Knowledge section has one owner per job and no conflicting top-level duplicate |

### Legacy entrypoints and redirects (`G1-P2` slice)

| Field | Content |
|-------|---------|
| Current behavior | Legacy paths remain bookmarkable from S001 coexistence rules |
| Target behavior | Legacy Knowledge paths stay functional through redirects, not duplicated screens |
| Migration strategy | Replace remaining legacy owner routes with redirects to final Knowledge owners while preserving deep-link compatibility where roadmap requires it |
| Rollback impact | Revert redirect changes; legacy ownership returns only via rollback to accepted baseline |
| Acceptance criteria | `/sources`, `/indexing`, and KP legacy paths no longer act as independent product owners |

---

## 6. Routing plan

| Route | Current owner | New owner after S002 | Redirect behavior | Compatibility |
|-------|---------------|----------------------|-------------------|---------------|
| `/knowledge/library` | S001 scaffold / transitional owner | Library (`G4-P1`) | None; remains canonical | Direct canonical route |
| `/knowledge/update` | S001 scaffold / transitional owner | Update (`G4-P2`) | None; remains canonical | Direct canonical route |
| `/knowledge/site` | S001 scaffold / transitional owner | Site (`G4-P3`) | None; remains canonical | Direct canonical route |
| `/sources` | Legacy Sources page | Redirect to `/knowledge/library` | Required | Bookmark compatibility preserved |
| `/indexing` | Legacy Indexing page | Redirect to `/knowledge/update` | Required | Bookmark compatibility preserved |
| Knowledge Profile legacy route(s) | Legacy Knowledge Profile owner | Redirect to `/knowledge/site` | Required | Bookmark compatibility preserved |

### Routing rules

1. No duplicate ownership between canonical and legacy pages.
2. Canonical routes stay fixed per RFC-101.
3. Legacy compatibility is allowed only as redirect behavior, not second owner behavior.
4. Catch-all behavior and `/` default are unchanged in S002.

---

## 7. Navigation plan

### Sidebar

- Knowledge family remains visible per S001/RFC-101 navigation contracts.
- Product nav must point users to:
  - Library
  - Update
  - Site
- No top-level duplicate Sources / Indexing / Knowledge Profile entries after S002 close.

### Knowledge section

- `KnowledgeLayout` owns sub-nav only.
- Sub-nav must expose canonical destinations and RFC-101 labels.
- Library = browse/coverage owner.
- Update = refresh/update owner.
- Site = site identity owner.

### Visibility rules

- Product navigation remains available with Engineering Mode off.
- Engineering-only destinations remain isolated under `/engineering/*`.
- S002 must not add engineering-only product nav entries to default product shell.

### Future placeholders

- Knowledge owners may still contain product-appropriate placeholder content only where roadmap-delayed functionality is explicitly out of S002 scope.
- Placeholder use must not conceal unresolved ownership; it is allowed only inside the final S002 owner surface.

### Engineering isolation

- No Source Intelligence, diagnostics, or engineering panels are moved in S002.
- S002 must preserve S001 Engineering Mode contracts unchanged.

---

## 8. State ownership

| Concern | S002 contract |
|---------|---------------|
| React Context | Reuse existing cross-cutting contexts only; no new app-wide product architecture is introduced without RFC-102 necessity |
| Stores / screen state | Knowledge feature-local state belongs in `features/knowledge/*`; shared state only if used by multiple Knowledge siblings |
| Navigation ownership | `navConfig.ts` remains the single source of sidebar ownership |
| Permissions | Existing permission model may be reused/updated only as needed for canonical Knowledge visibility; no new role model |
| Engineering Mode interaction | Engineering Mode continues to gate engineering routes only; S002 product Knowledge screens remain product-visible |
| Legacy compatibility | Legacy route support is via routing/redirects, not duplicated state owners |

### Ownership rules

1. Feature A must not import Feature B screens/widgets directly.
2. Knowledge-specific shared utilities may live under `features/knowledge/shared/`.
3. Global/shared extraction is allowed only when truly cross-feature, per RFC-102.

---

## 9. UI contracts

### Library page

| Contract | Requirement |
|----------|-------------|
| Purpose | Browse/coverage owner for product Knowledge workflows |
| Empty state | Must explain the product-facing absence of library content or sources in user terms |
| Loading state | Deterministic loading state, not blank shell |
| Error state | User-readable error state with retry or recovery direction using existing APIs |
| Navigation destination | Canonical destination for legacy `/sources` users |
| Placeholder policy | Allowed only for functionality explicitly deferred outside S002; not for the owner job itself |

### Update page

| Contract | Requirement |
|----------|-------------|
| Purpose | Product owner for refresh/update workflows |
| Empty state | Must explain what can be updated/refreshed and what is required before action |
| Loading state | Deterministic loading state |
| Error state | User-readable error state using existing error handling conventions |
| Navigation destination | Canonical destination for legacy `/indexing` users |
| Placeholder policy | Allowed only for deferred non-owner functionality, not the update owner contract |

### Site page

| Contract | Requirement |
|----------|-------------|
| Purpose | Product owner for site identity / knowledge profile workflows |
| Empty state | Must explain missing site/profile state in product language |
| Loading state | Deterministic loading state |
| Error state | User-readable error state |
| Navigation destination | Canonical destination for Knowledge Profile legacy users |
| Placeholder policy | Allowed only where roadmap-delayed detail is explicitly out of S002 |

### Redirected legacy routes

| Contract | Requirement |
|----------|-------------|
| Purpose | Preserve compatibility only |
| Empty state | N/A |
| Loading state | Should not present a second owner screen |
| Error state | Redirect failure is a routing defect |
| Navigation destination | Final canonical owner |
| Placeholder policy | Forbidden |

---

## 10. Backend interaction

### Existing APIs reused

S002 must reuse existing backend/dashboard APIs already used by:

- Sources / library-adjacent flows
- Indexing / refresh flows
- Knowledge Profile / site flows

### No new APIs

- No new backend endpoints
- No new database schema
- No new deploy/build identity surfaces

### Future API placeholders

- If product design requires future backend capability beyond current APIs, S002 may only document that gap in evidence/debt artifacts.
- S002 must not create fake backend abstractions to imply future work is complete.

### Forbidden backend changes

- `backend/**`
- `alembic/**`
- API contract redesign
- auth/session redesign
- release metadata changes

---

## 11. Test plan

### Requirement matrix

| Requirement | Unit | Integration | Regression | Release-check | Runtime validation | Acceptance evidence |
|-------------|------|-------------|------------|---------------|--------------------|---------------------|
| Library owns browse job | Library screen/ownership tests | Route + nav flow to `/knowledge/library` | Legacy `/sources` redirect test | Not required in release-check unless repo policy later expands product checks | Confirm runtime route + bundle markers + canonical owner | Implementation review + runtime evidence |
| Update owns refresh job | Update screen tests | Route + nav flow to `/knowledge/update` | Legacy `/indexing` redirect test | Same as above | Runtime route + owner evidence | Implementation review + runtime evidence |
| Site owns site identity | Site screen tests | Route + nav flow to `/knowledge/site` | KP legacy redirect test | Same as above | Runtime route + owner evidence | Implementation review + runtime evidence |
| No duplicate product ownership | navConfig / route ownership assertions | Sidebar + section-nav assertions | Redirect/no-top-level duplicate tests | N/A unless existing dashboard CI script aggregates it | Runtime nav/route review | Product Readiness Gate |
| RFC-102 structure on migrated screens | file/module ownership tests if present | review-level structure audit | no new legacy-page growth assertions if practical | N/A | N/A | Implementation review |
| Engineering Mode unaffected | existing S001 mode tests remain green | route guard unaffected | regression of `/engineering/*` gating | existing frontend test suite | runtime spot-check only if changed surfaces touch mode | Implementation review |
| Legacy compatibility preserved | N/A | redirect/deep-link tests | redirect permanence tests | N/A | runtime redirect confirmation | Push/deploy/runtime review |

### Required test families

1. **Unit**
   - Library / Update / Site screen contracts
   - nav ownership and label assertions
   - permissions visibility where applicable

2. **Integration**
   - Route ownership for canonical Knowledge pages
   - Redirect behavior from `/sources`, `/indexing`, KP legacy routes
   - Sidebar and Knowledge sub-nav contract

3. **Regression**
   - No duplicate top-level Sources / Indexing / KP owner surfaces
   - Engineering Mode behavior unaffected
   - Existing S001 routing coexistence not regressed outside S002-owned paths

4. **Release-check**
   - S002 is a product Step; no deploy-architecture release-check change is authorized by this package
   - If repo already includes dashboard test execution in release-check, those existing gates must stay green

5. **Runtime validation**
   - Runtime identity aligned to deployed S002 tip
   - Canonical Knowledge routes reachable
   - Legacy redirects proven
   - Health/deploy/remediation protections still pass unchanged

6. **Acceptance evidence**
   - Product Readiness Gate result: PASS or PASS WITH DEBT
   - Screenshots or equivalent UI evidence for Library / Update / Site owners
   - Redirect evidence
   - No duplicate nav owner evidence

---

## 12. Previous-step protection

S002 must **not** modify:

- Phase 1 publication
- Phase 2 verify-release
- Phase 2 smoke
- Deployment workflow
- Frontend provenance generation/verification
- Frontend identity semantics
- Backend deployment behavior
- RFC-100
- Step 067
- Release lifecycle semantics or metadata
- Accepted remediation evidence

S002 is a Dashboard product cutover only.

---

## 13. Risks

| Risk class | Risk | Detection | Mitigation | Rollback |
|------------|------|-----------|------------|----------|
| Implementation | Library / Update / Site accidentally remain partial wrappers around old owners | Ownership tests, route review, nav review | Make canonical Knowledge screens the only product owners; use redirects for legacy | Revert S002 commit(s) |
| Migration | Duplicate top-level nav entries survive close | navConfig diff, runtime nav check | Remove duplicate entries before acceptance | Revert nav changes |
| Compatibility | Legacy bookmarks break | redirect integration/runtime tests | Explicit redirect matrix and route tests | Restore legacy route behavior via rollback |
| Regression | S001 Engineering Mode or unrelated routes regress | existing dashboard tests, S001 mode regression tests | Limit scope to Knowledge surfaces; keep mode wiring untouched | Revert S002 commit(s) |
| Structure | New code grows legacy `pages/` monoliths instead of RFC-102 features | implementation review | Enforce thin pages + feature owners | Refactor before acceptance or rollback |
| Product | Product copy leaks engineering terminology into default Knowledge screens | product review against RFC-101 glossary | Use glossary/i18n contract only | Fix before acceptance |

---

## 14. Acceptance criteria

S002 passes only if all conditions below are true:

1. `/knowledge/library`, `/knowledge/update`, and `/knowledge/site` are the sole product owners for their respective Knowledge jobs.
2. `/sources`, `/indexing`, and Knowledge Profile legacy entrypoints no longer act as independent top-level product owners.
3. Legacy Knowledge entrypoints remain usable through explicit compatibility redirects.
4. Sidebar and Knowledge section navigation expose canonical Knowledge owners without duplicate ownership.
5. New or migrated S002 product code lands in RFC-102-compliant feature/layout/page structure.
6. No deploy/provenance/verify-release/smoke/remediation architecture changes are introduced.
7. Existing backend/schema/release metadata remain unchanged.
8. Required tests for ownership, redirects, and compatibility pass.
9. Product Readiness Gate records PASS or PASS WITH DEBT with only explicitly accepted debt.

---

## 15. Evidence required

### Implementation review must demonstrate

- Only S002 package IDs are implemented
- Correct owner transfer for Library / Update / Site
- Redirect matrix complete for S002-owned legacy routes
- RFC-102 placement followed
- No S003/S004/S005/S006 scope leakage

### Commit review must demonstrate

- Commit scope limited to S002-owned frontend/tests/docs artifacts
- No deploy/backend/remediation/lifecycle files included
- Message coherence: Knowledge product cutover only

### Push review must demonstrate

- Published range contains only the approved S002 commit set
- Fast-forward only
- Repository clean and synchronized

### Deployment review must demonstrate

- Standard deploy path only
- No deployment law changes required for S002
- Runtime identity target is the S002 tip

### Runtime validation must demonstrate

- Runtime identities aligned to deployed S002 tip
- Library / Update / Site routes live
- Legacy redirects work as specified
- Health/deploy/remediation protections remain valid

### Final acceptance must demonstrate

- All S002 acceptance criteria satisfied
- Remaining debt, if any, is explicitly outside S002 completion
- S001 and remediation remain accepted and unchanged

---

## 16. Deliverables

### Implementation

- Knowledge Library product owner screen
- Knowledge Update product owner screen
- Knowledge Site product owner screen
- Redirect wiring for `/sources`, `/indexing`, and KP legacy entrypoints
- Canonical Knowledge nav ownership

### Tests

- Ownership tests
- Redirect tests
- Knowledge nav/route compatibility tests
- Regression coverage proving no duplicate Knowledge owner remains

### Documentation

- This package
- S002 implementation evidence
- S002 Product Readiness Gate record
- Any accepted debt/evidence records directly required by S002

### Deployment evidence

- Standard deployment report for S002 tip
- Runtime validation evidence for canonical Knowledge ownership and redirects

### Acceptance evidence

- Implementation review
- Commit review
- Push review
- Deployment review
- Runtime validation review
- Final acceptance review

---

## 17. Non-goals

S002 will **not** solve:

- Insights migration
- Settings split
- Ask/Home productization
- Engineering isolation moves
- Overview retirement / Home default
- verify-release tooling hygiene beyond already accepted remediation
- Backend/API redesign
- New schema or data model work
- S003 work in parallel under this package

---

## 18. Final authorization

**S002 IMPLEMENTATION PACKAGE COMPLETE**

**READY FOR IMPLEMENTATION**

**STOP.**
