# Capability lifecycle

**Scope:** Any major capability — RFC-100 step, subsystem feature, release artifact, API surface, or Release 1.0 product surface.  
**Not in scope:** Architecture design (see constitution docs) or RFC-100 step ordering.

This document defines **states only**. Release-specific status (e.g. 0.3) lives in acceptance reports.

**Release 1.0 dual acceptance:** From Release 1.0 onward, **Engineering Ready / Feature Done** for any change requires Functional Acceptance **and** a **Product Readiness Gate** result of `PASS`, `PASS WITH DEBT`, or `N/A`. See [RFC-PRODUCT-READINESS.md](RFC-PRODUCT-READINESS.md) §6 and § “Release 1.0 acceptance model” below.

---

## Lifecycle overview

```
Draft → Implementation → Product Readiness Gate → Engineering Ready → Staging Validated
  → Production Ready → Production → Maintenance → Deprecated → Removed
```

(The Gate is skipped as a full review only when result is **N/A** for backend-only / non-user-facing work; the **N/A record is still required**.)

**Three tracks after Implementation (Release 1.0):**

- **Engineering track** — code, tests, RFC-100 sequence (`make release-check`)
- **Product Readiness track** — IA, UX, Engineering Mode, simplicity; **enforced by Product Readiness Gate** (parallel; not a deploy stage)
- **Operations track** — deploy, smoke, production (`make deploy-smoke`)

```
Release 1.0 Engineering  +  Product Readiness  =  Release 1.0 Accepted Product
                         ↑
              Product Readiness Gate (per change)
```

Operations gates **Production Ready** and **Production**.  
Product Readiness gates **Release 1.0 Accepted Product** (together with functional completion).  
Neither Product Readiness nor operations blocks **starting** the next additive RFC-100 step (flags OFF), but the **Gate blocks Feature Acceptance** on `FAIL`, and Product Readiness **blocks accepting** Release 1.0 while Program incomplete or must-resolve debt remains.

---

## State reference

| State | Purpose |
|-------|---------|
| **Draft** | Intent captured; not yet implemented |
| **Implementation** | Active development on branch or step |
| **Engineering Ready** | Deliverable complete; engineering gate passed **and** Product Readiness Gate ∈ {PASS, PASS WITH DEBT, N/A} |
| **Staging Validated** | Verified on real staging environment |
| **Production Ready** | Approved for production deployment |
| **Production** | Live for users/operators |
| **Maintenance** | Supported; limited change scope |
| **Deprecated** | Sunset announced; default OFF or legacy path only |
| **Removed** | No longer present in codebase or runtime |

---

### Draft

| | |
|---|---|
| **Entry** | RFC step approved, ADR accepted, or feature scoped |
| **Exit** | Implementation started (first commit or branch) |
| **Allowed** | Docs, RFCs, ADRs, spikes without production path |
| **Not allowed** | Production deploy; default-ON flags; schema without migration plan |

### Implementation

| | |
|---|---|
| **Entry** | Code or migration work in progress |
| **Exit** | `make release-check` passes; step deliverables complete; **Release 1.0:** Product Readiness Gate recorded (`PASS` / `PASS WITH DEBT` / `FAIL` / `N/A`) |
| **Allowed** | Feature branches; additive migrations (flags OFF); unit/golden tests; parallel Product Readiness work |
| **Not allowed** | Marking Engineering Ready without `release-check`; production deploy; Feature Acceptance with Gate `FAIL` or missing Gate record |

### Engineering Ready

| | |
|---|---|
| **Entry** | `make release-check` green; step/release deliverables merged or accepted; **Release 1.0:** Product Readiness Gate ∈ {PASS, PASS WITH DEBT, N/A} |
| **Exit** | Staging validation begins (deploy to staging) **or** next step starts while ops pending |
| **Allowed** | Next RFC step (sequence permitting); merge to main; local/staging experiments; parallel Product Readiness program work |
| **Not allowed** | Marking Production Ready; production deploy; flag ON in production without staging proof; marking **Release 1.0 Accepted** without Product Readiness Program complete / with open must-resolve Gate debt |

**Engineering gate:** `make release-check`  
**Product gate (Release 1.0):** [RFC-PRODUCT-READINESS.md](RFC-PRODUCT-READINESS.md) §6 Product Readiness Gate

### Staging Validated

| | |
|---|---|
| **Entry** | `make deploy` + `make smoke` on Linux staging; indexing/chat recorded per [STAGING-SEED-SMOKE.md](STAGING-SEED-SMOKE.md) |
| **Exit** | Production-ready checklist complete |
| **Allowed** | Production-ready review; flag-ON experiments **on staging only** |
| **Not allowed** | Production deploy; treating as Production Ready without checklist |

**Operations gate:** `make deploy-smoke`, `SMOKE_CHAT=1 make smoke`

### Production Ready

| | |
|---|---|
| **Entry** | Staging Validated + rollback verified + [RELEASE-CHECKLIST.md](releases/RELEASE-CHECKLIST.md) sign-off |
| **Exit** | Successful production deployment |
| **Allowed** | Production deploy; controlled flag rollout per RFC-100 |
| **Not allowed** | Deploy without rollback owner; skip migrations |

