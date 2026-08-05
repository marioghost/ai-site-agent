# S004 — Implementation Evidence

**Step:** S004
**Date:** 2026-08-05
**Authority:** `docs/releases/S004-implementation-package.md`
**Baseline:** `9a7134c05e2e9348baf65b59c2d75f4fcfdb1ac9`

## Scope implemented

- `G7-P1` General finishes beyond toggle host: persists `dashboard_language` server-side on change (Mode toggle unchanged)
- `G7-P2` Models product owner under `/settings/models`
- `G7-P3` Answers product owner under `/settings/answers`
- `G7-P4` Access product owner under `/settings/access` (migrated from `UsersPage`)
- `G1-P2` S004 redirect slice for `/users`
- `G8-P2` RFC-102 ownership migration into `features/settings/*`

## Architecture delta

- Canonical Settings screens own product behavior in:
  - `dashboard/src/features/settings/general/GeneralScreen.tsx`
  - `dashboard/src/features/settings/models/ModelsScreen.tsx`
  - `dashboard/src/features/settings/answers/AnswersScreen.tsx`
  - `dashboard/src/features/settings/access/AccessScreen.tsx`
- Models widgets live under `dashboard/src/features/settings/models/widgets/OllamaModelsPanel.tsx` (copied from `components/settings/OllamaModelsPanel.tsx` with relative imports fixed to `../../../../`)
- `dashboard/src/components/LanguageSwitcher.tsx` gained an additive optional `onChange` callback (used only by General to persist `dashboard_language`; Login/TopBar usages unaffected)
- Legacy page became a compatibility redirect only:
  - `dashboard/src/pages/UsersPage.tsx` → `/settings/access`
- `SettingsLayout` provides General/Models/Answers/Access section navigation
- `dashboard/src/lib/permissions.ts` and `dashboard/src/lib/navConfig.ts` already matched the target Settings routes/nav from the S001 baseline scaffold — no changes were required
- Knowledge (S002) and Insights (S003) ownership left unchanged
- `pages/SettingsPage.tsx` left unrouted and unmodified (dead code on baseline; not linked from any live surface); modifying it into a redirect would reopen frozen `step065Ownership.test.ts` / `s001EngineeringMode.test.ts` assertions that inspect its legacy `SettingsAdvancedSection`/`SettingsHelpAccordion` content — registered as accepted debt, not required by the S004 package (Section 7 marks it "for safety if anything links it", and nothing does)

## Files changed

### Modified

- `dashboard/src/components/LanguageSwitcher.tsx`
- `dashboard/src/features/settings/general/GeneralScreen.tsx`
- `dashboard/src/features/settings/models/ModelsScreen.tsx`
- `dashboard/src/features/settings/answers/AnswersScreen.tsx`
- `dashboard/src/features/settings/access/AccessScreen.tsx`
- `dashboard/src/layouts/SettingsLayout.tsx`
- `dashboard/src/pages/UsersPage.tsx`

### New

- `dashboard/src/features/settings/models/widgets/OllamaModelsPanel.tsx`
- `dashboard/src/s004SettingsCutover.test.ts`
- `docs/releases/S004-implementation-package.md`
- `docs/releases/S004-implementation-evidence.md`
- `docs/releases/S004-product-readiness-gate.md`
- `docs/releases/S004-acceptance-evidence.md`

## Tests expected

- `dashboard/src/s004SettingsCutover.test.ts`
- Existing dashboard suite (`npm test`)
- TypeScript check (`npx tsc --noEmit`)

## Test results

```
cd dashboard && npm test -- --run
 Test Files  13 passed (13)
      Tests  302 passed (302)

cd dashboard && npx tsc --noEmit
(no output — clean)
```

## Evidence checklist

- [x] Canonical Settings owners implemented (General/Models/Answers/Access)
- [x] Legacy `/users` route converted to a redirect
- [x] Settings ownership migrated into `features/settings/*`
- [x] Models/Answers contain no `SettingsAdvancedSection`/`RetrievalEnginePanel`/`MigrationFlagsPanel`
- [x] No deploy/backend/remediation/Knowledge/Insights ownership files modified
- [x] `npm test` and `npx tsc --noEmit` pass
- [ ] Implementation Review
- [ ] Commit Review
- [ ] Push Review
- [ ] Deployment Review
- [ ] Runtime Validation
- [ ] Final Acceptance
