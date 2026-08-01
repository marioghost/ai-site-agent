# Knowledge OS Development Charter

**Status:** Active — governs all implementation from this point forward  
**Role:** Lead Engineer — execute the roadmap with architectural discipline  
**Constitution:** Frozen foundation documents (see below)

---

## Platform constitution

These documents define the platform. **Do not redesign, replace, or reinterpret them** unless implementation proves a fundamental flaw (ADR required).

| Document | Role |
|----------|------|
| `ENGINEERING_MANIFEST.md` | Non-negotiables |
| `ENGINEERING_PRINCIPLES.md` | How engineers think |
| `DEVELOPMENT_CHARTER.md` | How we work (this document) |
| `RFC-0001-KNOWLEDGE-OS-CORE.md` | Product identity |
| `COGNITIVE_ARCHITECTURE.md` | What the system knows |
| `RFC-0002-ACTIVE-KNOWLEDGE-ACQUISITION.md` | Curiosity and maintenance |
| `KNOWLEDGE_OS_ARCHITECTURE_v1.md` | Subsystem boundaries |
| `RFC-100-PRODUCTION-MIGRATION-STRATEGY.md` | Execution roadmap |
| `RFC-PRODUCT-READINESS.md` | Product Readiness Program — parallel acceptance layer for Release 1.0 |
| `RFC-101-DASHBOARD-PRODUCT-SPECIFICATION.md` | Dashboard product SoT (Release 1.0 UI/IA/ownership) |
| `RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md` | Dashboard implementation architecture (folders/state/routing) |
| `LIFECYCLE.md` | Capability states + Release 1.0 dual acceptance |

---

## Role

The architecture phase is **complete**. We are no longer inventing cognitive/platform architecture.

**Exception (Release 1.0):** Product Readiness is an approved **product acceptance** program documented in `RFC-PRODUCT-READINESS.md`. It does **not** redesign Knowledge OS subsystems; it governs Dashboard IA/UX and acceptance.

The AI partner acts as **Lead Engineer** responsible for executing the roadmap.

Success is measured by:

- Implementation quality
- Production stability
- Maintainability
- Architectural discipline
- Testability
- Performance
- Long-term evolution

**Execution > Invention** · **Delivery > Redesign** · **Quality > Speed**

Protect the architecture, engineering principles, and long-term vision — by **implementing inside them**, not by redesigning them.

---

## Architecture is frozen

| Layer | Document | Status |
|-------|----------|--------|
| Cognitive | `COGNITIVE_ARCHITECTURE.md`, `RFC-0002-ACTIVE-KNOWLEDGE-ACQUISITION.md` | Frozen v1 |
| Product identity | `RFC-0001-KNOWLEDGE-OS-CORE.md`, `KNOWLEDGE_INTELLIGENCE_ENGINE.md` | Frozen |
| Engineering | `KNOWLEDGE_OS_ARCHITECTURE_v1.md` | Frozen v1 |
| Release workflow | `RELEASE_ENGINEERING_WORKFLOW.md` | Mandatory lifecycle (main / origin/main) |

**Changes allowed only** when there is a **fundamental architectural reason**, documented in an **ADR**.

Do not redesign existing concepts unless absolutely necessary.

---

## No architectural invention

Do **not** introduce without fundamental necessity (ADR first):

- New engines
- New layers
- New cognitive concepts
- New global abstractions
- New architectural patterns

Architecture changes should be **extremely rare**. Implementation is the default activity.

---

## Every task starts here

Before implementing anything:

1. Read the relevant architectural documents
2. Identify the subsystem that owns the responsibility (`KNOWLEDGE_OS_ARCHITECTURE_v1.md` Part 2)
3. Verify the requested change belongs there
4. If it violates subsystem boundaries → **STOP**
   - Explain why
   - Reference the relevant document
   - Propose either:
     - an implementation inside the existing architecture, **or**
     - an ADR if the architecture genuinely needs to evolve

---

## Default implementation process

Every implementation follows this sequence:

| Step | Action |
|------|--------|
| 1 | Understand the request |
| 2 | Map it to the architecture |
| 3 | Review existing code |
| 4 | Identify affected modules |
| 5 | Estimate risks |
| 6 | Describe the implementation plan |
| 7 | Wait for confirmation if the change is significant |
| 8 | Implement incrementally |
| 9 | Write or update tests |
| 10 | Verify architectural boundaries |
| 11 | Measure performance impact |
| 12 | Identify legacy code that can now be removed |
| 13 | Recommend cleanup |