### Production

| | |
|---|---|
| **Entry** | Deployed to production; smoke green on prod URL |
| **Exit** | Capability enters Maintenance (stable) or Deprecated (sunset) |
| **Allowed** | Bugfixes; flag changes per runbook; monitoring |
| **Not allowed** | Undocumented breaking changes; flag ON without rollback path |

### Maintenance

| | |
|---|---|
| **Entry** | Stable in production; active support |
| **Exit** | Deprecation announced |
| **Allowed** | Fixes, observability, security patches within boundaries |
| **Not allowed** | New product scope without new lifecycle from Draft |

### Deprecated

| | |
|---|---|
| **Entry** | Sunset announced; default OFF or legacy-only path documented |
| **Exit** | Removal scheduled/completed |
| **Allowed** | Migration guides; read-only access; rollback to legacy path |
| **Not allowed** | New dependents; default ON for new installs |

### Removed

| | |
|---|---|
| **Entry** | Code/schema/API excised; migrations applied |
| **Exit** | — (terminal) |
| **Allowed** | Historical docs, ADRs, release notes |
| **Not allowed** | Runtime references; silent reintroduction without Draft |

---

## Engineering vs operations (critical rule)

| Situation | Next RFC step (Engineering Ready) | Production deploy |
|-----------|-----------------------------------|-------------------|
| Staging unavailable | **Allowed** | **Blocked** |
| Sudo / infra blocked | **Allowed** | **Blocked** |
| Staging Validated pending | **Allowed** (additive, flags OFF) | **Blocked** |
| Product Readiness incomplete / Gate FAIL | **Next 1.0 step may start**; **Feature Acceptance blocked** on Gate `FAIL` or missing record | **Blocked** for Release 1.0 Accepted Product |

Behavior-changing capabilities (e.g. shadow writes, flag default ON) require **Staging Validated** proof before **Production**, even if engineering continues.

---

## Release 1.0 acceptance model

### Definition of Done (feature)

A Release 1.0 feature is Done only if:

1. Engineering complete, tests pass, docs updated (RFC-100 / charter)
2. **Product Readiness Gate** result ∈ {PASS, PASS WITH DEBT, N/A}
3. Integrated into final Information Architecture (or Engineering Mode only) when not N/A
4. Visual consistency verified for touched surfaces
5. No duplicated functionality or navigation introduced (else Gate FAIL)
6. Product Debt declared (none / accepted / must resolve before 1.0 Acceptance)

### Definition of Accepted (release)

Release 1.0 cannot be accepted until:

1. All RFC-100 Release 1.0 functionality completed  
2. **AND** Product Readiness Program completed  
3. **AND** Dashboard satisfies simplicity principles  
4. **AND** Information Architecture finalized  
5. **AND** Engineering functionality properly isolated  
6. **AND** no included change has Gate `FAIL` or missing Gate record  
7. **AND** no open Product Debt of class **must be resolved before Release 1.0 Acceptance**

Ops promotion (`staging_validated`, `production_ready`) remains governed by this lifecycle’s Staging / Production Ready states and is **not** implied by Product Readiness alone.

---

## RFC-100 mapping

| RFC-100 concept | Lifecycle state |
|-----------------|-----------------|
| Step in progress | Implementation |
| Step accepted + `release-check` + Gate ∈ {PASS, PASS WITH DEBT, N/A} | Engineering Ready |
| Staging smoke recorded | Staging Validated |
| Checklist + sign-off | Production Ready |
| Live in prod | Production |
| Release 1.0 Accepted Product | Functional closure **∧** Product Readiness Program complete **∧** Gate debt policy |

Migration **sequence** remains in RFC-100 §13.1 — lifecycle does not replace step order.  
Product Readiness Gate is defined in RFC-PRODUCT-READINESS §6.

---

## Where status is recorded

| What | Document |
|------|----------|
| Lifecycle definitions | This file |
| Ops checklist | [releases/RELEASE-CHECKLIST.md](releases/RELEASE-CHECKLIST.md) |
| Deploy commands | [DEPLOYMENT.md](DEPLOYMENT.md) |
| Per-release status | `docs/releases/RELEASE-0.x-ACCEPTANCE-REPORT.md` |
| Product Readiness + Gate | [RFC-PRODUCT-READINESS.md](RFC-PRODUCT-READINESS.md) |

---

## Cross-references

- [DEVELOPMENT_CHARTER.md](DEVELOPMENT_CHARTER.md) — how we implement
- [RFC-100-PRODUCTION-MIGRATION-STRATEGY.md](RFC-100-PRODUCTION-MIGRATION-STRATEGY.md) — what to build
- [RFC-PRODUCT-READINESS.md](RFC-PRODUCT-READINESS.md) — product acceptance layer + **Product Readiness Gate**
- [STAGING-SEED-SMOKE.md](STAGING-SEED-SMOKE.md) — staging validation procedure
- [RELEASE_ENGINEERING_WORKFLOW.md](RELEASE_ENGINEERING_WORKFLOW.md) — merge / push / deploy discipline
