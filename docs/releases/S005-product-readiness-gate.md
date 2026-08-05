# S005 — Product Readiness Gate Record

**Step:** S005 — Home shell + Ask coexistence
**Date:** 2026-08-05
**Authority:** `docs/releases/S005-implementation-package.md`

```yaml
gate_record:
  step_or_change: S005 Home shell + Ask coexistence
  program: RFC-101 Product Completion
  package_ids:
    - G6-P1
    - G3-P1
    - G8-P2
  reviewer: pending Implementation Review
  decision: pending
  scope: "Home readiness shell under /home; Ask product chrome coexistence under /ask; /chat -> /ask redirect; RFC-102 migration"
  engineering_mode_isolation: "Unchanged; Ask progressive disclosure and Eng ask-details population deferred to S006"
  simplicity_duplication: "Legacy Chat Test page becomes redirect only; Home and Ask remain singular canonical owners; no second Overview or chat surface introduced"
  accepted_debt:
    - "ChatHistoryModal and ChatDiagnosticsSidebar remain mounted in Ask pending G3-P2..P4 (S006) history/diagnostics ownership move to Activity/Eng ask-details"
    - "Overview widgets remain in place pending G6-P2 (S006/S007) redistribution to Insights/Eng status"
    - "/ default landing remains /overview pending G6-P3 (S007) Home-as-default cutover"
  evidence_paths:
    - docs/releases/S005-implementation-package.md
    - docs/releases/S005-implementation-evidence.md
    - docs/releases/S005-acceptance-evidence.md
```

**Decision:** Pending review.
