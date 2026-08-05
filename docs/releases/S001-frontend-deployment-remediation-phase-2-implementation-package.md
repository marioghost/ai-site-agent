# S001 Frontend Deployment Remediation — Phase 2 Implementation Package

**Type:** Implementation package (planning only — this document does not implement)  
**Date:** 2026-08-04  
**Status:** FROZEN for implementation  
**Phase 1 tip (live):** `c9c13d6e21787721914eea7493f20643bf92c9c1`  
**Authorities (highest → lowest):**

1. `docs/releases/S001-frontend-deployment-remediation-package-amendment.md` (final law)  
2. `docs/releases/S001-frontend-deployment-remediation-engineering-package.md`  
3. Approved Phase 1 Final Acceptance Review  
4. Approved Phase 2 Authorization Review (scope A–E)  
5. Existing deploy / `release-check` / smoke architecture  

**Frozen status entering Phase 2:**

```
Remediation Phase 1: ACCEPTED | CLOSED
Phase 2:             AUTHORIZED | NOT_IMPLEMENTED
S001:                DEPLOYED | RUNTIME_VALIDATION_PASS | NOT_ACCEPTED
S002:                NOT_STARTED
```

Do **not** reopen Phase 1. Do **not** redesign publication (`dist.next` → swap → stamp).

---

## 1. Phase 2 purpose

Phase 2 completes **only** verification, smoke static checks, regression protection, and backend-mode identity preservation left open by Phase 1:

| ID | Obligation |
|----|------------|
| **A** | verify-release served frontend provenance (Part 3 + Part 4) |
| **B** | static frontend smoke checks (Part 5) |
| **C** | deploy regression protection (incident class + mode gates) |
| **D** | backend-only frontend identity preservation (Part 6.1) |
| **E** | rsync `dashboard/dist/` exclusion regression + writable temp hygiene in verify-release |

Phase 2 must **not** change the Phase 1 publication algorithm, provenance schema, atomic rename flow, rollback meaning, or S001 product behavior.

---

## 2. Frozen scope

### A. verify-release

On nginx document root `$PROJECT_ROOT/dashboard/dist` (default `/opt/ai-site-agent/dashboard/dist`):

1. Verify `.frontend-provenance.json` via canonical helper (`deploy_guard_assert_frontend_provenance` → `frontend_provenance.py verify`).  
2. That helper already hashes `index.html`, hashes every listed asset, rejects orphans, recomputes `tree_sha256`, and optionally checks `git_commit`.  
3. Read `.deploy-identity.json`; require `provenance_tree_sha256 ==` provenance `tree_sha256`.  
4. Compare identity `git_commit` to provenance `git_commit`.  
5. **full / frontend / default standalone tip verify:** FE identity commit == tip; build-info `frontend_commit` == tip; metadata tip alone without Part 3 PASS is **illegal**.  
6. **backend mode:** FE may lag tip; FE self-provenance + identity consistency mandatory; `frontend_commit` must equal preserved identity commit (not tip).  
7. Fixed `/tmp/vr-*.json` must be replaced with a unique writable workspace (see §2.E).  

### B. smoke

Retain current API + golden checks in `scripts/release/smoke-staging.sh`.

**Add only** (HTTP against **public site base**, default `http://127.0.0.1/` — **not** the API `:8000` base):

1. `GET /` → 200; body contains `id="root"` (or current root mount marker).  
2. Parse returned HTML for `/assets/...` references (`src` / `href` / `modulepreload`).  
3. `GET` each referenced asset → 200.  
4. Content-Type acceptable for asset class (§7).  
5. `GET /overview` → 200.  
6. `GET /settings/general` → 200 (SPA fallback to `index.html` OK).  

**Forbidden:** Playwright, Puppeteer, Selenium, DOM/click E2E, provenance hashing / `tree_sha256` in smoke.

### C. tests

Automate T01–T24 (§9). Prefer fixture directories under a temp root — no live `/opt` mutation in unit/regression suites. No headed browser.

### D. backend-only identity

In `md_deploy_from_main` when `mode=backend`:

