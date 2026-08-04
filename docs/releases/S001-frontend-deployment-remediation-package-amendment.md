# S001 — Frontend Deployment Remediation Package Amendment (FINAL FREEZE)

**Status:** FINAL — implementation law  
**Date:** 2026-08-04  
**Amends:** `docs/releases/S001-frontend-deployment-remediation-engineering-package.md`  
**Does not modify:** that package’s text; historical S001 deploy/runtime evidence; RFC-100; Step 067; S001 product UI  

**Effect:** Every ambiguity identified by the Remediation Evidence Review is closed. Implementation may follow **only** this amendment where it conflicts with the original package. Where this amendment is silent, the original package still applies.

**Implementation freedom remaining after this document:** **zero** architectural decisions.

---

## Part 1 — Canonical publication mechanism

### 1.1 Sole legal publication path

For modes **full** and **frontend** only:

```
Worktree Vite output
  $MD_DEPLOY_WORKTREE/dashboard/dist/
        ↓  dedicated publish (not source rsync)
Staging directory (same filesystem as nginx root)
  $PROJECT_ROOT/dashboard/dist.next/
        ↓  provenance verification on staging
Atomic directory rename into nginx document root
  $PROJECT_ROOT/dashboard/dist/
```

No other publication path is legal.

### 1.2 Frozen parameters

| Parameter | Law |
|-----------|-----|
| **Mechanism** | Complete tree materialization into a sibling directory, then **atomic directory rename** into the nginx document root. Direct in-place overwrite of the live `dist/` tree (including `rsync` into live `dist/`) is **forbidden**. |
| **Publication source** | `$MD_DEPLOY_WORKTREE/dashboard/dist/` after successful Vite build and after `.frontend-provenance.json` exists in that tree. |
| **Publication destination** | `$PROJECT_ROOT/dashboard/dist/` (= nginx `root`; today `/opt/ai-site-agent/dashboard/dist`). |
| **Temporary location** | `$PROJECT_ROOT/dashboard/dist.next/` on the **same filesystem** as `$PROJECT_ROOT/dashboard/`. |
| **Prior-tree holding name during swap** | `$PROJECT_ROOT/dashboard/dist.old/` (exists only during swap window). |
| **Source rsync** | Continues to **exclude** `dashboard/dist/`. Source rsync is **not** publication. |
| **Success point** | `dist.next` has been renamed to `dist`, prior `dist.old` (if any) has been removed, and provenance verification against the **new** `$PROJECT_ROOT/dashboard/dist` has passed. |
| **Failure point (before swap)** | Any error while filling or verifying `dist.next` → delete `dist.next` if present; leave live `dist` untouched; deploy **FAILED** at stage `frontend_publish` (or equivalent named stage). |
| **Failure point (during swap)** | If rename cannot complete → restore prior `dist` from `dist.old` if needed; remove incomplete `dist.next`; deploy **FAILED**; live tree must be the pre-attempt `dist` or a fully restored prior `dist`. |
| **Cleanup (success)** | Remove `dist.old` and any residual `dist.next`. Worktree removal proceeds as today. |
| **Cleanup (failure)** | Remove `dist.next`; do not leave `dist.next` as nginx root; do not leave split `dist`/`dist.old` after failure handling completes. |
| **Nginx visibility** | Nginx `root` remains `$PROJECT_ROOT/dashboard/dist` only. Nginx must never be pointed at `dist.next` or `dist.old`. Clients either see the complete previous tree or the complete new tree. |
| **Mixed asset prevention** | Guaranteed by forbidding live in-place mutation: the live directory is replaced only by rename of a fully populated, provenance-verified tree. |
| **Replacement guarantee** | After success, every file under live `dist/` belongs to the tip build; no Jul-30/orphan hashed assets from the prior tree remain under live `dist/`. |

### 1.3 Publish algorithm (normative)

1. Require worktree `$WT/dashboard/dist/index.html` and `$WT/dashboard/dist/.frontend-provenance.json`.  
2. `rm -rf "$PROJECT_ROOT/dashboard/dist.next"`.  
3. Copy tree `$WT/dashboard/dist/` → `$PROJECT_ROOT/dashboard/dist.next/` (tooling may use `rsync -a --delete` **into `dist.next` only**).  
4. Run provenance verification on **`dist.next`** (Part 3). Fail → cleanup `dist.next` → stop.  
5. If `$PROJECT_ROOT/dashboard/dist` exists: `mv dist dist.old`.  
6. `mv dist.next dist`.  
7. `rm -rf dist.old`.  
8. Run provenance verification again on live **`dist`**. Fail → deploy FAILED (do not stamp identity; do not SUCCESS).  
9. Proceed to identity stamp (Part 3 / state machine).

