# S005 — Implementation Evidence

**Step:** S005
**Date:** 2026-08-05
**Authority:** `docs/releases/S005-implementation-package.md`
**Baseline:** S004 accepted state

## Scope implemented

- `G6-P1` Home readiness screen under `/home`: computes a single readiness state (needs_setup / needs_update / updating / ready / needs_attention per RFC-101 §7) from `getSettings`, `getHealth`, `getIndexStatus`, `listSources`, and `getOverview`; renders a readiness checklist and ≤2 state-driven CTAs plus a role-filtered quick-access row (`/ask`, `/knowledge/update`, `/insights/performance`, `/settings/general`)
- `G3-P1` Ask product owner under `/ask`: migrated the chat product chrome (`ChatToolbar`, `ChatMessageList`, `ChatComposer`, `ChatDiagnosticsSidebar`, `ChatHistoryModal`) from `pages/ChatTestPage.tsx`, reusing `ChatSessionContext` unchanged; `ChatHistoryModal`/`ChatDiagnosticsSidebar` remain mounted (retirement deferred to S006)
- `/chat` converted to a compatibility redirect to `/ask` (preserves `search`/`hash`), matching the S002/S003/S004 redirect precedent
- `/ask` route element moved inside the same `RequireAuth roles={["admin","operator"]}` wrapper already applied to `/chat` in `App.tsx`, closing a pre-existing gap where `/ask` was reachable without a route-level role guard
- `ProblematicQueriesSection` deep links retargeted from `/chat?q=` to `/ask?q=` in both `features/insights/performance/widgets/ProblematicQueriesSection.tsx` and the legacy `components/analytics/ProblematicQueriesSection.tsx`
- `G8-P2` RFC-102 ownership migration into `features/home/*` and `features/ask/*`

## Architecture delta

- Canonical Home/Ask screens own product behavior in:
  - `dashboard/src/features/home/HomeScreen.tsx`
  - `dashboard/src/features/ask/AskScreen.tsx`
- Legacy page became a compatibility redirect only:
  - `dashboard/src/pages/ChatTestPage.tsx` → `/ask`
- `dashboard/src/App.tsx`: `/ask` route relocated into the admin/operator `RequireAuth` group alongside `/chat`, `/sources`, `/indexing`, `/knowledge-profile`
- `dashboard/src/lib/permissions.ts` already matched the target `/ask` / `/chat` roles from the S001 baseline scaffold — no table change was required, only the `App.tsx` route-guard placement
- `dashboard/src/lib/navConfig.ts` already had top-level `Home`/`Ask` nav entries from S001 — unchanged
- `dashboard/src/i18n/en.ts` / `dashboard/src/i18n/uk.ts`: added `home.*` readiness-shell keys and `ask.subtitle`
- `dashboard/src/pages/OverviewPage.tsx` left fully intact (not emptied); `/` still redirects to `/overview`
- Settings (S004), Knowledge (S002), Insights (S003) ownership/structure left unchanged — only the single Ask deep link in `ProblematicQueriesSection` (both copies) was retargeted

## Files changed

### Modified

- `dashboard/src/App.tsx`
- `dashboard/src/features/home/HomeScreen.tsx`
- `dashboard/src/features/ask/AskScreen.tsx`
- `dashboard/src/pages/ChatTestPage.tsx`
- `dashboard/src/i18n/en.ts`
- `dashboard/src/i18n/uk.ts`
- `dashboard/src/features/insights/performance/widgets/ProblematicQueriesSection.tsx`
- `dashboard/src/components/analytics/ProblematicQueriesSection.tsx`

### New

- `dashboard/src/s005HomeAskCutover.test.ts`
- `docs/releases/S005-implementation-package.md`
- `docs/releases/S005-implementation-evidence.md`
- `docs/releases/S005-product-readiness-gate.md`
- `docs/releases/S005-acceptance-evidence.md`

## Tests expected

- `dashboard/src/s005HomeAskCutover.test.ts` (13 tests)
- Existing dashboard suite (`npm test`)
- TypeScript check (`npx tsc --noEmit`)

## Test results

```
cd dashboard && npm test -- --run
 Test Files  14 passed (14)
      Tests  315 passed (315)

cd dashboard && npx tsc --noEmit
(no output — clean)
```

## Evidence checklist

- [x] Home readiness owner implemented under `/home` (RFC-101 §7 states, checklist, ≤2 CTAs)
- [x] Ask product owner implemented under `/ask` (chat chrome migrated, history/diagnostics kept mounted)
- [x] Legacy `/chat` converted to a redirect preserving search/hash
- [x] `/ask` gated admin/operator at the route-guard level (parity with `/chat`)
- [x] `ProblematicQueriesSection` deep links retargeted to `/ask` (both locations)
- [x] Home/Ask ownership migrated into `features/home/*` / `features/ask/*`
- [x] Overview left fully intact; `/` still redirects to `/overview`
- [x] No deploy/backend/remediation/Settings/Knowledge/Insights ownership files modified beyond the single link retarget
- [x] `npm test` and `npx tsc --noEmit` pass
- [ ] Implementation Review
- [ ] Commit Review
- [ ] Push Review
- [ ] Deployment Review
- [ ] Runtime Validation
- [ ] Final Acceptance
