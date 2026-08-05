# S004 — Acceptance Evidence

**Step:** S004
**Authority:** `docs/releases/S004-implementation-package.md`

## Required review chain

- [ ] Implementation Review
- [ ] Commit Review
- [ ] Push Review
- [ ] Deployment Review
- [ ] Runtime Validation
- [ ] Final Acceptance

## What each review must prove

### Implementation Review

- General/Models/Answers/Access are the only Settings product owners
- Legacy `/users` is a redirect only
- Ownership lives in `features/settings/*`
- No `SettingsAdvancedSection`/`RetrievalEnginePanel`/`MigrationFlagsPanel` leaked into Models/Answers/Access
- No S005+ scope leakage
- S002 Knowledge and S003 Insights ownership unchanged

### Commit Review

- Commit scope limited to S004 frontend/tests/docs
- No deploy/backend/remediation files

### Push Review

- Published range contains only approved S004 changes
- Repository remains synchronized and clean

### Deployment Review

- Standard deployment path only (`sudo bash deploy/manage_deploy.sh deploy full`)
- No deployment architecture changes required for S004

### Runtime Validation

- Runtime identity equals deployed S004 tip
- `/settings/general`, `/settings/models`, `/settings/answers`, `/settings/access` are live
- `/users` resolves compatibly to `/settings/access`

### Final Acceptance

- All package acceptance criteria satisfied
- No duplicate Settings ownership remains
- Previous accepted remediation, S001, S002, and S003 remain unchanged