### 1.4 Forbidden publication behaviors

- Treating “`$PROJECT_ROOT/dashboard/dist/index.html` exists” as “already published for this tip.”  
- `write_frontend_deploy_identity` (or equivalent) onto live `dist` **without** completing Part 1 publish for this tip.  
- Publishing from operator checkout `dashboard/dist`.  
- Manual operator copy as the release path.  
- Committing `dashboard/dist` to git as the release path.

---

## Part 2 — Rollback contract

### 2.1 Sole rollback meaning

**Rollback = redeploy a known-good tip** via canonical `deploy full` (or the same One Command path) targeting that tip.

This matches existing `redeploy_known_good_tip` philosophy in deployment reports.

**Do not** create a frontend artifact archive.  
**Do not** restore UI from `pg_dump` backups.  
**Do not** keep `dist.old` as a long-lived rollback store (`dist.old` exists only during the swap window in Part 1).

### 2.2 Behavior

| Concern | Law |
|---------|-----|
| **Rollback meaning** | Operator redeploys previous known-good commit (example for this incident: rebuild+publish of the tip that last correctly served UI, or the last accepted engineering tip per operator choice). |
| **Frontend behavior** | That tip’s worktree is built and published exactly under Part 1. |
| **Backend behavior** | That tip’s backend is synced and restarted exactly as `deploy full` already does. |
| **Identity behavior** | `.build-info.json` and `.deploy-identity.json` are produced for **that** tip under Parts 3–4. |
| **Provenance behavior** | Served tree must verify against that tip’s `.frontend-provenance.json`. |

Failed mid-publish on a newer tip does **not** require a special rollback artifact: live `dist` remains the previous tree (Part 1 failure rules).

---

## Part 3 — Provenance contract

### 3.1 Canonical provenance artifact

**Filename:** `.frontend-provenance.json`  
**Location:** always inside the frontend artifact tree root: `dashboard/dist/.frontend-provenance.json` (worktree at build; live under nginx root after publish).

### 3.2 When created

Created **only** during the deploy worktree frontend build (stage BUILD), immediately after Vite emits `index.html` and assets, **before** publication.

Recreating or editing `.frontend-provenance.json` on `/opt` without a new tip build is **forbidden**.

### 3.3 Immutable contents (required fields)

JSON object with **exactly** these required fields (additional fields forbidden unless a future ADR amends this freeze):

| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | number | `1` |
| `git_commit` | string | Full tip commit SHA built |
| `git_commit_short` | string | First 7 chars |
| `release` | string | Tip `APP_RELEASE` |
| `build_time` | string | UTC ISO-8601 time of this provenance write |
| `index_html_sha256` | string | Hex SHA-256 of `index.html` bytes |
| `assets` | array | Every file under `assets/` relative to dist root |
| `assets[].path` | string | e.g. `assets/index-XXXX.js` |
| `assets[].sha256` | string | Hex SHA-256 of file bytes |
| `index_references` | array of string | Every `/assets/...` URL referenced by `index.html` (script src, link href, modulepreload) |
| `tree_sha256` | string | Hex SHA-256 over a canonical serialization of sorted `path + "\\0" + sha256` lines for `index.html` and all `assets[]` entries |

### 3.4 Relationship to other identity files

| File | Role |
|------|------|
| `.frontend-provenance.json` | **Content truth** of the UI tree. |
| `.deploy-identity.json` | **Commit claim** for the served UI; may be written **only after** live provenance verification passes (Part 8). Must include `git_commit`, `git_commit_short`, `release`, `artifact`=`dashboard/dist`, and `provenance_tree_sha256` equal to provenance `tree_sha256`. |
| `.build-info.json` | Release/runtime metadata at project root. For **full** / **frontend**: `frontend_commit` **must equal** tip and equal `.deploy-identity.json` `git_commit` after SUCCESS. For **backend**: see Part 6. |
| `/api/build` | Reflects `.build-info.json` after backend restart; not a substitute for FE provenance. |

### 3.5 Verification rules (normative)

Provenance verification on a tree root `D` **passes** only if all hold:

1. `D/.frontend-provenance.json` exists and parses.  
2. `schema_version == 1`.  
3. `D/index.html` SHA-256 equals `index_html_sha256`.  
4. Every `assets[].path` exists under `D` with matching `sha256`.  
5. No extra files under `D/assets/` beyond those listed (orphan hashed assets ⇒ fail).  
6. Every `index_references` entry resolves to a listed asset path that exists.  
7. Recomputed `tree_sha256` equals the stored value.  
8. When checking a tip deploy: `git_commit` equals the deploy target commit.

