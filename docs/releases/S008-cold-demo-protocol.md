# S008 — Cold-Demo Protocol (Mode-off)

```
Program: docs/releases/1.0-rfc-101-master-program.md
Package IDs: G9-P2
Inventory findings: A6.2, A9.1
Execution Strategy: docs/releases/1.0-rfc-101-execution-strategy.md
```

**Step:** S008
**Authority:** `docs/releases/S008-implementation-package.md`
**Status:** **Protocol only.** This document defines a repeatable checklist. It does **not** claim the checklist has been run against a live/deployed instance. Runtime execution (screenshots, session recording, or a real first-time-user trial) is a separate, later, explicitly authorized task per the Master Program's own rule: *"execution evidence only when surfaces claim complete"* (§7, G9-P2 row).

---

## 1. Purpose

RFC-101 §8.1/§8.2 and `RFC-PRODUCT-READINESS.md` §9 ("Product Validation: First-time user / cold demo without coaching") require that Release 1.0 Accepted Product be demonstrable to a new operator with **Engineering Mode off** and **no developer coaching**. This protocol is the fixed checklist that a later execution task must follow and record against.

## 2. Preconditions for execution (not evaluated here)

- A running Dashboard build reachable by the reviewer, logged in as each of `admin`, `operator`, `viewer` in turn
- Engineering Mode toggle left in its **default (off)** state for the core walkthrough (§4); a second, explicit Mode-on pass is optional and separately noted (§5)
- Reviewer has no prior product-specific coaching beyond this checklist and the product's own in-app copy/empty-states

## 3. Roles covered

| Role | Included in cold-demo? |
|------|------------------------|
| `admin` | Yes — full walkthrough |
| `operator` | Yes — full walkthrough minus admin-only Settings/Access |
| `viewer` | Yes — read-only walkthrough (no mutating actions) |

## 4. Mode-off checklist (core cold demo)

Each row is a pass/fail observation to record at execution time — this protocol does not pre-fill any result.

### 4.1 Landing / Home

- [ ] Logging in lands on `/home` (not `/overview`, not a blank/legacy screen) for all three roles
- [ ] Home shows a readiness state (not a wall of unrelated charts/widgets) — RFC-101 §7 Home contract
- [ ] Home surfaces a clear "next action" / setup checklist without requiring the reviewer to already know the product's internal module names
- [ ] Home has no visible "Overview" label or link anywhere in its own chrome

### 4.2 No Overview home

- [ ] There is no "Overview" entry in the left/top navigation for any role
- [ ] Visiting `/overview` directly redirects to `/home` and does not show a full legacy widget page
- [ ] Visiting `/` (root) and any unknown path redirect to `/home`, not to a 404 or blank page

### 4.3 Knowledge

- [ ] The reviewer can find "Library", "Update", and "Site" under a single "Knowledge" nav group without being told what the words mean beforehand
- [ ] Library shows source/knowledge-base readiness without requiring a jump to a separate "Sources" or "Indexing" screen
- [ ] Update lets the reviewer trigger a refresh/reindex action and see job status without leaving the screen
- [ ] Visiting legacy `/sources`, `/indexing`, `/knowledge-profile` redirects into the corresponding Knowledge screen rather than 404ing

### 4.4 Ask

- [ ] The reviewer can find "Ask" in the top-level nav (not "Chat" or "Chat Test")
- [ ] Asking a question returns an answer with visible sources, with no engineering diagnostics panel, trace viewer, or pipeline dump shown by default
- [ ] There is exactly one entry point to ask a question (no second "chat" surface competing for attention)
- [ ] Visiting legacy `/chat` redirects into `/ask`

### 4.5 Insights

- [ ] The reviewer can find "Performance" and "Activity" under a single "Insights" nav group
- [ ] Performance shows the full analytics surface (KPIs, trends, popular/problematic queries) without needing Engineering Mode
- [ ] Activity shows past questions/requests as the one place to look for history (no second "Logs" page competing for the same job)
- [ ] Visiting legacy `/analytics`, `/logs` redirects into the corresponding Insights screen

### 4.6 Settings

- [ ] The reviewer can find General, Models, Answers, and Access as four distinct, clearly named Settings children (not one long monolithic page)
- [ ] Answers shows the four response modes (Automatic/Fast/Balanced/High precision) without an accompanying retrieval-tuning knob panel
- [ ] Access (admin/operator only) is where user management lives — there is no separate top-level "Users" page competing for that job
- [ ] `viewer` cannot reach Access at all (redirected/blocked, not shown a broken page)
- [ ] Visiting legacy `/users` redirects into `/settings/access`

### 4.7 Engineering Mode behavior (off by default)

- [ ] With Mode off, there is no "Engineering" section in the nav for any role
- [ ] With Mode off, navigating directly to any `/engineering/*` URL does not render engineering content (redirect/block observed instead)
- [ ] The Mode toggle itself lives in Settings → General and is off by default for a fresh session

## 5. Optional Mode-on pass (not part of the cold-demo claim)

A cold demo is, by definition, Mode-off. A separate, clearly labeled Mode-on pass may additionally record:

- [ ] Toggling Mode on in General reveals an "Engineering" nav group with exactly 6 destinations (Status, Ask details, Knowledge, Tensions, Advanced, Build)
- [ ] Turning Mode back off hides the Engineering group again without a page reload being required to "lose" access

## 6. Recording results

A future execution task must attach, per role and per section above:

- Pass/fail per checklist row
- Screenshot or short recording reference for any fail
- Reviewer identity/date
- Link back to this protocol document

No result table is pre-filled in this document — doing so without an actual run would be a false Gate PASS, which `RFC-PRODUCT-READINESS.md` and the Master Program's risk model (§10, "False Gate PASS") explicitly forbid.

## 7. Relationship to Product Readiness Gate

This protocol satisfies the **protocol-authoring** half of package `G9-P2`. The **execution** half (`G9-P2 execution` in the Master Program's dependency table, §4.2) remains open and is not claimed complete by this document. `docs/releases/S008-product-readiness-gate.md` records this distinction explicitly.
