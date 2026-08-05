# S007 — Implementation Package

**Step:** S007 — Home default + Overview retirement
**Program:** `docs/releases/1.0-rfc-101-master-program.md`
**Roadmap:** `docs/releases/1.0-rfc-101-execution-roadmap.md`
**Execution Strategy:** `docs/releases/1.0-rfc-101-execution-strategy.md`
**Implementation HOW:** `docs/RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md`
**Baseline:** S006 accepted state (`docs/releases/S006-*`)

**Status:** **FROZEN for implementation** — authorized, scoped, and ready for Step S007 coding
**Duration band (roadmap):** S
**Prerequisites:** S005 (Home/Ask coexistence substrate), S006 (Engineering isolation — `EngStatusScreen`/`EngTensionsScreen` already real screens capable of absorbing Overview's remaining capabilities)

---

## 1. Goal

S007 completes the RFC-101 Home-as-default cutover by:

1. Redistributing every remaining Overview-only widget/capability to its real product or engineering owner, so no capability is lost when Overview is retired (`G6-P2`).
2. Retiring Overview as the product default: `/` and the catch-all `*` route now land on `/home`; `OverviewPage` becomes a thin redirect-compatibility shim (preserving search/hash) instead of a full page (`G6-P3`).
3. Finalizing the nav/i18n glossary cleanup so Overview is not registered as a product nav entry anywhere (`G1-P3`/`G1-P4` — verified already correct from S001, confirmed and locked here).
4. Fixing every auth/login redirect that still pointed at `/overview` (`LoginPage`, `RequireAuth`) to point at `/home`.

S007 is a **Home-default + Overview-retirement Step**. It is not a new product surface, not a backend Step, and does not reopen S001–S006 ownership beyond the narrow `/overview` → `/home` redirect-target changes explicitly listed here.

---

## 2. Frozen scope

### In scope

- `App.tsx`: `/` → `Navigate to="/home"`; catch-all `*` → `Navigate to="/home"`; `/overview` route kept registered (renders `OverviewPage`, which is now a redirect shim)
- `pages/OverviewPage.tsx`: replaced with a thin `Navigate`-based redirect wrapper to `/home`, preserving `location.search`/`location.hash` (same pattern as `pages/ChatTestPage.tsx` from S005)
- `pages/LoginPage.tsx`: post-login default destination (`from`) changed from `/overview` to `/home`
- `components/auth/RequireAuth.tsx`: role-mismatch fallback changed from `/overview` to `/home`
- `lib/permissions.ts`: `/overview` role-table entry kept unchanged (redirect-compatibility only), comment added
- `features/engineering/status/EngStatusScreen.tsx`: gains the two Overview capabilities that had no other owner — the `LlmRuntimePanel` (previously mounted only on Overview) and the Knowledge OS release/memory/knowledge-version tags (previously mounted only on Overview's build-info tag row and `OverviewKnowledgeOsPanel`)
- Tests and evidence for the cutover, plus the two frozen S001/S005 test assertions that explicitly encoded the pre-S007 `/` → `/overview` behavior

### Out of scope (forbidden in this package)

| Area | Reason / Owner |
|------|----------------|
| Deleting `components/overview/*` widget files that remain referenced by other live code or by frozen tests (`OverviewHeader` used by `UpdateScreen`; `OverviewKpiCard` used by `SourceSummaryCard`; `OverviewKnowledgeOsPanel` read by `step065Ownership.test.ts`; `SubsystemHealthPanel`/icons used by `EngStatusScreen`) | Deleting would either break a live product surface or a frozen prior-step test; RFC-102 duplication-ban exception is for *dead* code only |
| Home ownership changes | Completed in S005; frozen |
| Ask route/chat-chrome ownership | Completed in S005/S006; frozen |
| Settings ownership | Completed in S004; frozen |
| Knowledge ownership (Library/Update/Site) | Completed in S002; frozen |
| Insights ownership (Performance/Activity) | Completed in S003; frozen |
| Engineering isolation structure | Completed in S006; frozen — S007 only adds two widgets to the existing `EngStatusScreen` |
| Backend APIs, persistence, schema, Alembic | Forbidden |
| Deploy / provenance / verify-release / smoke architecture | Frozen by accepted remediation |
| Commit / push / deploy | Explicitly forbidden for this task — implementation only |

### Future steps (not part of S007)

- S008: cleanup, validation, tooling, remaining product evidence hygiene

---

## 3. Package IDs

| Identifier | Purpose | User-visible result | Dependencies | Completion criteria |
|------------|---------|---------------------|--------------|---------------------|
| `G6-P2` | Redistribute Overview widgets | No capability Overview used to host is lost; each has a real owner (Performance for analytics, Library/Home for knowledge readiness, EngStatus for subsystem health + LLM runtime + release/version tags, EngTensions + epistemic-health page for tensions) | Soft: S002/S003/S005/S006 ownership | Every widget class previously mounted only on `OverviewPage` has at least one live mount point outside Overview |
| `G6-P3` | Retire Overview default | `/` and `*` land on `/home`; `OverviewPage` is a redirect-only compatibility shim preserving search/hash; `LoginPage`/`RequireAuth` redirects go to `/home` | Hard: `G6-P2` (must redistribute before emptying) | `App.tsx` has no `Navigate to="/overview"`; `OverviewPage.tsx` source is a `Navigate` wrapper only; `/overview` remains routable |
| `G1-P3`/`G1-P4` (finalize) | Nav glossary/i18n lock-in | Product nav has no Overview entry; Home/Library/Update/Site/Ask/Performance/Activity/Settings remain the only product nav children | None — already satisfied since S001/S005; verified and covered by test here | `PRODUCT_NAV` has no `/overview` or `nav.overview` entry (confirmed unchanged) |

---

## 4. Architecture impact

### Allowed layers to change

| Layer / concern | Allowed S007 impact |
|-----------------|---------------------|
| Routing | `App.tsx` (`/` and `*` redirect targets only — no new routes, no removed routes) |
| Pages | `pages/OverviewPage.tsx` (full rewrite to redirect shim), `pages/LoginPage.tsx` (one-line default destination) |
| Auth | `components/auth/RequireAuth.tsx` (one-line fallback destination) |
| Permissions | `lib/permissions.ts` (comment only — no role-table value changes) |
| Engineering | `features/engineering/status/EngStatusScreen.tsx` (adds `LlmRuntimePanel` + release/version tags — additive only) |
| Tests | New `s007HomeDefaultOverview.test.ts`; narrow assertion updates in `s005HomeAskCutover.test.ts` and `s001EngineeringMode.test.ts` that explicitly encoded the pre-S007 `/`→`/overview` behavior |
| Documentation | This package, S007 evidence artifacts |

### Forbidden areas

- Deployment scripts and deploy workflow; committing, pushing, or deploying any part of this change
- Backend APIs, schema, Alembic, DB data model
- Release metadata, `APP_RELEASE`, lifecycle semantics
- RFC-100, Step 067, remediation law, or accepted evidence
- Home ownership (S005), Ask ownership (S005/S006), Settings ownership (S004), Knowledge ownership (S002), Insights ownership (S003), Engineering isolation structure (S006) — untouched beyond the narrow `EngStatusScreen` addition in §3
- Deleting any `components/overview/*` file still referenced by live code or a frozen test (see §2 out-of-scope table)
- Removing the `/overview` route path itself (must remain routable for compatibility)

### Architectural invariants

1. RFC-101 defines product/engineering ownership; S007 completes the Home-default migration the RFC always specified, it does not reinterpret ownership.
2. No capability is deleted without a live successor — verified per-widget in §6.
3. `/overview` remains a valid, low-risk redirect target forever (bookmarks/deep links keep working) — it is retired as *default*, not removed as a *route*.
4. S001–S006 ownership remains unchanged except for the explicit, narrow deltas listed in §3 (two widgets added to `EngStatusScreen`; four redirect-target strings changed).

---

## 5. Expected production files

### Required (new)

- `dashboard/src/s007HomeDefaultOverview.test.ts`
- S007 evidence/gate docs under `docs/releases/`

### Required (modified)

- `dashboard/src/App.tsx`
- `dashboard/src/pages/OverviewPage.tsx`
- `dashboard/src/pages/LoginPage.tsx`
- `dashboard/src/components/auth/RequireAuth.tsx`
- `dashboard/src/lib/permissions.ts`
- `dashboard/src/features/engineering/status/EngStatusScreen.tsx`
- `dashboard/src/s005HomeAskCutover.test.ts` (one assertion updated — see §14)
- `dashboard/src/s001EngineeringMode.test.ts` (one assertion updated — see §14)

### Removed

- None. No `components/overview/*` file is deleted (see §2 rationale) — `OverviewPage.tsx` is rewritten in place, not deleted.

### Forbidden

- `deploy/**`, `backend/**`, `alembic/**`
- `APP_RELEASE` / release lifecycle metadata mutation
- `docs/releases/S001-*` … `S006-*` (except read-only reference)
- Frozen RFCs / roadmap rewrite
- Any S008 implementation artifacts
- Any `git commit` / `git push` / deploy invocation

---

## 6. Component ownership (G6-P2 redistribution ledger)

Every widget/capability previously mounted only on `OverviewPage` is accounted for below. None are deleted; each has a live, real owner outside Overview.

| Overview capability (pre-S007) | New/confirmed owner | Evidence |
|---|---|---|
| `AnalyticsPreviewRow` (compact stats/requests/intents preview) | `/insights/performance` (`PerformanceScreen`) — already the full, real analytics surface (KPIs, trends, popular/problematic queries, retrieval quality, source analytics, intent/topic distribution, AI insights) | Confirmed pre-existing (S003); S007 only removes the now-redundant compact preview from Overview |
| `KnowledgeBaseStatusCard` (readiness %, ready/waiting/needs_refresh/failed/skipped breakdown, total sources/chunks) | `/knowledge/library` (`SourcesSummaryCards` + `SourcesKnowledgeMiniCard`) for the detailed breakdown; `/home` (`HomeScreen` checklist) for the at-a-glance readiness state | Confirmed pre-existing (S002/S005); `LibraryScreen` already renders both widgets against the same `KnowledgeBaseStatus` shape |
| `OverviewKnowledgeOsPanel` — release/memory/knowledge-version tags | `/engineering/status` (`EngStatusScreen`) — **added in S007** (release tag already existed from S006; memory/knowledge-version tags and the in-progress badge are new in S007) | New in this package — see diff |
| `OverviewKnowledgeOsPanel` — real_open_tensions / real_claims / si_claims metrics + "open health" link | `/engineering/tensions` (`EngTensionsScreen`, real_open/real_support_deficit/real_conflict summary, S006) and `/diagnostics/epistemic-health` (`EpistemicHealthPage`, full real_claims/si_claims/memory_version metrics, pre-existing) | Confirmed pre-existing (S006 + prior); `EngTensionsScreen` links directly to the full explorer |
| `SubsystemHealthPanel` (backend/db/ollama/qdrant/indexing status) | `/engineering/status` (`EngStatusScreen`) — same shared widget, real health calls (S006) | Confirmed pre-existing (S006) |
| `LlmRuntimePanel` (LLM runtime info + benchmark) | `/engineering/status` (`EngStatusScreen`) — **added in S007** (previously mounted *only* on `OverviewPage`, orphaned once Overview is retired) | New in this package — see diff |
| Overview build/release tag row (`overview.kos.release_accepted`, `memory_version`, `knowledge_version`) | `/engineering/status` (`EngStatusScreen`) — **added in S007**, folded into the same release Alert that already showed the accepted-release tag | New in this package — see diff |
| Overview page chrome (`OverviewHeader`, `OverviewFooterNote`, refresh button) | Retired — `OverviewPage` no longer needs a header/footer since it renders nothing but a redirect | `OverviewHeader` remains as a file because `UpdateScreen` uses it independently as a generic page-header component (unrelated to Overview product ownership) |

**No widget is deleted.** `AnalyticsPreviewRow.tsx`, `KnowledgeBaseStatusCard.tsx`, and `OverviewKnowledgeOsPanel.tsx` remain in `components/overview/` as orphaned-but-present files: `OverviewKnowledgeOsPanel.tsx` is still read directly (via `?raw`) by the frozen `step065Ownership.test.ts`, and none of the three block anything by continuing to exist unmounted (same precedent S006 used for `components/settings/*` originals it copied rather than deleted).

---

## 7. Routing plan

| Route | Before S007 | After S007 |
|---|---|---|
| `/` | `Navigate to="/overview"` | `Navigate to="/home"` |
| `*` (catch-all) | `Navigate to="/overview"` | `Navigate to="/home"` |
| `/overview` | Full `OverviewPage` (widgets) | `OverviewPage` renders `Navigate` to `/home`, preserving `search`/`hash` (same pattern as `/chat` → `/ask` from S005) |
| `/home` | Real product route (unchanged) | Real product route (unchanged) — now the effective default |

No route paths are added or removed; only the `/` and `*` redirect *targets* change, and `/overview`'s *element* changes from a full page to a redirect.

---

## 8. Navigation plan

No `navConfig.ts` changes. `PRODUCT_NAV` already lists `/home` as the sole top-level landing entry (since S005) and has never listed `/overview` (verified in §3 `G1-P3`/`G1-P4`). The unused `nav.overview` i18n key is left in place (harmless, not wired into any nav — removing it is out of scope and not required by any test or product surface).

---

## 9. State management plan

- `OverviewPage`: no state — pure `Navigate` redirect component, matching `ChatTestPage`
- `EngStatusScreen`: no new state; `LlmRuntimePanel` manages its own runtime/benchmark state internally (unchanged since S004/S006); the release/version tags reuse the `build` state `EngStatusScreen` already fetches via `getBuildInfo`
- No new global store introduced

---

## 10. UI/UX plan

- `OverviewPage`: renders nothing visible — immediate client-side redirect to `/home` (or `/login` first, if unauthenticated, via the existing `RequireAuth` wrapper)
- `EngStatusScreen`: release `Alert` now shows up to four `Tag`s (accepted release, in-progress release if any, memory version, knowledge version) instead of one; `SubsystemHealthPanel` unchanged; new `LlmRuntimePanel` (compact `variant="overview"`) mounted below it

---

## 11. Permissions

No permission table value changes. `/overview`'s role entry (`admin`/`operator`/`viewer`) stays exactly as it was — it is retained purely so `canAccessRoute` continues to resolve the compatibility route correctly; the `/home` entry (already `admin`/`operator`/`viewer` since S005) is what the redirects now target.

---

## 12. Shared component policy

Acceptable:

- `components/settings/LlmRuntimePanel` (already shared — Overview and now `EngStatusScreen` both mount it with different `variant` props, same precedent as S004/S006)
- `components/overview/SubsystemHealthPanel` + `components/overview/icons` (already shared, non-feature components — reused by `EngStatusScreen` since S006, unchanged in S007)

Rejected:

- Deleting still-referenced `components/overview/*` files (would violate the RFC-102 duplication-ban exception, which only applies to genuinely dead code, and would break `step065Ownership.test.ts` / `UpdateScreen` / `SourceSummaryCard`)
- Re-introducing a full-page Overview widget dashboard anywhere — every capability now has exactly one real owner

---

## 13. Backend boundary

S007 must not change:

- `backend/**`, `alembic/**`
- API contracts, auth/session, `APP_RELEASE`, release_status fields
- Database schema or migrations

S007 introduces no new backend calls — `EngStatusScreen` already called `getBuildInfo`; `LlmRuntimePanel` already called `getLlmRuntimeInfo`/`pullOllamaModel`/`runLlmBenchmark` (unchanged since S004).

Expected migration strategy on deploy: `post_sync_only` (not exercised — this task does not deploy).
Expected Alembic head unchanged from S006 baseline.

---

## 14. Testing strategy

- `dashboard/src/s007HomeDefaultOverview.test.ts` covering:
  - `/` navigates to `/home` (not `/overview`)
  - catch-all `*` navigates to `/home`
  - `App.tsx` has no remaining `Navigate to="/overview"`, but `/overview` stays registered
  - `/home` remains a real registered product route
  - `OverviewPage` is a thin `Navigate` redirect wrapper preserving `search`/`hash`, with no Overview widget imports
  - `LoginPage`'s default post-login destination is `/home`
  - `RequireAuth`'s role-mismatch fallback is `/home`
  - `canAccessRoute` still resolves `/overview` for all three roles (compatibility)
  - `PRODUCT_NAV` has no Overview entry (item or nested item)
  - Performance owns full analytics (not a preview fragment); Library owns readiness detail; Home owns quick links; `EngStatusScreen` owns subsystem health + LLM runtime + release/version tags; `EngTensionsScreen` owns the tension summary + explorer link
  - No regression to S006 Engineering isolation or S005 Home/Ask routes
- Update `s005HomeAskCutover.test.ts`'s one assertion that explicitly pinned the pre-S007 `/` → `/overview` behavior (comment now points at this package)
- Update `s001EngineeringMode.test.ts`'s one assertion that explicitly matched `Navigate to="/overview"` in `App.tsx` (comment now points at this package)
- Full regression: `cd dashboard && npm test`
- Full type-check: `cd dashboard && npx tsc --noEmit`

---

## 15. Documentation requirements

Create/maintain only S007 evidence artifacts under `docs/releases/`:

- `S007-implementation-package.md` (this file — frozen contract)
- `S007-implementation-evidence.md`
- `S007-product-readiness-gate.md`
- `S007-acceptance-evidence.md`

Do not rewrite S001–S006 evidence, RFC-100/101/102, or the execution roadmap.

---

## 16. Previous-step protection

S007 **must not modify** or reopen:

- S001 (product scaffold / Engineering Mode substrate) — except the one `Navigate to="/overview"` assertion in `s001EngineeringMode.test.ts` explicitly authorized here
- S002 (Knowledge ownership cutover)
- S003 (Insights ownership cutover)
- S004 (Settings ownership cutover)
- S005 (Home/Ask coexistence) — except the one assertion in `s005HomeAskCutover.test.ts` explicitly authorized here
- S006 (Engineering isolation) — except the additive `LlmRuntimePanel` + release/version tags on `EngStatusScreen` explicitly authorized here
- RFC-100, Step 067
- Deployment architecture, provenance, identity, verify-release, smoke, backend, schema, release workflow

---

## 17. Risks

| Risk | Rating | Mitigation |
|------|--------|------------|
| Redirect loop between `/`, `/overview`, and `/home` | none | `/overview` and `/home` are terminal routes (no further redirects between each other); only `/` and `*` redirect *into* `/home` |
| Bookmarked `/overview` links breaking | none | `OverviewPage` still renders at `/overview`, now redirecting to `/home` while preserving `search`/`hash`, same pattern proven by `/chat` → `/ask` in S005 |
| Losing a capability during redistribution | controlled | Full per-widget ownership ledger in §6; every capability has a named live owner; nothing is deleted |
| `EngStatusScreen` becoming overloaded (health + LLM runtime + release tags) | controlled | All three are read-only status widgets consistent with the screen's existing "engineering status" purpose; no new interactive surfaces added beyond what `LlmRuntimePanel` already provided on Overview |
| Frozen S001/S005 tests breaking from the redirect-target change | controlled | Both affected assertions are updated narrowly, in place, with explicit S007 cross-reference comments — same precedent S006 used for the `s005HomeAskCutover.test.ext` diagnostics/history assertion |

---

## 18. Acceptance criteria

S007 is complete only when all are true:

1. `/` navigates to `/home`, not `/overview`.
2. The catch-all `*` route navigates to `/home`, not `/overview`.
3. `/overview` remains routable and redirects to `/home`, preserving `search`/`hash`.
4. `OverviewPage.tsx` contains no Overview widget chrome — it is a thin redirect wrapper only.
5. `LoginPage`'s default post-login destination and `RequireAuth`'s role-mismatch fallback both target `/home`, not `/overview`.
6. `lib/permissions.ts` still resolves `/overview` for `admin`/`operator`/`viewer` (redirect compatibility preserved).
7. No Overview capability is lost: analytics (Performance), knowledge readiness (Library/Home), subsystem health + LLM runtime + release/version tags (EngStatus), tension summary + explorer (EngTensions/epistemic-health) all have live owners.
8. `PRODUCT_NAV` has no Overview entry (item or nested item) — confirmed unchanged from S001/S005.
9. No S001–S006 ownership regression beyond the two explicitly authorized test-assertion updates and the additive `EngStatusScreen` widgets.
10. No backend/deploy/provenance/identity/verify-release/smoke/schema/release-metadata changes; no commit/push/deploy performed.
11. `npm test` and `npx tsc --noEmit` pass.

---

## 19. Deliverables

- `/` and `*` defaulting to `/home`
- `OverviewPage` as a redirect-compatibility shim
- `LoginPage`/`RequireAuth` redirect fixes
- `EngStatusScreen` gaining the LLM runtime panel and release/version tags (closing the last two orphaned Overview capabilities)
- Full G6-P2 redistribution ledger (§6) proving no capability loss
- Tests + S007 evidence docs

---

## 20. Explicit non-goals

S007 will **not**:

- Delete any `components/overview/*` file still referenced by live code or a frozen test
- Remove the `/overview` route path itself
- Modify Home/Ask/Settings/Knowledge/Insights/Engineering ownership structure beyond the narrow, additive `EngStatusScreen` change in §3
- Rename or restructure `PRODUCT_NAV`/`ENGINEERING_NAV` (already correct since S001/S005)
- Commit, push, or deploy any part of this change
- Invent new admin retrieval-tuning controls or hardcoded business/domain knowledge

---

## Implementation contract seal

This document is the **sole implementation contract** for S007.

Nothing outside this package may be implemented under the S007 label.

**S007 IMPLEMENTATION PACKAGE COMPLETE — READY FOR IMPLEMENTATION**