**Identity stamp is illegal unless steps 1–8 pass on the tree being stamped.**

Route-string markers (e.g. `/settings/general`) are **not** provenance and **must not** be used to authorize identity.

---

## Part 4 — verify-release contract

### 4.1 What verify-release proves

| Layer | Must prove |
|-------|------------|
| **Repository identity** | Operator checkout / expected tip as today (branch, tip SHA). |
| **Runtime identity** | `/api/health` reachable; `/api/build` `git_commit` / `release` / `alembic_head` readable. |
| **Backend provenance** | `/api/build` `git_commit` equals `.build-info.json` `backend_commit` (and equals tip for **full** / **frontend** / default release verify). |
| **Frontend provenance** | On nginx root `$PROJECT_ROOT/dashboard/dist`: Part 3 verification **PASS**; `.deploy-identity.json` `git_commit` equals provenance `git_commit`; `.deploy-identity.json` `provenance_tree_sha256` equals provenance `tree_sha256`; served `index.html` references exist on disk. |
| **Release metadata** | Tip `APP_RELEASE` equals `.build-info.json` `release` and `/api/build` `release` when expected_release is supplied (unchanged intent). |
| **Deployment metadata** | `.build-info.json` present; for **full**/**frontend** verify: `frontend_commit` equals FE identity commit equals tip. |

### 4.2 Served frontend rule

verify-release **must read files from the nginx document root on disk** (`$PROJECT_ROOT/dashboard/dist`).  
JSON-only equality of `.deploy-identity.json` to tip **without** Part 3 file hashing is **insufficient** and **illegal** as a PASS condition.

### 4.3 Mode nuance

For **backend** mode verification expectations, see Part 6 (FE may legally lag tip; FE self-provenance still mandatory).

### 4.4 Out of scope for verify-release

- Browser navigation / click paths  
- Visual regression  
- Fixing `/tmp/vr-*` curl exit-23 (remains S00T / G10; deploy-time verify must use writable temp paths or equivalent so this freeze is testable without that defect)

---

## Part 5 — Smoke contract

### 5.1 Nature

Smoke remains **lightweight HTTP/API (+ existing golden unit)**.  
**Forbidden:** Playwright, Puppeteer, Selenium, headed browsers, click-paths, “open SPA and assert React tree.”

### 5.2 Exact checks (normative)

Retain existing API checks:

- `GET /api/health`  
- `GET /api/metrics` (kos_memory_version)  
- `GET /api/metrics/operational`  
- `GET /api/build`  
- `POST /api/auth/login`  
- authenticated `GET /api/settings`  
- optional chat when `SMOKE_CHAT=1`  
- golden unit parity as today  

**Add only these static frontend checks** (HTTP against the public site root that nginx serves, default `http://127.0.0.1/` or configured base):

1. `GET /` returns HTTP 200 and body contains `index.html`’s root mount expectation (`id="root"` or current equivalent).  
2. Parse `index.html` for `/assets/...` references; `GET` each referenced asset → HTTP 200.  
3. `GET /overview` and `GET /settings/general` return HTTP 200 (SPA fallback to `index.html` is sufficient; **no** DOM assertion).  

### 5.3 Separation

- Smoke **does not** hash provenance or compare `tree_sha256` (verify-release owns that).  
- verify-release **does not** replace smoke’s API login/settings/golden checks.  
- Smoke **PASS** never authorizes SUCCESS if verify-release failed.

---

## Part 6 — Deployment mode matrix

Legend: **Y** = must perform · **N** = must not · **—** = N/A

| Mode | Build FE | Publish FE (Part 1) | Stamp FE identity | Validate FE provenance | Touch live `dist` | Notes |
|------|----------|---------------------|-------------------|------------------------|-------------------|-------|
| **full** | Y | Y | Y (after provenance on live tree) | Y | Y (atomic replace) | Canonical release |
| **frontend** | Y | Y | Y (after provenance) | Y | Y | Same FE laws as full; backend restart per existing frontend mode |
| **backend** | N | N | N | Y (self-check only) | **N** (preserve entire tree) | See §6.1 |
| **restart** | N | N | N | N | N | Service restart only |
| **rollback** | Y* | Y* | Y* | Y* | Y* | \*Via `deploy full` of known-good tip (Part 2) |
| **verify-release** | N | N | N | Y (per mode rules) | N | Diagnostic / deploy gate |
| **smoke** | N | N | N | N (static GETs only) | N | Part 5 |

### 6.1 Backend mode (frozen)

- Source sync may update backend code and `.build-info.json`.  
- Live `dashboard/dist/**` including `.deploy-identity.json` and `.frontend-provenance.json` must be **byte-preserved**.  
- After sync, `.build-info.json` **`frontend_commit` must be set to** the preserved `.deploy-identity.json` `git_commit` (not the new tip).  
- `.build-info.json` `backend_commit` and (for backend semantics) overall backend tip fields reflect the new tip.  
- verify-release **PASS** requires: backend tip alignment + FE Part 3 self-check + FE identity consistent with preserved provenance; it does **not** require `frontend_commit == tip`.  
- Skipping FE publish in backend mode is **allowed**. Skipping FE publish in **full**/**frontend** is **forbidden**.

