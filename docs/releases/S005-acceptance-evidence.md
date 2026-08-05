# S005 — Acceptance Evidence

**Step:** S005
**Authority:** `docs/releases/S005-implementation-package.md`

## Required review chain

- [ ] Implementation Review
- [ ] Commit Review
- [ ] Push Review
- [ ] Deployment Review
- [ ] Runtime Validation
- [ ] Final Acceptance

## What each review must prove

### Implementation Review

- Home and Ask are the only owners for `/home` and `/ask`, both free of the S001 `MigrationPlaceholder`
- Home computes a readiness state per RFC-101 §7 with a checklist and at most one primary + one secondary CTA
- Ask hosts the migrated chat product chrome; `ChatHistoryModal`/`ChatDiagnosticsSidebar` remain mounted (not retired — that is S006)
- Legacy `/chat` is a redirect only, preserving search/hash
- `/ask` and `/chat` are both gated to admin/operator at the route-guard level
- `ProblematicQueriesSection` deep links point to `/ask`, not `/chat`, in both locations
- Ownership lives in `features/home/*` and `features/ask/*`
- Overview is not emptied; `/` still redirects to `/overview`
- No S006/S007 scope leakage
- S002 Knowledge, S003 Insights, S004 Settings ownership unchanged

### Commit Review

- Commit scope limited to S005 frontend/tests/docs
- No deploy/backend/remediation files

### Push Review

- Published range contains only approved S005 changes
- Repository remains synchronized and clean

### Deployment Review

- Standard deployment path only (`sudo bash deploy/manage_deploy.sh deploy full`)
- No deployment architecture changes required for S005

### Runtime Validation

- Runtime identity equals deployed S005 tip
- `/home` and `/ask` are live and free of placeholders
- `/chat` resolves compatibly to `/ask`, preserving `?q=` deep links
- `/overview` remains fully populated and reachable via `/`

### Final Acceptance

- All package acceptance criteria satisfied
- No duplicate Home/Ask ownership remains
- Previous accepted remediation, S001, S002, S003, and S004 remain unchanged
