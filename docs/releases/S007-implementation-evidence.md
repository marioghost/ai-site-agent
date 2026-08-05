# S007 — Implementation Evidence

**Step:** S007
**Date:** 2026-08-05
**Authority:** `docs/releases/S007-implementation-package.md`
**Baseline:** S006 accepted state

## Scope implemented

- `G6-P3` Retire Overview default: `App.tsx`'s `/` route now `Navigate to="/home"` (was `/overview`); the catch-all `*` route now `Navigate to="/home"` (was `/overview`); `/overview` remains registered and renders `OverviewPage`, which is now a thin `Navigate`-based redirect wrapper to `/home` preserving `location.search`/`location.hash` (identical pattern to `pages/ChatTestPage.tsx`'s `/chat` → `/ask` shim from S005). `pages/LoginPage.tsx`'s post-login default destination (`from`) changed from `"/overview"` to `"/home"`. `components/auth/RequireAuth.tsx`'s role-mismatch fallback changed from `/overview` to `/home`. `lib/permissions.ts`'s `/overview` role-table entry is unchanged in value (still `admin`/`operator`/`viewer`) — only a clarifying comment was added, since the route must stay resolvable for the redirect-compatibility shim.
- `G6-P2` Redistribute Overview widgets: audited every widget `OverviewPage` used to mount and confirmed/completed a live owner for each (full ledger in the package §6):
  - `AnalyticsPreviewRow` → superseded by `/insights/performance` (`PerformanceScreen`), which already owns the full analytics surface (confirmed pre-existing from S003; no new work needed).
  - `KnowledgeBaseStatusCard` → superseded by `/knowledge/library`'s `SourcesSummaryCards`/`SourcesKnowledgeMiniCard` (readiness breakdown) and `/home`'s checklist (at-a-glance state) — both confirmed pre-existing.
  - `OverviewKnowledgeOsPanel`'s tension/claims metrics + "open health" link → superseded by `/engineering/tensions` (`EngTensionsScreen`, S006) and the full `/diagnostics/epistemic-health` explorer (pre-existing `real_claims`/`source_intelligence_claims`/`memory_version` metrics) — confirmed pre-existing, no gap.
  - `OverviewKnowledgeOsPanel`'s release/memory/knowledge-version tags and the separate build-info `Tag` row directly in `OverviewPage` → **new work**: `EngStatusScreen`'s existing release `Alert` (S006) was extended to also render an in-progress-release tag (when present), a memory-version tag, and a knowledge-version tag, using the same `build` state it already fetched via `getBuildInfo`.
  - `SubsystemHealthPanel` → already owned by `EngStatusScreen` since S006; unchanged.
  - `LlmRuntimePanel` (LLM runtime/benchmark) → **new work**: this widget was previously mounted *only* on `OverviewPage` (with `variant="overview"`); it is now also mounted on `EngStatusScreen` with the same compact `variant="overview"`, so retiring Overview does not orphan it. The original `components/settings/LlmRuntimePanel.tsx` file is unchanged (still a shared, non-feature component per S004/S006 precedent).
