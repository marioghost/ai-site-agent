# S006 — Acceptance Evidence

**Step:** S006
**Authority:** `docs/releases/S006-implementation-package.md`

## Required review chain

- [ ] Implementation Review
- [ ] Commit Review
- [ ] Push Review
- [ ] Deployment Review
- [ ] Runtime Validation
- [ ] Final Acceptance

## What each review must prove

### Implementation Review

- `/knowledge/update` no longer imports the Source Intelligence generate/preview widgets or `generateSourceIntelligence`; the indexing job (start/stop/reindex-all/reprocess-existing) is unchanged
- `/engineering/knowledge` hosts the relocated SI generate/preview UX with working status polling
- `/engineering/advanced` hosts the relocated advanced retrieval/chunking/cache/tracing knobs; `/engineering/build` hosts the relocated migration-flag catalog
- Product Settings screens (General/Models/Answers/Access) never import `SettingsAdvancedSection`, `RetrievalEnginePanel`, or `MigrationFlagsPanel`
- `/ask` no longer imports `ChatDiagnosticsSidebar` or `ChatHistoryModal`; keeps only core chat chrome (toolbar/message list/composer)
- `/engineering/ask-details` reuses the shared chat session to show diagnostics, or guidance + a link to `/ask` when no session/turns exist
- Ask's "History" toolbar action navigates to `/insights/activity`
- `EngStatusScreen` and `EngTensionsScreen` are free of the S001 `MigrationPlaceholder` and show real (or link-based) content
- `EngineeringLayout` renders section navigation for all 6 Engineering destinations
- All 6 `/engineering/*` routes remain gated by `RequireEngineeringMode` (Mode on + admin)
- No S007 scope leakage — `HomeScreen.tsx`/`OverviewPage.tsx` untouched; `/` still redirects to `/overview`
- S002 Knowledge, S003 Insights, S004 Settings structural ownership unchanged beyond the narrow, explicitly authorized deltas
- `npm test` (327/327) and `npx tsc --noEmit` (clean) both pass

### Commit Review

- Not performed for this task (explicitly out of scope — implementation only)
- When performed: commit scope must be limited to S006 frontend/tests/docs, no deploy/backend/remediation files

### Push Review

- Not performed for this task (explicitly out of scope)

### Deployment Review

- Not performed for this task (explicitly out of scope)
- When performed: standard deployment path only (`sudo bash deploy/manage_deploy.sh deploy full`); no deployment architecture changes required for S006

### Runtime Validation

- Not performed for this task (explicitly out of scope — no deploy occurred)
- When performed: `/engineering/knowledge`, `/engineering/advanced`, `/engineering/build`, `/engineering/status`, `/engineering/tensions`, `/engineering/ask-details` are live and free of placeholders; `/ask` no longer shows diagnostics/history chrome; `/knowledge/update` indexing job still functions

### Final Acceptance

- All package acceptance criteria in `docs/releases/S006-implementation-package.md` §18 satisfied
- No duplicate Ask/Engineering ownership remains
- Previous accepted remediation, S001–S005 remain unchanged beyond the narrow, explicitly authorized deltas