- No FE build, no `md_publish_frontend_artifact`, no live `dist` mutation.  
- After source sync: validate preserved live provenance; rewrite `.build-info.json.frontend_commit` from preserved `.deploy-identity.json.git_commit`.  
- `backend_commit` / overall tip fields = new tip.  
- Never stamp backend tip onto preserved FE identity/provenance.  

### E. Writable temp hygiene (narrow)

Inside `md_verify_release_run` only:

- Replace fixed `/tmp/vr-health.json`, `/tmp/vr-build.json`, `/tmp/vr-overview.json`, `/tmp/vr-qdrant.json`.  
- Use `mktemp -d` (pattern e.g. `/tmp/ai-site-agent-vr-XXXXXX`) + `trap` cleanup on EXIT.  
- Do **not** implement broader S00T/G10 program work.

---

## 3. File ownership

| Path | Classification | Role |
|------|----------------|------|
| `deploy/lib/verify_release.sh` | **Required** | Part 4 + temps + mode-aware FE rules |
| `scripts/release/smoke-staging.sh` | **Required** | Part 5 static FE checks |
| `deploy/lib/deploy_source.sh` | **Required** | Backend-mode `frontend_commit` rewrite after sync; **no** publish algorithm change |
| `deploy/lib/deploy_guard.sh` | **Required** | Reuse provenance/identity asserts; optional thin helpers for mode-aware FE rules if needed |
| `deploy/lib/frontend_provenance.py` | **Optional only if proven necessary** | Current `verify` CLI is sufficient for Part 3; extend only if verify-release needs structured JSON stdout (prefer exit-code + existing files first) |
| `deploy/manage_deploy.sh` | **Optional only if proven necessary** | Touch only if backend-mode legacy path stamps FE illegally; prefer fix in `deploy_source.sh` |
| `scripts/release/verify-release.sh` | **Required** | Pass mode / expected commit through to shared core if signature expands |
| `scripts/release/test-one-command-deploy.sh` | **Required** | Contract greps for verify/smoke separation, backend rewrite, no fixed `/tmp/vr-*`, publication stages unchanged |
| `scripts/release/test-deploy-rsync-excludes.sh` | **Required** | Add `exclude 'dashboard/dist/'` assertions (today missing) |
| `scripts/release/test-frontend-remediation-phase2.sh` | **Required (new)** | Focused T01–T22 fixture tests |
| `scripts/release/release-check.sh` | **Required** | Wire new focused script once (no duplicate suites) |
| `docs/releases/S001-frontend-deployment-remediation-phase-2-*.md` | **Required** | Evidence docs after implementation (not this package’s implementation) |
| `dashboard/**` product | **Forbidden** | |
| `backend/app/**` | **Forbidden** | |
| Alembic / schema | **Forbidden** | |
| nginx root / FE archive | **Forbidden** | |
| Phase 1 publish redesign | **Forbidden** | |
| RFC-100 / Step 067 / S002 | **Forbidden** | |

---

## 4. Function-level map

### 4.1 `deploy/lib/verify_release.sh`

| Current | Required change | Owner |
|---------|-----------------|-------|
| `md_verify_release_run root project_root expected_commit expected_release` | Extend signature (or env) with **verification mode**: `full` \| `frontend` \| `backend` \| `standalone` (default `standalone` ≡ tip-aligned full rules). Deploy pipeline must pass the deploy mode. | verify-release |
| Fixed `/tmp/vr-*.json` curls | Create `VR_TMP=$(mktemp -d ...)`; write health/build/overview/qdrant under `$VR_TMP`; `trap 'rm -rf "$VR_TMP"' EXIT` | verify-release |
| Section 2 FE identity == build-info `git_commit` always | Replace with mode-aware rules (§5). Still require FE identity file + Part 3 provenance. | verify-release |
| Section 5 “FULL CHAIN” requires FE == tip always | Mode-aware chain summary; backend allows FE lag when self-consistent | verify-release |
| Missing: Part 3 on-disk hashing | After reading FE identity, call `deploy_guard_assert_frontend_provenance "$project_root/dashboard/dist" "<expected_fe_commit_or_empty>"` then assert identity `provenance_tree_sha256` | verify-release via deploy_guard |

**New helper (bash, same file or deploy_guard):**