- `pages/OverviewPage.tsx` was rewritten in place (not deleted) to drop every widget import (`AnalyticsPreviewRow`, `KnowledgeBaseStatusCard`, `OverviewKnowledgeOsPanel`, `LlmRuntimePanel`, `OverviewFooterNote`, `OverviewHeader`, `SubsystemHealthPanel`, icons) and all associated state/effects/API calls, replacing them with a single `Navigate` redirect, matching the `ChatTestPage` precedent.
- No `components/overview/*` widget file was deleted: `OverviewHeader.tsx` is still used by `features/knowledge/update/UpdateScreen.tsx` as a generic page-header component (unrelated to Overview product ownership); `OverviewKpiCard.tsx` is still used by `components/sources/SourceSummaryCard.tsx` (type import); `OverviewKnowledgeOsPanel.tsx` is still read directly via `?raw` by the frozen `step065Ownership.test.ts`; `SubsystemHealthPanel.tsx`/`icons.tsx` are still used by `EngStatusScreen`. `AnalyticsPreviewRow.tsx` and `KnowledgeBaseStatusCard.tsx` are the only two files that are now fully unmounted (orphaned-but-present) — left in place rather than deleted since deleting unreferenced files was not required by any acceptance criterion and preserves a clean rollback path.
- `G1-P3`/`G1-P4` (finalize): confirmed `lib/navConfig.ts`'s `PRODUCT_NAV` has never listed `/overview` or a `nav.overview` labelKey (verified by inspection and by the new `s007HomeDefaultOverview.test.ts` assertion) — no code change was needed, since S001/S005 already wired `PRODUCT_NAV` around `/home` as the sole top-level landing entry. The unused `nav.overview` i18n key (en/uk) was left in place — it is not wired into any nav and removing it was not required by any acceptance criterion.
- Updated the one `s005HomeAskCutover.test.ts` assertion that explicitly pinned the pre-S007 `/` → `/overview` behavior (previously titled "does not empty Overview and does not change the `/` default"); it now only asserts `OverviewPage` has no `MigrationPlaceholder` and that `/overview` stays registered, with a comment pointing at `s007HomeDefaultOverview.test.ts` for the current contract.
- Updated the one `s001EngineeringMode.test.ts` assertion that explicitly matched `Navigate to="/overview"` in `App.tsx`; it now asserts `/overview` stays registered as a path (without asserting it's a `Navigate` target), with the same cross-reference comment.

## Architecture delta

- `dashboard/src/App.tsx`: `/` and `*` redirect targets changed from `/overview` to `/home`; `/overview` route comment updated to document its new redirect-compatibility role
- `dashboard/src/pages/OverviewPage.tsx`: full page → thin `Navigate` redirect wrapper (same shape as `ChatTestPage.tsx`)
- `dashboard/src/pages/LoginPage.tsx`: default post-login destination `/overview` → `/home`
- `dashboard/src/components/auth/RequireAuth.tsx`: role-mismatch fallback `/overview` → `/home`
- `dashboard/src/lib/permissions.ts`: comment only, no value change
- `dashboard/src/features/engineering/status/EngStatusScreen.tsx`: additive — `LlmRuntimePanel` import + mount, release Alert extended with in-progress/memory/knowledge-version tags
- No route path, permission table value, or nav config changes — only redirect *targets* and one screen's additive content changed

## Files changed

### New

- `dashboard/src/s007HomeDefaultOverview.test.ts`
- `docs/releases/S007-implementation-package.md`
- `docs/releases/S007-implementation-evidence.md`
- `docs/releases/S007-product-readiness-gate.md`
- `docs/releases/S007-acceptance-evidence.md`

### Modified

- `dashboard/src/App.tsx`
- `dashboard/src/pages/OverviewPage.tsx`
- `dashboard/src/pages/LoginPage.tsx`
- `dashboard/src/components/auth/RequireAuth.tsx`
- `dashboard/src/lib/permissions.ts`
- `dashboard/src/features/engineering/status/EngStatusScreen.tsx`
- `dashboard/src/s005HomeAskCutover.test.ts` (one assertion updated, test count unchanged: 13)
- `dashboard/src/s001EngineeringMode.test.ts` (one assertion updated, test count unchanged: 13)

### Removed

- None

## Tests

- `dashboard/src/s007HomeDefaultOverview.test.ts` — 15 new tests
- `dashboard/src/s005HomeAskCutover.test.ts` — 13 tests (1 assertion updated, count unchanged)
- `dashboard/src/s001EngineeringMode.test.ts` — 13 tests (1 assertion updated, count unchanged)
- Full dashboard suite: `cd dashboard && npm test -- --run`

## Test results

```
cd dashboard && npm test -- --run
 Test Files  16 passed (16)
      Tests  342 passed (342)

cd dashboard && npx tsc --noEmit
(no output — clean)
```

## Evidence checklist

- [x] `/` navigates to `/home`, not `/overview`
- [x] Catch-all `*` navigates to `/home`, not `/overview`
- [x] `/overview` remains routable, redirects to `/home`, preserves search/hash
- [x] `OverviewPage.tsx` is a thin redirect wrapper with no Overview widget chrome
- [x] `LoginPage`/`RequireAuth` redirects target `/home`, not `/overview`
- [x] `lib/permissions.ts` still resolves `/overview` for all three roles
- [x] Every Overview capability has a live owner (full ledger in package §6) — no capability lost
- [x] `PRODUCT_NAV` has no Overview entry (confirmed unchanged from S001/S005)
- [x] No S001–S006 ownership regression beyond the two authorized test-assertion updates and the additive `EngStatusScreen` widgets
- [x] No backend/deploy/provenance files touched; no commit/push/deploy performed
- [x] `npm test` and `npx tsc --noEmit` pass
- [ ] Implementation Review
- [ ] Commit Review
- [ ] Push Review
- [ ] Deployment Review
- [ ] Runtime Validation
- [ ] Final Acceptance
