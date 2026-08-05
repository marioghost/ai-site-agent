# S004 — Product Readiness Gate Record

**Step:** S004 — Settings product split (except Eng Advanced move)
**Date:** 2026-08-05
**Authority:** `docs/releases/S004-implementation-package.md`

```yaml
gate_record:
  step_or_change: S004 Settings product split
  program: RFC-101 Product Completion
  package_ids:
    - G7-P1
    - G7-P2
    - G7-P3
    - G7-P4
    - G1-P2
    - G8-P2
  reviewer: pending Implementation Review
  decision: pending
  scope: "General/Models/Answers/Access product ownership; Users->Access redirect; RFC-102 migration"
  engineering_mode_isolation: "Unchanged; G7-P5 Advanced/Build move deferred to S006 as documented dependency"
  simplicity_duplication: "Legacy Users page becomes redirect only; canonical Settings owners remain singular"
  accepted_debt:
    - "SettingsAdvancedSection/RetrievalEnginePanel/LlmRuntimePanel/MigrationFlagsPanel remain in components/settings on disk pending G7-P5 (S006) Eng Advanced/Build relocation"
    - "pages/SettingsPage.tsx left unrouted and unmodified (dead code, no live links); not converted to a redirect to avoid reopening frozen Step 065/S001 contract tests"
  evidence_paths:
    - docs/releases/S004-implementation-package.md
    - docs/releases/S004-implementation-evidence.md
    - docs/releases/S004-acceptance-evidence.md
```

**Decision:** Pending review.
