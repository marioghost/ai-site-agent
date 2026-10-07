# RELEASE 1.1 LIVE ACCEPTANCE & PHASE 1 SHADOW REPORT

**Date:** 2026-10-07  
**Production tip at start:** `6bbe2f9`  
**Post-fix tip (pending deploy):** see git log after this report  
**Validation tenant:** current production corpus (not architecture target)

---

## 1. Wave A — runtime / KP

| Check | Result |
|-------|--------|
| Settings singleton | 1 row |
| `site_url` | `https://ukrsibbank.com` |
| KU flag | ON |
| KP identity | organization/display set; 3 important topics; 7 intents |
| KP regen after KV-aligned READY | Ran; Understanding matched KV |
| KP topic quality gate | Raw regen collapsed to org/news topics — **kept prior topic set**, restored subject from topics |

**Wave A:** PASS (with KP topic-preservation gate after noisy KU-fed discovery).

---

## 2. KU READY inspection

| Snapshot | Status | KV | Concepts | Evidence |
|----------|--------|---:|--------:|---------:|
| 2 (initial deploy) | ready | 34 | 9661 | 64865 |
| 4 (ops rebuild) | ready | 37 | 9658 | 64813 |
| **5 (after entity-echo fix)** | **ready** | **38** | **9654** | **60628** |

**KV alignment:** Fixed — `latest_ready` id=5 matches KnowledgeVersion 38.

**Quality (id=5):**
- `article` / `document` concept flood **removed** (was 3707 / 172)
- Remaining head still org-name / news lexical dominance (`UKRSIBBANK`, `Новини`, …) — SI main_topic quality debt
- Aliases present on ~35% of concepts (pre-fix baseline)
- Merge: `token_block` (~113k checks)

---

## 3. SI corpus

| Bucket | Count |
|--------|------:|
| indexed `source-intelligence-v3` | 4325 |
| indexed v2 / empty / other | **0** |
| pending (no profile) | 669 |
| error | 21 |
| skipped | 5 |
| `needs_intelligence` | 0 |

**SI v3 reprocess:** NOT required for indexed corpus (already converged).

---

## 4. Phase 1 shadow — non-interference

Full suite (12 queries) on live tip before builder fix; spot re-check after snap 5:

| Metric | Value |
|--------|------:|
| ranking_unchanged_all | **true** |
| failure_rate | 0.0 |
| concept_resolution_success | 1.0 |
| snapshot_availability | 1.0 |
| overlap mean / median / p50 | 0.22 / 0.10 / 0.20 |
| understanding_only mean | ~23 (diagnostics only; not ranked) |
| latency p50 / p95 / max | 2406 / 2516 / 2717 ms |

**Shadow is observe-only:** OFF vs ON selected hit source-id lists identical.

Latency exceeds soft budget 250ms — debt (Optimization), not ranking interference.

---

## 5. Live Ask QA (historical failure classes)

| Case | Outcome | Owner |
|------|---------|-------|
| org overview UK/EN | Weak promo-framed answers from homepage | Retrieval / Evidence / Corpus |
| org benefits | No information | Retrieval / Evidence |
| product benefits | Acceptable card benefits | — |
| cash loan family | Partial; generation typo | Generation |
| life insurance | Correctly limited / redirects to business insurance | Evidence / Corpus |
| deposit rates | No information | Retrieval / Corpus |
| branch locator | Weak homepage guidance | Retrieval / UX |
| privacy policy | Cookie policy contamination | Retrieval |
| unsupported geo | Correct refuse | — |
| short ambiguous | Weak generic | Retrieval |
| UK/EN quality | Mixed; about-bank paths better | Retrieval / Generation |
| truncation / degenerate | None observed | — |
| news / wrong-product contamination | Overview/privacy weak; not Phase-1-caused | Retrieval |

**Phase 1 did not cause these** (shadow zero ranking effect).

---

## 6. Fixes in Release 1.1 scope

1. **Ops:** KU rebuild to clear KV drift (READY behind KV after stopped SI finalize).
2. **Code (Understanding):** skip SI purpose/content-kind `entity_type` echoes as concepts (`builder.py`) — removes corpus-wide `article`/`document` concepts.
3. **Ops:** KP regen with topic-preservation when Understanding-fed discovery collapses to org/news.
4. **Scripts:** `release_11_live_acceptance.py`, KU-only batch path.

**Not done (correctly):** Phase 2 ranking assist; bank-specific heuristics; SI full reprocess; Library pending/error crawl (corpus ops, separate).

---

## 7. Tests

| Gate | Result |
|------|--------|
| `make test-backend` | PASS |
| `make test-dashboard` | PASS |
| `make release-check` | PASS |

---

## 8. Independent reviews (concise)

**Staff Engineer:** Shadow contract holds; KV/READY lifecycle debt was real and fixed; Ask gaps are retrieval/corpus, not flag wiring.

**Software Architect:** No boundary redesign; Understanding owns concept extraction filter; SI v3 convergence closed for indexed set.

**AI Architect:** Phase 1 validated as observe-only; concept quality improved for content-kind echo; remaining org/news main_topic dominance is SI→KU inference debt, not ranking.

**Product/UX:** Agent usable; overview/rates/benefits still weak — product acceptance should weigh Ask quality separately from Phase 1 shadow completeness.

---

## 9. Remaining debt

- Shadow latency ≫ 250ms budget  
- SI `main_topic` often org/news chrome  
- Library: 669 pending, 21 errors, ~3397 refresh-due  
- Multiple historical READY rows (2/4 superseded by 5) — cleanup optional  
- Ask overview/rates/benefits quality (not Phase 1)

## 10. Next decision

Deploy tip with Understanding builder fix → re-smoke shadow + one Ask overview.  
Phase 2 assist remains **explicit go required**.  
Product acceptance on Ask quality is a **separate** gate from Phase 1 shadow validation.