- Name: `md_verify_frontend_served_tree` (preferred in `verify_release.sh`) or `deploy_guard_assert_frontend_served_identity`.  
- **Inputs:** `project_root`, `mode`, `tip_commit`.  
- **Outputs:** PASS messages / FAIL messages on stderr+stdout; return 0/1.  
- **Behavior:**  
  1. `dist=$project_root/dashboard/dist`  
  2. Require `.frontend-provenance.json` and `.deploy-identity.json`  
  3. `deploy_guard_assert_frontend_provenance "$dist"` (no expected commit yet) — enforces hash/orphan/tree  
  4. Read provenance `git_commit`, `tree_sha256`; identity `git_commit`, `provenance_tree_sha256`  
  5. Require identity tree == provenance tree; identity commit == provenance commit  
  6. If mode ∈ {full, frontend, standalone}: require those commits == `tip_commit`; require build-info `frontend_commit` == tip  
  7. If mode == backend: require build-info `frontend_commit` == identity `git_commit`; do **not** require == tip; still require Part 3 PASS  
- **Failure exit:** return 1; caller increments FAIL / returns 1 from `md_verify_release_run`.

**Do not** reimplement hashing in bash — call Python verifier.

### 4.2 `scripts/release/smoke-staging.sh`

| Current | Required change | Owner |
|---------|-----------------|-------|
| API checks + golden + `SMOKE_TMP` mktemp | **Retain** | smoke |
| No public site checks | Add section after API build (or after settings), before optional chat | smoke |
| `BASE` = API (`:8000`) | Introduce `PUBLIC_BASE="${SMOKE_PUBLIC_BASE_URL:-http://127.0.0.1}"` (no trailing slash). Do **not** reuse API `BASE` for static FE. | smoke |

**New helpers (same file):**

| Helper | Inputs | Outputs | Failure |
|--------|--------|---------|---------|
| `smoke_fetch_public path -o file` | path relative to PUBLIC_BASE | HTTP body + code | fail() if not 200 |
| `smoke_assert_root_marker file` | HTML file | pass/fail | missing `id="root"` |
| `smoke_parse_index_assets file` | HTML | list of `/assets/...` | fail if zero refs when index claims scripts |
| `smoke_assert_asset url` | absolute URL | 200 + Content-Type | fail |

### 4.3 `deploy/lib/deploy_source.sh`

| Current | Required change | Owner |
|---------|-----------------|-------|
| `md_publish_frontend_artifact` | **Unchanged** (Phase 1 freeze) | publication |
| FE publish only for full/frontend | **Unchanged** | publication |
| After sync for backend: nothing FE | **Add** `md_preserve_backend_frontend_identity "$project_root" "$tip_commit"` after SYNC OK when `mode=backend`, before POST-SYNC MIGRATE | deploy_source |
| `md_verify_release_run "$repo" "$root" "$commit" "$release"` | Pass mode: e.g. 5th arg or `MD_VERIFY_MODE=$mode` | deploy_source |

**New helper `md_preserve_backend_frontend_identity`:**

- **Inputs:** `project_root`, `backend_tip_commit`  
- **Algorithm:** exactly §8  
- **Failure:** `md_deploy_fail frontend_identity|frontend_provenance "..."` — never SUCCESS  
- **Must not:** call publish, build FE, or write `.deploy-identity.json` / provenance  

### 4.4 `deploy/lib/deploy_guard.sh`

| Current | Required change |
|---------|-----------------|
| `deploy_guard_assert_frontend_provenance` | Reuse as-is |
| `deploy_guard_assert_frontend_identity` | Remains tip-equality helper for **full/frontend publish path**; do **not** use unmodified for backend verify |
| Optional | Add `deploy_guard_assert_frontend_identity_consistent` (identity↔provenance only, no tip) if it reduces duplication — **optional** |

### 4.5 `deploy/lib/frontend_provenance.py`

| Current | Required change |
|---------|-----------------|
| `verify` / `write` / `stamp` | **None required** if exit codes suffice |
| Optional | Add `--json` print of verified payload only if tests need machine-readable output without scraping OK lines |

### 4.6 `deploy/manage_deploy.sh`

