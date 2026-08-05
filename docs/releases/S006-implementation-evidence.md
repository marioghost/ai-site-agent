# S006 — Implementation Evidence

**Step:** S006
**Date:** 2026-08-05
**Authority:** `docs/releases/S006-implementation-package.md`
**Baseline:** S005 accepted state

## Scope implemented

- `G4-P4` Source Intelligence engineering isolation: copied `SourceIntelligencePanel`, `SourceIntelligencePreviewModal`, and the profile-display card (renamed `SourceIntelligenceProfileCard`) from `features/knowledge/update/widgets` and `features/knowledge/shared` into `features/engineering/knowledge/widgets`, with relative imports fixed for the new depth. `EngKnowledgeScreen` now hosts SI stats/generate/dry-run/preview UX with its own `getIndexStatus` polling and `generateSourceIntelligence` calls. `UpdateScreen` no longer imports the SI panel/preview modal or `generateSourceIntelligence`; it keeps the indexing job (start/stop/reindex-all/reprocess-existing) fully intact and shows a small `SectionCard` link to `/engineering/knowledge`, gated on Engineering Mode (`useEngineeringMode`) — hidden entirely when Mode is off. `IndexingActionsBar` dropped its SI-specific "Generate intelligence"/"Intelligence preview" buttons and props; `Stop` now derives from the shared job `status.status` alone (unaffected, since SI runs use the same job/status endpoint as indexing runs). The two now-orphaned product-path SI widget files were deleted (fully superseded by the Engineering copies; no remaining references).
- `G7-P5` Advanced/Build engineering isolation: copied `SettingsAdvancedSection` + `RetrievalEnginePanel` into `features/engineering/advanced/widgets`, and `MigrationFlagsPanel` into `features/engineering/build/widgets`, with relative imports fixed. `EngAdvancedScreen` hosts the advanced knobs with its own settings load + explicit Save action; `EngBuildScreen` hosts the flag catalog. The original `components/settings/*` files are untouched (still referenced by `s001EngineeringMode.test.ts`/`step065Ownership.test.ts`). Product Settings screens (`GeneralScreen`/`ModelsScreen`/`AnswersScreen`/`AccessScreen`) already did not mount these (verified, not modified).
- `G3-P2` Ask diagnostics → Engineering: `AskScreen` no longer imports `ChatDiagnosticsSidebar` (nor the `getSettings`-derived diagnostics flags, nor the diagnostics-only derived state — `pipelineStages`/`trace`/`retrievalDebug`/`lastUserMessage`/export toast — all of which existed only to feed that sidebar). `EngAskDetailsScreen` reuses the app-wide `ChatSessionContext` (already mounted at `main.tsx` above `App`) to render the same diagnostics view for the active session, computing the same derived shape Ask used to. When no session/turns exist yet, it shows an explainer + guidance card with a link to `/ask` instead.
- `G3-P3` Ask history → Activity handoff: confirmed by inspection that `ChatToolbar` does not own history-modal state itself — it delegates via an `onOpenHistory` callback prop, and `ChatSessionContext`'s `historyOpen`/`setHistoryOpen` were only ever consumed by `AskScreen` and `ChatHistoryModal`. `AskScreen` now passes `onOpenHistory={() => navigate("/insights/activity")}` (via `useNavigate`) instead of `() => setHistoryOpen(true)`, and no longer imports `ChatHistoryModal`. `ChatToolbar.tsx` itself required no changes (it already only takes a callback).
- `G3-P4` Ask progressive disclosure: `AskScreen` now mounts only `ChatToolbar` + `ChatMessageList` + `ChatComposer` inside a single-column `ds-chat-console--single` (new CSS modifier in `ui/styles/chat.css`, since the two-column grid was sized for a diagnostics sidebar that no longer exists).
- `EngStatusScreen`: real health screen — `Promise.all([getHealth(), getIndexStatus(), getBuildInfo()])`, rendering the same `SubsystemHealthPanel` widget Overview uses (shared, non-feature component under `components/overview/`) with backend/database/ollama/qdrant/indexing status, plus a release tag banner and a Refresh action. Loading/error states included.
- `EngTensionsScreen`: real lightweight screen — fetches `getEpistemicHealthSummary()` for a 3-metric summary (`real_open_tensions`/`real_support_deficit_tensions`/`real_conflict_tensions`) and links to the existing full `/diagnostics/epistemic-health` explorer (`EpistemicHealthPage`, left unchanged — it already has full filter/pagination/JSON-export functionality; duplicating that logic here would violate the RFC-102 duplication ban).
- `EngineeringLayout`: added a `NavLink` section-nav bar (mirrors `KnowledgeLayout`) driven by the existing `ENGINEERING_NAV.items` from `lib/navConfig.ts` — no nav config changes needed.
- `s005HomeAskCutover.test.ts`: updated the one assertion whose comment explicitly said "S006 retires these; S005 keeps them mounted for coexistence" — it no longer asserts `ChatHistoryModal`/`ChatDiagnosticsSidebar` presence in Ask, since S006 is the step that retires them.

## Architecture delta

- New Engineering-owned widget folders (RFC-102 `features/<domain>/<screen>/widgets` convention):
  - `dashboard/src/features/engineering/knowledge/widgets/{SourceIntelligencePanel,SourceIntelligencePreviewModal,SourceIntelligenceProfileCard}.tsx`
  - `dashboard/src/features/engineering/advanced/widgets/{SettingsAdvancedSection,RetrievalEnginePanel}.tsx`
  - `dashboard/src/features/engineering/build/widgets/MigrationFlagsPanel.tsx`