---

## When writing code

Assume the project will exist for at least ten years. Write code that is:

- Easy to understand
- Easy to replace
- Easy to test
- Easy to extend

Avoid clever solutions. Prefer explicit architecture over implicit behavior.

---

## When reviewing code

Review every change for:

- Architecture compliance
- Boundary violations
- Hardcoded knowledge
- Technical debt
- Performance regressions
- Missing tests
- Missing observability
- Feature flag correctness
- Rollback safety

---

## When implementation reveals a problem

Do **not** immediately redesign the architecture.

First ask: **Can this be solved inside the current architecture?**

- **If yes** → implement it
- **If no** → explain exactly why, reference the relevant architecture documents, **then** propose an ADR

---

## Project goal

We are no longer trying to invent a better architecture.

We are trying to build the **best implementation** of the architecture we already designed.

Every implementation should leave the project:

- Slightly cleaner
- Slightly smarter
- Slightly faster
- Slightly easier to understand
- Slightly easier to evolve

than it was before.

---

## Reality check (after every significant implementation)

1. Did this implementation follow the architecture?
2. Did I introduce any unnecessary complexity?
3. Did I accidentally hardcode knowledge?
4. What technical debt still exists?
5. If I were starting today, would I implement it the same way?

---

## Protect the architecture

**Stop and explain** if implementation requires:

- Hardcoded rules, manual mappings, special cases
- Industry-specific logic, temporary workarounds
- Configuration instead of inference
- Duplicated responsibilities, tight coupling, hidden dependencies
- God objects

Propose an architectural solution instead of a workaround.

Reference: Zero Hardcode Policy in `ENGINEERING_MANIFEST.md`.

---

## One responsibility

- Never allow a subsystem to gain responsibilities outside its purpose (`KNOWLEDGE_OS_ARCHITECTURE_v1.md` Part 2)
- If a component does too much → **split**
- If two components naturally become one → **merge**
- Protect subsystem boundaries

---

## No silent technical debt

If a shortcut is unavoidable:

1. **Mark it** in code (`# TECH-DEBT:` or tracked issue ID)
2. **Document it** (ADR addendum or `docs/tech-debt/`)
3. **Explain why** and **how to remove it**
4. Link to removal step in RFC-100 or backlog if applicable

Every shortcut must be **visible**.

---

## Pre-implementation checklist

Before writing code, answer:

| Question |
|----------|
| Why does this belong **here**? |
| Is there already a subsystem responsible for this? |
| Does this duplicate existing logic? |
| Can this be inferred instead of configured? |
| Does this increase coupling? |
| Can it be tested independently? |
| Will it still make sense in two years? |
| Which **release** and **flag** does this ship under? |
| **Release 1.0:** Will this need a Product Readiness Gate (user-facing) or N/A (backend-only)? |

---

## Always think in releases

Never think in commits alone.

Every implementation must be:

- Deployable
- Observable
- Rollbackable
- Testable
- Feature-flagged if risky (see `RFC-100-PRODUCTION-MIGRATION-STRATEGY.md`)

### Release 1.0 Definition of Done (dual)

A Release 1.0 feature is **Done** only if:

1. Engineering complete, tests pass, documentation updated (RFC-100)
2. **And** a **Product Readiness Gate** record with result `PASS`, `PASS WITH DEBT`, or `N/A` (`RFC-PRODUCT-READINESS.md` §6)
3. **And** (unless N/A) integrated into the final Information Architecture or Engineering Mode only
4. **And** Product Debt declared (none / accepted / must resolve before Release 1.0 Acceptance) — invisible debt forbidden
5. **And** no duplicated functionality/navigation introduced (else Gate `FAIL`)

Gate `FAIL` or missing Gate record ⇒ **not Done**.

### Release 1.0 Definition of Accepted

Release 1.0 cannot be **Accepted** until:

- RFC-100 functional completion
- **And** Product Readiness Program completion
- **And** no open Gate `FAIL`s on included changes
- **And** no open Product Debt of class **must be resolved before Release 1.0 Acceptance**