| Current | Required change |
|---------|-----------------|
| Release full/frontend skip local FE stamp | **Unchanged** |
| Backend mode path under `MD_RELEASE_DEPLOY` | Prefer all backend FE rewrite in `deploy_source.sh`. Touch `manage_deploy.sh` **only if** a non-release or legacy path still stamps tip identity onto live dist without provenance — then remove that path (mirror Phase 1 illegal-skip removal). |

### 4.7 Tests

| Script | Ownership |
|--------|-----------|
| `scripts/release/test-frontend-remediation-phase2.sh` | T01–T22 primary |
| `scripts/release/test-deploy-rsync-excludes.sh` | T21 (`dashboard/dist/`) |
| `scripts/release/test-one-command-deploy.sh` | T19/T20/T22/T24 contract greps + backend rewrite wiring |
| `scripts/release/release-check.sh` | T23 — invoke focused script once |

---

## 5. Mode contract

Legend: tip = deploy/verify target commit. FE tree = live `$PROJECT_ROOT/dashboard/dist`.

| Mode | Backend commit | Frontend commit (build-info + identity) | FE provenance == tip? | FE lag allowed? | Live dist may change? | PASS | FAIL |
|------|----------------|------------------------------------------|----------------------|-----------------|----------------------|------|------|
| **full** | = tip | = tip | Yes | No | Yes (publish) | Part 3+4 tip-aligned + health | Any provenance/identity/tip mismatch; metadata-only |
| **frontend** | per existing frontend mode | = tip | Yes | No | Yes (publish) | Same FE rules as full | Same FE fails |
| **backend** | = tip | = preserved FE identity (may ≠ tip) | Self-consistent; **not** required == tip | Yes | **No** | Part 3 PASS + identity↔provenance + `frontend_commit`==identity; backend tip OK | Dist mutated; tip stamped on FE; broken provenance; `frontend_commit`==tip while identity lags (unless equal by chance) |
| **restart** | unchanged | unchanged | N/A (no verify FE gate beyond prior) | — | **No** | Services healthy | — |
| **rollback** | known-good tip via `deploy full` | = that tip after full | Yes after full | No | Yes via full | Same as full on chosen tip | — |
| **standalone verify-release** | expect tip-aligned **full** rules unless `MD_VERIFY_MODE=backend` explicitly set | tip-aligned by default | Yes by default | Only if mode=backend | No | Per mode | Per mode |
| **smoke** | N/A (API build readable) | N/A | Does not hash | — | No | API+static HTTP | Any required check fail |

**Invariant:** Smoke PASS never overrides verify FAIL; verify PASS never overrides smoke FAIL (`md_deploy_fail` distinct stages).

---

## 6. Verify-release algorithm (logical)

Implement inside `md_verify_release_run` (no shell listed here — logic only):

1. **Create writable temp workspace** `VR_TMP`; register EXIT cleanup.  
2. **Fetch** health → `$VR_TMP/health.json`; build → `$VR_TMP/build.json` (same curl semantics as today).  
3. **Read** `$project_root/.build-info.json` (`git_commit`, `backend_commit`, `frontend_commit`, `release`).  
4. **Identify mode** from arg/env (`MD_VERIFY_MODE` / 5th parameter); default `standalone` (= tip-aligned full FE rules). Deploy full/frontend/backend passes that mode.  
5. **Verify backend identity:** tip/expected_commit vs build-info `git_commit`/`backend_commit` vs `/api/build` per existing section rules; for backend mode, `/api/build.git_commit` and `backend_commit` track tip; do not require `frontend_commit` == tip.  
6. **Verify live FE provenance** via canonical helper on `$project_root/dashboard/dist` (Part 3).  
7. **Read** `.deploy-identity.json`.  
8. **Compare** identity `git_commit` == provenance `git_commit`; identity `provenance_tree_sha256` == provenance `tree_sha256`.  
9. **Mode-aware frontend commit rule** (§5).  
10. **Release metadata** (expected_release vs APP_RELEASE / build-info / api) — unchanged intent.  
11. **PASS** only if FAIL count == 0.  
12. **Cleanup** temp workspace (trap).

### Failure classification (messages)

