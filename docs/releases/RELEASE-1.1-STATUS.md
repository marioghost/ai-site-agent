# Release 1.1 — Development Status

**Updated:** 2026-10-07  
**Authority:** Architecture Contract 1.0 · DEVELOPMENT_CHARTER · SEMANTIC_UNDERSTANDING_MVP  
**Release 1.0:** CLOSED (`v1.0.0` → `71b308f`) — do not reopen.

---

## Current release state

**IN DEVELOPMENT — Wave A deploy blocked on host sudo TTY**

| Wave | Goal | Status |
|------|------|--------|
| A Runtime Truth | tip deploy + Settings singleton + site_url + KP proof | **PARTIAL** — code on `main`; production still `7b5548d` until `deploy full` |
| B Corpus / SI / KU Phase 0 ops | SI v3 convergence + ready snapshot | **NOT STARTED** (blocked on Wave A deploy) |
| C Phase 1 Understanding shadow | Observe-only after DFP | **CODE READY** on tip (flag default OFF) |

---

## Completed work (tip)

- KP SI/Understanding-grounded generation (`5177999` and earlier)
- Settings singleton prune + unique index migration `0022`
- Generic `site_url` backfill from dominant indexed origin (`SiteOriginService`)
- Phase 1 shadow module (`knowledge_understanding/shadow.py`) wired at EA §6.1 insertion point
- Rebuild soft-fail now persists `stopped` / `failed` error snapshots (root-cause aid for empty table)

## Current architecture milestone

Frozen Ask path unchanged:

`QueryPlanner → DFP → EvidencePlanner → Context → Prompt → LLM`

Phase 1 shadow runs **after** DFP inside Evidence Assembly; **never** mutates candidates, EvidencePlanner input, prompt, or answer.

## SI corpus status (last measured pre-Wave-B)

| profile_version | count |
|-----------------|------:|
| source-intelligence-v2 | ~2490 |
| source-intelligence-v3 | ~907 |
| empty | ~217 |

## KU Phase 0 status

- Schema `0021` present on production
- Tables empty: **zero** snapshots (ready or error) at audit/resume time
- Likely cause: rebuild soft-fail/stop without durable record historically; and/or finalize never completed embedding rebuild after Phase 0 ship
- Flag `enable_knowledge_understanding=false`

## KU Phase 1 shadow metrics

Not yet measured on production (requires Wave A deploy + Wave B ready snapshot + flag ON for observation).

## Remaining Release 1.1 work

1. Operator: `sudo bash deploy/manage_deploy.sh deploy full` on tip
2. Wave A KP live regenerate proof
3. Wave B SI v3 controlled reprocess + Understanding ready snapshot proof
4. Wave C enable shadow flag for evaluation suite; record overlap/latency; keep ranking OFF
5. Explicit decision for Phase 2 assist (not automatic)

## Known debt

- Dual Settings row (addressed by `0022` once migrated)
- Orphaned dashboard trees (DEBT-S008-*) — post-1.1
- DEBT-G10 verify-release tooling — excluded
- Knowledge route RBAC deep-link gap (viewer) — separate fix

## Next decision

**Run canonical `deploy full` for tip `main`, then resume Wave A acceptance → Wave B SI/KU ops.**
