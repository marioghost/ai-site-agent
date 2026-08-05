# S007 — Product Readiness Gate Record

**Step:** S007 — Home default + Overview retirement
**Date:** 2026-08-05
**Authority:** `docs/releases/S007-implementation-package.md`

```yaml
gate_record:
  step_or_change: S007 Home default + Overview retirement
  program: RFC-101 Product Completion
  package_ids:
    - G6-P2
    - G6-P3
  reviewer: pending Implementation Review
  decision: pending
  scope: "Home (`/home`) becomes the effective product default: `/` and `*` now redirect to `/home` instead of `/overview`; OverviewPage becomes a thin redirect-compatibility shim; every remaining Overview-only widget (LLM runtime panel, Knowledge OS release/version tags) gains a real owner on EngStatusScreen; LoginPage/RequireAuth redirects fixed to target /home"
  engineering_mode_isolation: "Unaffected — no Engineering Mode gating changes; EngStatusScreen gains two additive widgets but remains behind the same RequireEngineeringMode + admin guard as all other /engineering/* routes"
  simplicity_duplication: "No new duplication: LlmRuntimePanel and the release/version tags are moved (Overview no longer renders them) to EngStatusScreen, which already fetches the same build/health data; no Overview widget file is deleted since some remain referenced by live code (OverviewHeader/OverviewKpiCard) or a frozen prior-step test (OverviewKnowledgeOsPanel via step065Ownership.test.ts) — left as orphaned-but-present rather than duplicated elsewhere"
  accepted_debt:
    - "AnalyticsPreviewRow.tsx and KnowledgeBaseStatusCard.tsx are now fully unmounted (no importer) but not deleted — deletion was not required by any acceptance criterion and is deferred to S008 cleanup if desired"
    - "Unused `nav.overview` i18n key (en/uk) left in place — harmless, not wired into any nav, removal deferred to S008 cleanup if desired"
  evidence_paths:
    - docs/releases/S007-implementation-package.md
    - docs/releases/S007-implementation-evidence.md
    - docs/releases/S007-acceptance-evidence.md
```

**Decision:** Pending review. This task explicitly excluded commit, push, and deploy — implementation and local verification (`npm test`, `npx tsc --noEmit`) only.