| Layer | Example FAIL message | Exit |
|-------|----------------------|------|
| Temp | (should not fail creation; if so abort verify) | 1 |
| Health | `health unreachable (...)` | count FAIL |
| Build-info missing | `missing .../.build-info.json` | FAIL |
| Backend tip | `build-info (...) != tip (...)` | FAIL |
| API | `/api/build (...) != build-info (...)` | FAIL |
| Provenance missing/invalid | helper stderr / `frontend provenance verification failed` | FAIL |
| Identity missing | `missing frontend identity ...` | FAIL |
| Tree mismatch | `identity provenance_tree_sha256 (...) != provenance tree_sha256 (...)` | FAIL |
| Tip FE required | `frontend identity (...) != tip (...)` (full/frontend/standalone) | FAIL |
| Backend split | `build-info frontend_commit (...) != preserved FE identity (...)` | FAIL |
| Metadata-only | Any path that would PASS without Part 3 must not exist | FAIL |
| Chain summary | Mode-aware; must not require FE==tip in backend | FAIL if inconsistent |

Overview/Qdrant remain best-effort **WARN** (unchanged).

---

## 7. Smoke algorithm (logical)

1. Existing API checks (health, metrics, operational, build, login, settings) using API `BASE` and `SMOKE_TMP`.  
2. `GET ${PUBLIC_BASE}/` → save body; require HTTP 200.  
3. Body must contain root mount marker: `id="root"` (exact substring).  
4. Parse `src`/`href` attributes referencing `/assets/...` (same spirit as provenance `ASSET_REF_RE`).  
5. For each unique reference: `GET ${PUBLIC_BASE}${path}`.  
6. Require HTTP 200.  
7. Require Content-Type:  
   - `.js` → `application/javascript` or `text/javascript` (substring match OK)  
   - `.css` → `text/css`  
   - other under `/assets/` → `application/javascript` or `text/css` or `application/octet-stream` only if needed; **reject** `text/html` (SPA fallback disguising missing asset).  
8. `GET ${PUBLIC_BASE}/overview` → 200 (body may be index.html).  
9. `GET ${PUBLIC_BASE}/settings/general` → 200.  
10. Existing optional chat + golden unit parity.  
11. Exit 1 if `failures > 0`.

**No** browser rendering assertions. **No** provenance hashing.

---

## 8. Backend-only flow (exact)

Inside `md_deploy_from_main` when `mode=backend`:

### Before sync (optional but recommended for tests)

- Record checksum/tree of live `dashboard/dist` (e.g. `find … | sort | sha256sum` or provenance `tree_sha256`) into locals for post-check.

### After SYNC OK (mandatory)

1. Do **not** run FE build or `md_publish_frontend_artifact`.  
2. `dist=$MD_DEPLOY_PROJECT_ROOT/dashboard/dist`  
3. Require `$dist/.deploy-identity.json` and `$dist/.frontend-provenance.json`.  
4. `deploy_guard_assert_frontend_provenance "$dist"` (self-check; expected_commit = identity’s `git_commit`).  
5. Read `fe_commit` from identity.  
6. Rewrite `.build-info.json`: set `frontend_commit=$fe_commit`; keep `git_commit` / `backend_commit` = tip (as written by sync).  
7. Assert live dist bytes/tree unchanged vs pre-sync snapshot (I10).  
8. Continue migrate → restart → health.  
9. `md_verify_release_run …` with **mode=backend**.  

### Failure conditions → deploy FAILED (no SUCCESS)

| Condition | failed_stage |
|-----------|--------------|
| Preserved FE identity missing | `frontend_identity` |
| Preserved provenance missing/invalid | `frontend_provenance` |
| build-info rewrite fails | `frontend_identity` |
| Dist bytes changed | `frontend_publish` or `frontend_identity` |
| verify-release split inconsistent | `verify_release` |

**Forbidden:** writing tip into `.deploy-identity.json` or provenance during backend mode.

---

## 9. Test matrix

**Primary script:** `scripts/release/test-frontend-remediation-phase2.sh`  
**Fixture root:** `mktemp -d` with synthetic `dashboard/dist` trees (copy minimal HTML/JS/CSS + generate provenance via `frontend_provenance.py write` where needed).  
**Sudo/runtime:** not required for T01–T22 unit/regression. T23 is release-check aggregator. Live `/opt` not mutated.

