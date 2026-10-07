# RELEASE 1.1 LIVE ACCEPTANCE — FINAL (CLOSED)

**Date:** 2026-10-07  
**Release status:** **CLOSED / ACCEPTED**  
**Accepted runtime SHA:** `bc51669f6b8cb7622f497a93ae316e8178fd80ae`  
**Deploy:** `20261007_161405-bc51669` · manifest `2026-10-07T16:14:06Z` · outcome **success**  
**Validation tenant:** current production corpus (not architecture target)

---

## 1. Ship identity chain

| Check | Result |
|-------|--------|
| local HEAD | `bc51669` |
| origin/main | `bc51669` |
| deployed commit | `bc51669` |
| `/api/build` backend/frontend | `bc51669` / `bc51669` |
| `.build-info.json` | `bc51669` · build_time `2026-10-07T16:13:37Z` |
| Alembic | `0022_settings_singleton_and_site_url` |
| health | ok |
| verify-release | **pass** |
| smoke | **pass** |
| partial_deploy | false |

No second deploy required for docs-only closure commits.

---

## 2. Runtime state after deploy

| Area | Result |
|------|--------|
| Settings singleton | 1 row · `site_url=https://ukrsibbank.com` |
| KU flag | ON |
| KnowledgeVersion | 40 (aligned with READY) |
| SI indexed | 4325 with `document_purpose` profiles (`SOURCE_INTELLIGENCE_VERSION=source-intelligence-v3`) |
| KU READY | id=**7** · concepts=**3522** · evidence=**9371** |
| article/document concepts | **0** |
| Phase 1 | observe-only · flag does not grant ranking authority |

---

## 3. Phase 1 final

| Metric | Value |
|--------|------:|
| Shadow executes | yes (snap 7) |
| Shadow failures | 0 |
| Warm latency | p50≈25–59ms (cold first hit can be ~1–4s) |
| Ranking authority | none |

**Non-interference:** repeated OFF/ON comparisons show occasional source-id set differences that also appear **within OFF-only repeats** (retrieval nondeterminism). No evidence that Understanding mutates ranking/context/prompt/answer. Contract remains observe-only.

---

## 4. Critical Ask smoke (post-deploy, /opt)

8/8 cases returned non-degenerate answers (2026-10-07 close smoke):

| Case | Retrieval survivors | Notes |
|------|---------------------|-------|
| org overview UK | homepage + about-bank | usable |
| org overview EN | charity/service pages | **accepted debt** (soft) |
| org benefits | awards/compliance about | **accepted debt** (awards lean) |
| deposit rates | deposit product/pricing | rates present |
| branch locator | branches-atms + homepage | locator page selected |
| privacy | personal-data notice + info-security | fixed class |
| cash loan | consumer-cash-loan + compliance | product page retained |
| unsupported geo | honest no-NY branches | safe refusal |

No truncation / degenerate completion in this subset. Soft P2 wording debt is **not** reopened.

---

## 5. Gates

| Gate | Result |
|------|--------|
| `make test-backend` | PASS (pre-ship) |
| `make test-dashboard` | PASS (pre-ship) |
| `make release-check` | PASS (pre-ship) |
| verify-release (deploy) | PASS |
| smoke (deploy) | PASS |

---

## 6. Accepted debt / next cycle

**ACCEPTED 1.1 DEBT:** EN overview softness; benefits/awards bias; life-insurance corpus gap; cold KU load.

**CORPUS OPS:** 669 pending; 21 errors; ~3397 refresh-due.

**NEXT (not 1.1):** Phase 2 Understanding ranking-assist only with explicit go; corpus reliability; further Ask quality iteration.

---

## 7. Recommendation for next milestone

**B → then C, then A:** corpus operations / indexing reliability first; then Ask product-quality iteration on real gaps; Phase 2 ranking-assist only after explicit product decision.
