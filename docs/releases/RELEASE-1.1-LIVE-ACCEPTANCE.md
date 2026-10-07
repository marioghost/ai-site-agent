# RELEASE 1.1 LIVE ACCEPTANCE & PRODUCT QUALITY COMPLETION

**Date:** 2026-10-07  
**Prior production tip:** `6bbe2f9`  
**Code tip for this wave (pre-deploy):** workspace `main` ahead of `a2ad863` with quality fixes  
**Expected deploy SHA after push:** tip of `origin/main` after product-quality commits  
**Validation tenant:** current production corpus (not architecture target)

---

## 1. Deployment / identity

| Check | Result |
|-------|--------|
| Prior deployed tip | `a2ad863` (Understanding entity-echo fix) |
| Local / origin before this wave | `a2ad863` |
| KU flag | ON |
| SI indexed | 4325 / 4325 `source-intelligence-v3` |
| KU READY | **id=7**, KnowledgeVersion=**40**, concepts=**3522**, evidence=**9371** |
| `article` / `document` concepts | **0** |

Canonical deploy after push: `sudo bash deploy/manage_deploy.sh deploy full`

---

## 2. Concept-quality audit (snap 7)

| Signal | Observation |
|--------|-------------|
| Concept count | 9654 → **3522** after SI rules refresh + rebuild |
| Head | Still includes org name + some news titles (SI main_topic = page title on news) |
| Content-kind echoes | Removed |
| Structural «Новини» as topic | Suppressed at SI rules + builder |

Remaining org/news lexical head is **SI inference debt**, not Phase 1 ranking.

---

## 3. SI main_topic RCA

**Path:** page → SI rules/LLM → `main_topic` / keywords → UnderstandingBuilder → concepts  

**Root causes addressed (generic):**

1. Structural section/title labels used as topics → rejected in `source_semantic_rules`
2. Content-kind `entity_type` (`article`/`document`) echoed as concepts → filtered in builder
3. Single-token keyword crumbs as subtopics → skipped

**Not done:** tenant blacklists; bank-specific vocabulary.

---

## 4. Shadow latency RCA + optimization

| Stage | Before | After (warm) |
|-------|--------|--------------|
| Dominant cost | Per-request READY load ~1.8s + Python resolve ~0.45s | Process-local immutable snapshot cache + numpy resolve |
| p50 | ≈2406 ms | **≈24 ms** (acceptance harness) |
| p95 | ≈2516 ms | **≈27 ms** |
| Soft budget | 250 ms | **Met when warm** |
| Cold | — | First load still ~1–1.5s (accepted) |

No new vector DB / Redis / ANN.

---

## 5. Ask QA — before vs after (representative classes)

| Case | Before | After | Owner |
|------|--------|-------|-------|
| Org overview UK | Homepage promo / weak | about-bank + homepage; coherent overview | RETRIEVAL fixed |
| Org overview EN | Weak | Mixed (charity/service pages) | ACCEPTED DEBT |
| Org benefits | Empty / no info | about-bank pages; award-leaning | P2 wording |
| Deposit rates | Empty (news filtered) | Deposit product/pricing pages with rates | RETRIEVAL fixed |
| Branch locator | Homepage / wrong | **branches-atms** selected | RETRIEVAL fixed |
| Privacy | Cookie only | Personal-data notice + informational security | RETRIEVAL fixed |
| Cash loan | Credit-card contamination | consumer-cash-loan retained | EVIDENCE/packer fixed |
| Unsupported geo | Correct refuse | Correct refuse | — |
| Life insurance | Limited | Still weak (mostly news/business insurance in corpus) | CORPUS GAP |
| Truncation / degenerate | None | None (after trace-session fix) | — |

Harness note: duplicate `answer_traces.request_id` previously aborted the Session mid-suite — fixed in `RagService._store_trace` rollback + unique harness ids.

---

## 6. Corpus operations

| State | Count | Meaning |
|-------|------:|---------|
| indexed | 4325 | Active retrieval corpus |
| pending | 669 | Discovered, not indexed (empty error_message) |
| error | 21 | Mostly fetch timeout / embedding failures |
| refresh_due | ~3397 | Indexed but past `next_refresh_at` — stale schedule, not “missing” |

Do **not** mass-reprocess without ops prioritization. Prefer sources tied to Ask failures (done for rates/locator/privacy/cash-loan via retrieval, not re-crawl).

Privacy: dedicated page `povidomlennia-pro-zakhyst-personalnykh-danykh` exists — was a retrieval miss, not absence.

---

## 7. Phase 1 metrics before / after

| Metric | Baseline (pre-cache) | After quality wave |
|--------|---------------------|--------------------|
| ranking_unchanged_all | true | **true** (fresh OFF vs ON, 12 queries, 0 mismatches) |
| failure_rate | 0 | 0 |
| concept_resolution_success | 1.0 | 1.0 |
| snapshot_availability | 1.0 | 1.0 |
| overlap mean / median | 0.22 / 0.10 | ~0.29 / ~0.29 (diagnostic only) |
| latency p50 / p95 | 2406 / 2516 ms | **24 / 27 ms** warm |

Higher overlap is **not** treated as better. Understanding remains observe-only.

---

## 8. RAG non-interference proof

Re-measured after all product fixes: KU OFF vs ON selected `source_id` lists **identical** for the 12 shadow queries.

---

## 9. Tests

| Gate | Result |
|------|--------|
| `make test-backend` | PASS |
| `make test-dashboard` | PASS |
| `make release-check` | PASS |
| Targeted retrieval / lexical / evidence | PASS |

---

## 10. Independent reviews (summary)

**Staff Engineer:** Trace UniqueViolation session poison fixed; packer no longer evicts exact-match product evidence for opportunistic KP-boosted about pages; tests cover morphology + locator false career.

**Software Architect:** Changes stay inside SI rules, QueryUnderstanding, lexical retrieval, focus/authority/packer, KU cache — no Phase 2, no second pipeline, no tenant hardcode.

**AI Architect:** Main Ask empties were news-flood + FTS morphology + evidence packing — fixed at owners. Remaining life-insurance weakness is corpus (news-only life products).

**Product/UX:** Overview/rates/locator/privacy/cash-loan materially improved; benefits/EN overview wording still soft — accepted debt for 1.1 close.

---

## 11. Phase 2 recommendation

**Do not start Phase 2 by default.** Phase 1 is proven non-interfering and cheap when warm. Phase 2 needs an explicit product decision with ranking-assist evaluation gates.

---

## 12. Release decision inputs

- Infrastructure / SI / KU truthful  
- Phase 1 non-interfering  
- Major Ask empty-retrieval P1 classes fixed  
- No remaining P0  
- Remaining P1-quality soft misses classified as corpus/debt  

**Recommend: close Release 1.1.**