| ID | Requirement | Fixture / setup | Under test | Exit | Expected output | Unchanged | Invariant |
|----|-------------|-----------------|------------|------|-----------------|-----------|-----------|
| T01 | Valid provenance PASS | tip-aligned dist + provenance + identity | `frontend_provenance.py verify` + verify helper | 0 | OK / PASS | fixture only | I2 |
| T02 | Metadata tip + stale bundle FAIL | identity/build-info tip; assets/hashes from other tree | verify helper / Part 3 | ≠0 | FAIL provenance or hash | — | I5 |
| T03 | Missing provenance FAIL | dist without `.frontend-provenance.json` | verify | ≠0 | missing provenance | — | I1 |
| T04 | index hash mismatch FAIL | mutate index.html after write | verify | ≠0 | index sha mismatch | — | Part 3 |
| T05 | asset hash mismatch FAIL | mutate listed asset | verify | ≠0 | asset sha mismatch | — | Part 3 |
| T06 | orphan asset FAIL | extra file under `assets/` | verify | ≠0 | orphan | — | I12 |
| T07 | identity tree mismatch FAIL | identity `provenance_tree_sha256` wrong | served-tree helper | ≠0 | tree mismatch | — | I11 |
| T08 | full mode FE tip required | FE commit ≠ tip | verify mode=full | ≠0 | FE != tip | — | Part 4/6 |
| T09 | frontend mode FE tip required | same | mode=frontend | ≠0 | FE != tip | — | Part 6 |
| T10 | backend FE lag allowed | tip backend; FE older but Part 3 OK; frontend_commit=FE | mode=backend | 0 | PASS | — | Part 6.1 |
| T11 | backend broken FE FAIL | lag + bad hash | mode=backend | ≠0 | FAIL | — | Part 6.1 |
| T12 | backend dist bytes unchanged | contract: `md_preserve_*` must not call publish; optional checksum assert in script test of helper with fake roots | deploy_source helper / grep | 0 | no publish call | dist | I10 |
| T13 | restart untouched | grep/contract: restart path does not call publish | test-one-command / phase2 | 0 | — | — | Part 6 |
| T14 | smoke root PASS | tiny HTTP static server or curl against fixture nginx-less python http.server serving index with root+assets | smoke static helpers | 0 | OK static | — | Part 5 |
| T15 | smoke missing root marker FAIL | index without `id="root"` | smoke helper | ≠0 | FAIL marker | — | Part 5 |
| T16 | smoke missing asset FAIL | index refs missing file | smoke helper | ≠0 | FAIL asset | — | Part 5 |
| T17 | smoke wrong content type FAIL | asset returns `text/html` | smoke helper | ≠0 | FAIL content-type | — | Part 5 |
| T18 | SPA routes PASS | server returns 200 index for `/overview` and `/settings/general` | smoke helper | 0 | OK | — | Part 5 |
| T19 | verify PASS ⇏ smoke FAIL | grep: smoke failure calls `md_deploy_fail smoke` after verify stage | test-one-command-deploy.sh | 0 | stages distinct | — | I7 |
| T20 | smoke PASS ⇏ verify FAIL | grep: verify failure calls `md_deploy_fail verify_release` before smoke SUCCESS | test-one-command-deploy.sh | 0 | — | — | I6 |
| T21 | rsync exclude remains | grep `exclude 'dashboard/dist/'` in manage_deploy (≥1 release sync path) | test-deploy-rsync-excludes.sh | 0 | OK | — | I8 |
| T22 | no fixed `/tmp/vr-*` | grep verify_release.sh must **not** contain `/tmp/vr-health.json` etc.; must contain `mktemp` | test-one-command + phase2 | 0 | — | — | Part 4.4 |
| T23 | release-check wiring | `release-check.sh` lists focused phase2 script once | release-check.sh | 0 | step runs | — | gate |
| T24 | Phase 1 publication tests green | existing greps for `md_publish_frontend_artifact`, dist.next, no skip-stamp | test-one-command-deploy.sh | 0 | still pass | publish code | Phase 1 freeze |

Equivalent coverage may merge T14–T18 into one smoke-static subsuite if IDs are reported in the test script header.