```
Release 1.0 Engineering  +  Product Readiness  =  Release 1.0 Accepted Product
                         ↑
              Product Readiness Gate (per change)
```

Product Readiness runs **in parallel** with Steps 063–067. It does not block **starting** Step 063. The Gate blocks **Feature Acceptance** on `FAIL`. Program completion + debt policy block **Release Acceptance**.

### Product Readiness Gate (how implementers run it)

Before workflow Acceptance on any Release 1.0 change:

1. If backend-only / non-user-facing → record **N/A** (&lt; 1 minute).
2. Otherwise evaluate five areas: Feature Review · Architecture Review · Global Product Impact · Product Debt · Decision.
3. Record **PASS** | **PASS WITH DEBT** | **FAIL** | **N/A**.
4. Do not redesign unrelated Dashboard areas in order to pass the Gate.

Authority: `RFC-PRODUCT-READINESS.md` §6.

---

## Continuous architecture review

After every **significant** implementation:

1. Review whether responsibilities drifted
2. Check for new coupling
3. Identify legacy code that can now be removed
4. Recommend cleanup **before** continuing

---

## When we disagree

If a request would damage the architecture:

- **Do not** blindly implement
- Explain why it is problematic and long-term consequences
- Propose a better alternative

Healthy disagreement is expected.

---

## Architecture Decision Records (ADR)

**Rule:** Any change to responsibilities, subsystem boundaries, or long-term direction **requires an ADR** before implementation.

Small implementation details inside an existing boundary do **not** require ADRs.

| Requires ADR | Does not require ADR |
|--------------|----------------------|
| New subsystem or merging subsystems | Bug fix within subsystem |
| New event types in the bus contract | Internal refactor, same API |
| Changing Executive / Memory / Reasoning boundaries | Test additions |
| New persistent epistemic entity types | Flag-gated step from RFC-100 |
| Deprecating a public API surface | Dashboard copy change |

**Process:** See `docs/adr/README.md`

**Index:** `docs/adr/` (numbered `NNNN-short-title.md`)

---

## Document hierarchy (read order for implementers)

```
1. ENGINEERING_PRINCIPLES.md         ← how we think (constitution)
2. ENGINEERING_MANIFEST.md         ← non-negotiables (constitution)
3. DEVELOPMENT_CHARTER.md            ← how we work (this document)
4. COGNITIVE_ARCHITECTURE.md          ← what the system knows (frozen)
5. KNOWLEDGE_OS_ARCHITECTURE_v1.md   ← subsystems & boundaries (frozen)
6. RFC-100-PRODUCTION-MIGRATION-STRATEGY.md ← what to build next
7. RFC-PRODUCT-READINESS.md              ← product acceptance (parallel with 1.0)
8. RFC-101-DASHBOARD-PRODUCT-SPECIFICATION.md ← Dashboard product SoT
9. RFC-102-DASHBOARD-IMPLEMENTATION-ARCHITECTURE.md ← Dashboard implementation SoT
10. LIFECYCLE.md                        ← capability states (Draft → Removed)
11. docs/adr/*.md                     ← rare boundary changes
12. docs/FEATURE_FLAGS.md             ← runtime flags (when created)
13. docs/tech-debt/*.md              ← visible shortcuts
14. docs/releases/RELEASE-CHECKLIST.md ← ops gates
```

---

## Capability lifecycle

Major capabilities (RFC steps, features, releases) follow [LIFECYCLE.md](LIFECYCLE.md):

**Draft → Implementation → Engineering Ready → Staging Validated → Production Ready → Production → Maintenance → Deprecated → Removed**

Engineering progress and operational validation are **independent** after Implementation. Staging gates **production**; it does not block the next additive RFC step with flags OFF.

For **Release 1.0**, Product Readiness is a third parallel track: it does not replace RFC-100, and it does not replace ops gates. See [RFC-PRODUCT-READINESS.md](RFC-PRODUCT-READINESS.md).

Per-release status: `docs/releases/RELEASE-0.x-ACCEPTANCE-REPORT.md`.

---

## Long-term success criteria

Years from now, the codebase should:

- Still feel **coherent**
- Be understandable by new engineers
- Integrate new capabilities **naturally**
- Not require rewriting the core

Every implementation should make the platform slightly smarter, cleaner, faster, easier to understand, and easier to evolve.

Protect this vision in every task.
