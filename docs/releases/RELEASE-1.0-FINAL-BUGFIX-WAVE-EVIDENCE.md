# Release 1.0 — Final Bugfix / UX Wave Evidence

```
Program: docs/releases/1.0-rfc-101-master-program.md
Related: Brutal UX audit · Final Bugfix review · Staff commit review · Stabilization
```

**Date:** 2026-08-05  
**Prior deployed tip:** `afa28daac8c6fbebf675c5d4a4d0495ea49f6ac9`  
**Wave status:** Included on `main` in this commit · push/deploy follow separately

## Scope

Frontend-only Release 1.0 bugfix + UX polish + stabilization on top of Product
Completion tip `afa28da`.

## Explicit non-claims

- Does **not** claim Product Accepted Product / Final Acceptance.
- Does **not** claim G9-P2 cold-demo execution complete until run on the post-deploy tip.
- Does **not** claim G9-P3 accessibility execution complete until run on the post-deploy tip.
- Engineering metadata `accepted=1.0` / Step 067 remains engineering closure only — not Product Accepted Product.

## Blockers closed in source

| ID | Resolution |
|----|------------|
| BF-001 | Home readiness excludes skipped via `lib/homeReadiness.ts` / `deriveHomeModel` |
| BF-002 | Activity search labeled page-local; empty vs no-match |
| BF-003 | Focused + behavioral helpers and wave tests |
| Staff-P1 Performance empty | `evaluatePerformancePresence` meaningful-data gates |
| Staff-P1 Home health trust | `healthChecklistCopyKey` — unknown ≠ degraded |
| Staff-P1 Activity errors | ErrorState + retry |
| Staff-P1 tsc tests | `@types/node` + tests in `tsc --noEmit` |

## Local verification (implementation machine)

| Check | Result |
|-------|--------|
| `cd dashboard && npm test -- --run` | **402 passed** |
| `cd dashboard && npx tsc --noEmit` | **OK** |
| `cd dashboard && npm run build` | **OK** (dist discarded) |

## Still open (mandatory before Accepted Product)

| Item | Class |
|------|--------|
| G9-P2 cold-demo on deployed post-wave tip | must_resolve_before_1_0_acceptance |
| G9-P3 accessibility on deployed post-wave tip | must_resolve_before_1_0_acceptance |
| Runtime validation of the post-wave tip | process |
| Final Acceptance | process |
