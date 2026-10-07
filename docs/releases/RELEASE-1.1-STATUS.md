# Release 1.1 — Development Status

**Updated:** 2026-10-07  
**Authority:** Architecture Contract 1.0 · DEVELOPMENT_CHARTER · SEMANTIC_UNDERSTANDING_MVP  
**Release 1.0:** CLOSED — do not reopen.

**Live acceptance report:** `docs/releases/RELEASE-1.1-LIVE-ACCEPTANCE.md`

---

## Current release state

| Wave | Status |
|------|--------|
| A Runtime Truth | **PASS** |
| B SI / KU Phase 0 | **PASS** — SI v3=4325/4325; READY snap **id=7 KV=40** (3522 concepts / 9371 evidence) |
| C Phase 1 shadow | **VALIDATED** — observe-only; warm p50≈24ms after cache |
| D Product quality completion | **PASS with accepted debt** — Ask retrieval P1 classes fixed generically |

Architecture Contract 1.0 remains frozen. Phase 2 ranking assist was **not** implemented.

---

## Product quality completion (this wave)

Generic fixes (no tenant hardcode):

- SI structural topic rejection + Understanding content-kind entity echo filter
- Phase 1 shadow process-local READY snapshot cache + vectorized resolve
- Lexical morphology for FTS `simple` (inflected query tokens)
- News/promo flood refill via purpose→document_type exclusion
- QueryUnderstanding: UK org overview, rates→pricing, locator/policy expectations
- Focus/authority: career false-positive on «Робота відділення»; product-path vs locator; packer protects exact-match evidence
- Answer-trace UniqueViolation no longer poisons the DB session

---

## Remaining (classified)

| Class | Items |
|-------|--------|
| ACCEPTED DEBT | EN overview can still latch onto charity/service pages; org “benefits” leans awards; life-insurance has no stable non-news product page |
| CORPUS OPS | 669 pending, 21 errors, ~3397 refresh-due — triage separately |
| PHASE 2+ | Ranking assist; ANN; sub-250ms cold-start without process cache |

---

## Release decision

See live acceptance report — recommend **close Release 1.1**.