- `dashboard/src/features/ask/AskScreen.tsx`: diagnostics/history chrome removed; single-column console
- `dashboard/src/features/engineering/ask-details/EngAskDetailsScreen.tsx`: real screen, diagnostics ownership
- `dashboard/src/features/engineering/knowledge/EngKnowledgeScreen.tsx`: real screen, SI ownership
- `dashboard/src/features/engineering/advanced/EngAdvancedScreen.tsx`: real screen, advanced knobs ownership
- `dashboard/src/features/engineering/build/EngBuildScreen.tsx`: real screen, flag catalog ownership
- `dashboard/src/features/engineering/status/EngStatusScreen.tsx`: real screen, live health ownership
- `dashboard/src/features/engineering/tensions/EngTensionsScreen.tsx`: real screen, tension summary + link ownership
- `dashboard/src/features/knowledge/update/UpdateScreen.tsx`: SI panel/preview modal + SI-only state removed; Mode-gated Engineering link added
- `dashboard/src/features/knowledge/update/widgets/IndexingActionsBar.tsx`: SI-specific props/buttons removed
- `dashboard/src/layouts/EngineeringLayout.tsx`: section nav added
- `dashboard/src/ui/styles/chat.css`: `.ds-chat-console--single` modifier added
- `dashboard/src/i18n/en.ts` / `uk.ts`: `eng.*` namespace + `indexing.intelligence.eng_link_*` keys added
- No route path, permission table, or nav config changes — S001/S005 substrate already provided all 6 `/engineering/*` routes and the `/ask` route

## Files changed

### New

- `dashboard/src/features/engineering/knowledge/widgets/SourceIntelligencePanel.tsx`
- `dashboard/src/features/engineering/knowledge/widgets/SourceIntelligencePreviewModal.tsx`
- `dashboard/src/features/engineering/knowledge/widgets/SourceIntelligenceProfileCard.tsx`
- `dashboard/src/features/engineering/advanced/widgets/SettingsAdvancedSection.tsx`
- `dashboard/src/features/engineering/advanced/widgets/RetrievalEnginePanel.tsx`
- `dashboard/src/features/engineering/build/widgets/MigrationFlagsPanel.tsx`
- `dashboard/src/s006EngineeringIsolation.test.ts`
- `docs/releases/S006-implementation-package.md`
- `docs/releases/S006-implementation-evidence.md`
- `docs/releases/S006-product-readiness-gate.md`
- `docs/releases/S006-acceptance-evidence.md`

### Modified

- `dashboard/src/features/ask/AskScreen.tsx`
- `dashboard/src/features/engineering/ask-details/EngAskDetailsScreen.tsx`
- `dashboard/src/features/engineering/knowledge/EngKnowledgeScreen.tsx`
- `dashboard/src/features/engineering/advanced/EngAdvancedScreen.tsx`
- `dashboard/src/features/engineering/build/EngBuildScreen.tsx`
- `dashboard/src/features/engineering/status/EngStatusScreen.tsx`
- `dashboard/src/features/engineering/tensions/EngTensionsScreen.tsx`
- `dashboard/src/features/knowledge/update/UpdateScreen.tsx`
- `dashboard/src/features/knowledge/update/widgets/IndexingActionsBar.tsx`
- `dashboard/src/layouts/EngineeringLayout.tsx`
- `dashboard/src/i18n/en.ts`
- `dashboard/src/i18n/uk.ts`
- `dashboard/src/ui/styles/chat.css`
- `dashboard/src/s005HomeAskCutover.test.ts`

### Deleted

- `dashboard/src/features/knowledge/update/widgets/SourceIntelligencePanel.tsx`
- `dashboard/src/features/knowledge/update/widgets/SourceIntelligencePreviewModal.tsx`

## Tests

- `dashboard/src/s006EngineeringIsolation.test.ts` — 12 new tests
- `dashboard/src/s005HomeAskCutover.test.ts` — 13 tests (1 assertion updated, count unchanged)
- Full dashboard suite: `cd dashboard && npm test -- --run`

## Test results

```
cd dashboard && npm test -- --run
 Test Files  15 passed (15)
      Tests  327 passed (327)

cd dashboard && npx tsc --noEmit
(no output — clean)
```

## Evidence checklist

- [x] Source Intelligence generate/preview UX relocated to `/engineering/knowledge`; Update indexing job intact
- [x] Advanced knobs relocated to `/engineering/advanced`; flag catalog relocated to `/engineering/build`
- [x] Ask diagnostics ownership relocated to `/engineering/ask-details`
- [x] Ask history handoff to `/insights/activity` (no `ChatHistoryModal`)
- [x] Ask remains a simple, product-only chat surface (progressive disclosure)
- [x] `EngStatusScreen`/`EngTensionsScreen` free of `MigrationPlaceholder`, real/link-based content
- [x] `EngineeringLayout` section nav for all 6 Engineering destinations
- [x] No Home/Overview/S007 scope leakage
- [x] No backend/deploy/provenance files touched; no commit/push/deploy performed
- [x] `npm test` and `npx tsc --noEmit` pass
- [ ] Implementation Review
- [ ] Commit Review
- [ ] Push Review
- [ ] Deployment Review
- [ ] Runtime Validation
- [ ] Final Acceptance
