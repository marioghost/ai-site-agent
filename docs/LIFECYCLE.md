# Capability lifecycle

**Scope:** Any major capability — RFC-100 step, subsystem feature, release artifact, or API surface.  
**Not in scope:** Architecture design (see constitution docs) or RFC-100 step ordering.

This document defines **states only**. Release-specific status (e.g. 0.3) lives in acceptance reports.

---

## Lifecycle overview

```
Draft → Implementation → Engineering Ready → Staging Validated → Production Ready
  → Production → Maintenance → Deprecated → Removed
```

**Two tracks after Implementation:**

- **Engineering track** — code, tests, RFC sequence (`make release-check`)
- **Operations track** — deploy, smoke, production (`make deploy-smoke`)

Operations gates **Production Ready** and **Production**. It does **not** block **Engineering Ready** or the next additive RFC step (flags OFF).

---

## State reference

| State | Purpose |
|-------|---------|
| **Draft** | Intent captured; not yet implemented |
| **Implementation** | Active development on branch or step |
| **Engineering Ready** | Deliverable complete; engineering gate passed |
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
| **Exit** | `make release-check` passes; step deliverables complete |
| **Allowed** | Feature branches; additive migrations (flags OFF); unit/golden tests |
| **Not allowed** | Marking Engineering Ready without `release-check`; production deploy |

### Engineering Ready

| | |
|---|---|
| **Entry** | `make release-check` green; step/release deliverables merged or accepted |
| **Exit** | Staging validation begins (deploy to staging) **or** next step starts while ops pending |
| **Allowed** | Next RFC step (sequence permitting); merge to main; local/staging experiments |
| **Not allowed** | Marking Production Ready; production deploy; flag ON in production without staging proof |

**Engineering gate:** `make release-check`

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

Behavior-changing capabilities (e.g. shadow writes, flag default ON) require **Staging Validated** proof before **Production**, even if engineering continues.

---

## RFC-100 mapping

| RFC-100 concept | Lifecycle state |
|-----------------|-----------------|
| Step in progress | Implementation |
| Step accepted + `release-check` | Engineering Ready |
| Staging smoke recorded | Staging Validated |
| Checklist + sign-off | Production Ready |
| Live in prod | Production |

Migration **sequence** remains in RFC-100 §13.1 — lifecycle does not replace step order.

---

## Where status is recorded

| What | Document |
|------|----------|
| Lifecycle definitions | This file |
| Ops checklist | [releases/RELEASE-CHECKLIST.md](releases/RELEASE-CHECKLIST.md) |
| Deploy commands | [DEPLOYMENT.md](DEPLOYMENT.md) |
| Per-release status | `docs/releases/RELEASE-0.x-ACCEPTANCE-REPORT.md` |

---

## Cross-references

- [DEVELOPMENT_CHARTER.md](DEVELOPMENT_CHARTER.md) — how we implement
- [RFC-100-PRODUCTION-MIGRATION-STRATEGY.md](RFC-100-PRODUCTION-MIGRATION-STRATEGY.md) — what to build
- [STAGING-SEED-SMOKE.md](STAGING-SEED-SMOKE.md) — staging validation procedure
