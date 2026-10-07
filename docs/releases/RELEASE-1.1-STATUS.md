# Release 1.1 — Development Status

**Updated:** 2026-10-07  
**Authority:** Architecture Contract 1.0 · DEVELOPMENT_CHARTER · SEMANTIC_UNDERSTANDING_MVP  
**Release 1.0:** CLOSED (`v1.0.0` → `71b308f`) — do not reopen.

---

## Current release state

**Wave A+B+C ops complete on live DB; tip code pending redeploy for normalizer token-block**

| Wave | Goal | Status |
|------|------|--------|
| A Runtime Truth | tip deploy + Settings singleton + site_url + KP proof | **DONE** — `site_url=https://ukrsibbank.com`; tip includes Settings/KP work |
| B Corpus / SI / KU Phase 0 ops | SI v3 convergence + ready snapshot | **DONE** — SI v3 on all indexed sources; KU snapshot `id=2` READY |
| C Phase 1 Understanding shadow | Observe-only after DFP | **DONE** — flag ON; ranking unchanged; metrics below |

---

## Completed work (tip + ops)

- KP SI/Understanding-grounded generation
- Settings singleton prune + unique index migration `0022`
- Generic `site_url` backfill (`SiteOriginService`)
- Phase 1 shadow module wired at EA §6.1; flag `enable_knowledge_understanding`
- SI v3 URL structural typing fix (`5f9d1a9`)
- Concept normalizer token-block for large corpora (avoids O(C²) ~500M pairwise)
- Ops: `scripts/ops/wave_b_si_batch_upgrade.py`, `scripts/ops/wave_c_phase1_shadow_eval.py`

## Current architecture milestone

Frozen Ask path unchanged:

`QueryPlanner → DFP → EvidencePlanner → Context → Prompt → LLM`

Phase 1 shadow runs **after** DFP inside Evidence Assembly; **never** mutates candidates, EvidencePlanner input, prompt, or answer.

## SI corpus status (post Wave B)

| profile_version | count |
|-----------------|------:|
| source-intelligence-v3 | 4325 |

`needs_intelligence` residual cleared (pending/error/skipped only).

## KU Phase 0 status

| Field | Value |
|-------|------:|
| Ready snapshot id | 2 |
| knowledge_version | 34 |
| concepts | 9661 |
| evidence | 64865 |
| merge strategy | `token_block` (113 562 checks vs ~498M full pairwise) |
| Flag rebuild path | always runs after SI |

`enable_knowledge_understanding` = **true** (Phase 1 observation).

## KU Phase 1 shadow metrics (eval suite, 6 queries)

| Metric | Value |
|--------|------:|
| ranking_unchanged_all | true |
| shadow_enabled_all | true |
| no_failure_all | true |
| avg_overlap_ratio | ~0.23 (dense-correct suite) |
| avg_shadow_ms | ~1986 (over 250ms budget — observe; soft-warn only) |

Non-interference: OFF vs ON selected `hits` source-id lists identical for all queries.

## Remaining Release 1.1 work

1. Redeploy tip with normalizer token-block + ops scripts (`deploy full`) when approved
2. Re-run Wave C eval after dense embedding fix; record latency under budget if possible
3. Explicit decision for Phase 2 assist (not automatic)

## Known debt

- Top Phase 0 concepts still include high-frequency generic labels (`article`, bank name) — inference/quality follow-up inside Understanding, not ranking rules
- Shadow latency over `SHADOW_BUDGET_MS` (250) on first suite — observe + optimize resolve/find path
- Orphaned dashboard trees (DEBT-S008-*) — post-1.1
- DEBT-G10 verify-release tooling — excluded

## Next decision

**Redeploy tip after commit; Phase 2 assist remains OFF until explicit go.**