### 6.2 Forbidden in full/frontend

- “Artifact already present — skip duplicate npm build” when skip means “do not publish worktree dist.”  
- Stamping tip identity onto pre-existing live `dist` without Part 1.

### 6.3 Expected outputs

| Mode | SUCCESS implies |
|------|-----------------|
| full | Tip backend + tip FE published + provenance + identities aligned |
| frontend | Tip FE published + provenance + FE identity aligned; backend per existing frontend mode |
| backend | Tip backend running; prior FE unchanged and self-consistent |
| restart | Process health only |
| rollback | SUCCESS of `deploy full` on chosen known-good tip |

---

## Part 7 — Failure contracts

| Condition | Deployment verdict | Rollback requirement | Runtime state | Operator action |
|-----------|--------------------|----------------------|---------------|-----------------|
| Worktree FE build fails | FAILED (`build`) | none_pre_sync | Prior live UI unchanged | Fix source; redeploy tip |
| Missing `.frontend-provenance.json` after build | FAILED (`build`) | none_pre_sync | Prior UI unchanged | Fix build pipeline; redeploy |
| Fill/verify `dist.next` fails | FAILED (`frontend_publish`) | none (live untouched) | Prior UI unchanged | Fix publish; redeploy |
| Atomic swap fails | FAILED (`frontend_publish`) | Restore prior `dist` if needed | Prior UI restored or still live | Redeploy |
| Live provenance mismatch after swap | FAILED (`frontend_provenance`) | Redeploy known-good tip if live tree suspect | Treat as broken publish | `deploy full` known-good tip |
| Identity stamp attempted without provenance PASS | FAILED (must not stamp) | — | No SUCCESS | Fix; redeploy |
| Identity / tip mismatch at verify | FAILED (`verify_release`) | redeploy_known_good_tip | Partial possible | Redeploy known-good tip |
| Mixed/orphan assets under live `dist` | FAILED (provenance) | redeploy_known_good_tip | Do not SUCCESS | Redeploy |
| Stale live UI with new tip metadata (the incident class) | FAILED (must be detected) | redeploy_known_good tip after fix | — | Ship this remediation then redeploy |
| FE publish skipped in full/frontend | FAILED | — | Illegal | Forbidden by law |
| Backend-only deploy | SUCCESS allowed without FE publish | — | FE preserved; `frontend_commit` preserved | Normal |
| Smoke fail after verify PASS | FAILED (`smoke`) | redeploy_known_good_tip | Per report partial rules | Investigate API/static; redeploy |
| `/tmp` curl exit-23 standalone verify | Not a product FE fail | — | — | S00T; use writable temps |

---

## Part 8 — State machine

Normative order for **full** and **frontend** (no skipped transitions):

```
[1] BUILD
      worktree checkout
      write .build-info.json (worktree)
      npm build
      write .frontend-provenance.json
      FAIL → stop (build)
        ↓
[2] SOURCE SYNC
      rsync worktree → $PROJECT_ROOT excluding dashboard/dist/
      FAIL → stop (sync)
        ↓
[3] PUBLISH
      materialize dist.next from worktree dist
      FAIL → stop (frontend_publish); live dist untouched
        ↓
[4] PROVENANCE VERIFICATION (on dist.next)
      Part 3 rules
      FAIL → delete dist.next; stop (frontend_provenance)
        ↓
[5] ATOMIC SWAP
      dist → dist.old; dist.next → dist; remove dist.old
      FAIL → restore; stop (frontend_publish)
        ↓
[6] PROVENANCE VERIFICATION (on live dist)
      Part 3 rules
      FAIL → stop (frontend_provenance); no identity stamp; no SUCCESS
        ↓
[7] IDENTITY STAMP
      write .deploy-identity.json on live dist (includes provenance_tree_sha256)
      align .build-info.json frontend_commit to tip (full/frontend)
      FAIL → stop (frontend_identity)
        ↓
[8] POST-SYNC MIGRATE / RESTART / HEALTH
      existing stages
      FAIL → stop at named stage
        ↓
[9] RUNTIME VERIFICATION (verify-release)
      Part 4
      FAIL → stop (verify_release)
        ↓
[10] SMOKE
      Part 5
      FAIL → stop (smoke)
        ↓
[11] SUCCESS
```