---

## 10. Release-check wiring

**Aggregator:** `make release-check` → `scripts/release/release-check.sh`.

**Current required steps (do not duplicate):** backend-unit, deploy-rsync-excludes, deploy-guard, manage-deploy-cli, migrate-release, migrate-machine, empty-target bootstrap, schema-first docs, one-command-deploy, release-worktree-preserve, golden, dashboard vitest/tsc/build, optional migration, optional docker.

**Phase 2 addition (exactly one new required step):**

```text
run_required "Frontend remediation Phase 2" \
  bash "$ROOT/scripts/release/test-frontend-remediation-phase2.sh"
```

Place **after** `One Command Deployment` and **before** or **after** `Release worktree preserve` (either OK; prefer immediately after One Command Deployment).

**Also update (same PR, not a second gate):**

- `test-deploy-rsync-excludes.sh` — add `dashboard/dist/` (T21)  
- `test-one-command-deploy.sh` — T19/T20/T22/T24 contract assertions  

Do **not** create a second full release-check. Do **not** add Phase 2 tests to `test-backend-unit.sh`.

---

## 11. Evidence model

| Artifact | When |
|----------|------|
| Phase 2 implementation report | After code complete, before commit review |
| Phase 2 test report (T01–T24) | After tests green |
| `make release-check` result | Before commit / push authorization |
| Phase 2 commit review | Before push |
| Phase 2 push | After commit approval |
| Phase 2 deployment report | After authorized `deploy full` |
| Phase 2 runtime validation report | After deploy |
| Phase 2 final acceptance review | After RV PASS |
| Full remediation closure review | After Phase 2 accepted |
| S001 final acceptance review | After remediation closure |

**Immutable historical evidence (must not rewrite):**

- `/opt/ai-site-agent/deployments/20260804_182928-e9dbaab.json`  
- Original S001 Runtime Validation FAIL  
- Remediation engineering package + amendment  
- Phase 1 acceptance / `20260804_192430-c9c13d6.json`  

---

## 12. Acceptance checklist (implementation ready for review)

Phase 2 implementation is ready for Implementation Review only if:

- [ ] Scope A–E implemented as specified  
- [ ] Phase 1 publication code unchanged except allowed integration (verify call mode; backend rewrite; no publish edits beyond necessity)  
- [ ] verify-release rejects metadata-only stale FE  
- [ ] verify-release passes valid provenance tree  
- [ ] smoke static checks implemented against PUBLIC_BASE  
- [ ] backend-mode split identity implemented  
- [ ] T01–T24 (or documented equivalents) green  
- [ ] `make release-check` PASS  
- [ ] no dashboard/backend product code changed  
- [ ] no deploy performed in the implementation step  
- [ ] S001 remains NOT_ACCEPTED  
- [ ] S002 remains NOT_STARTED  

---

## 13. Stop conditions (implementer must halt)

Stop and escalate — do **not** invent a solution — if work would require:

- changing provenance schema (`schema_version` / field set)  
- changing atomic publication / `dist.next` flow  
- adding browser E2E  
- changing nginx document root  
- adding frontend artifact archive  
- changing S001 product behavior / Engineering Mode  
- changing release lifecycle semantics (`accepted` / `in_progress` / APP_RELEASE meaning)  

---

## 14. Implementation order (mechanical)

1. Writable temps in `verify_release.sh` (E)  
2. Served-tree provenance + mode-aware FE rules in `verify_release.sh` (A)  
3. Pass mode from `deploy_source.sh` into verify (A)  
4. Backend preserve helper + call site (D)  
5. Smoke static section + PUBLIC_BASE (B)  
6. `test-frontend-remediation-phase2.sh` (C)  
7. Extend rsync exclude test + one-command contracts (C/E)  
8. Wire `release-check.sh` (C)  
9. Evidence docs only after code review  

---

## 15. Package status

```
Phase 2 Implementation Package: FROZEN
Architectural choices left for implementer: NONE (within this package)
Next authorized step: Phase 2 Implementation (code) under this package
```

---

## Final freeze statement

Phase 2 may begin implementation **only** against this package and the amendment.  
Any deviation that reopens Phase 1 publication or product scope is **out of authorization**.