**Backend mode** skips [1] FE build through [7] FE stamp; preserves live dist; rewrites `frontend_commit` forward from preserved FE identity; then continues migrate/restart/health/verify/smoke under Part 6 rules.

**Identity never runs before [6] PASS.**

---

## Part 9 — Invariants (testable)

| ID | Invariant | Test idea |
|----|-----------|-----------|
| I1 | Identity never precedes provenance PASS on the tree being stamped | Attempt stamp without manifest ⇒ fail; no `.deploy-identity` tip claim |
| I2 | Served artifact always has verified provenance after SUCCESS | Post-SUCCESS Part 3 on `$PROJECT_ROOT/dashboard/dist` |
| I3 | Publication is atomic (no live in-place mutate) | Probe mid-publish: nginx root never contains partial new+old asset set |
| I4 | Rollback = redeploy known-good tip (no FE archive) | Assert no durable `dist.old` archive API; rollback docs = deploy full prior tip |
| I5 | Metadata never represents unpublished UI | After simulated skip-without-publish, verify-release MUST fail |
| I6 | Smoke never replaces verify-release | Smoke PASS + broken provenance ⇒ overall deploy FAIL at verify |
| I7 | verify-release never replaces smoke | verify PASS + smoke API fail ⇒ deploy FAIL at smoke |
| I8 | Source rsync exclusion of `dashboard/dist/` remains; publish is separate | Unit assert exclude list + publish stage exists |
| I9 | full/frontend cannot SUCCESS if worktree dist ≠ live dist tree_sha256 | Stale /opt + new worktree ⇒ FAIL unless publish updates live |
| I10 | backend mode does not modify live dist bytes | Checksum `dist` before/after backend deploy |
| I11 | `.deploy-identity.json.provenance_tree_sha256` == provenance `tree_sha256` | Direct equality check |
| I12 | Orphan files under `assets/` fail provenance | Drop extra file ⇒ verify FAIL |

---

## Part 10 — Amendment impact

### 10.1 What changes relative to the original Engineering Package

| Original package item | Amendment law |
|----------------------|---------------|
| “Atomic publication” (unspecified) | Part 1 sibling `dist.next` + rename only |
| Rollback “matching previous frontend artifact” | Part 2 = **redeploy known-good tip** (no archive) |
| Smoke “canonical S001 routes load” / markers | Part 5 static HTTP only; no Playwright; no provenance hashing in smoke |
| verify-release “bundle provenance” | Part 3+4 mandatory `.frontend-provenance.json` + on-disk hashing |
| “Artifact already present” skip | **Forbidden** for full/frontend as a substitute for publish |
| Identity stamp timing | **After** live provenance PASS only |
| Mode matrix | Part 6 complete freeze |
| Test hints using route strings as authority | Route strings **not** authoritative; manifest is |

### 10.2 What remains unchanged

- RCA causal chain and incident facts in the original package  
- Forbidden fixes list intent (manual copy, nginx root move, accepting metadata-only, S002, etc.)  
- Module hit list: `deploy_source.sh`, `manage_deploy.sh`, `deploy_guard.sh`, `verify_release.sh`, `smoke-staging.sh`, tests, remediation evidence docs  
- Out of scope: RFC-100, Step 067 product reopen, S002, Product Completion features, DB migrations  
- Historical immutability of `20260804_182928-e9dbaab.json` and Runtime Validation FAIL  
- S001 product UI scope (routes/Mode) — this amendment is deploy publication only  
- `/tmp/vr-*` exit-23 remains S00T/G10, not this remediation’s product gate  

### 10.3 What implementation must follow

Implementers must implement **exactly** Parts 1–9.  
If the original package and this amendment disagree, **this amendment wins**.  
No alternate publication, rollback, provenance, verify, smoke, or mode behavior is authorized.

---

## Status (unchanged by this amendment)

```
S001: IMPLEMENTED | COMMITTED | PUSHED | DEPLOYED_METADATA_ONLY
      | RUNTIME_VALIDATION_FAIL | NOT_ACCEPTED

S002: NOT_STARTED

Product Readiness: FAIL for deployed S001 runtime until superseding
frontend deployment evidence exists after remediation implementation + deploy.
```

---

## Final freeze statement

Architectural ambiguity for S001 frontend deployment remediation is **closed**.  
The next authorized step is **implementation evidence review / implementation** against this amendment — not further design choice.
