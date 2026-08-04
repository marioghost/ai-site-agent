# S001 — Frontend Deployment Artifact Remediation Engineering Package

**Type:** RCA + remediation requirements (no implementation in this document’s creation task)  
**Date:** 2026-08-04  
**Incident tip:** `e9dbaab9e6e1ceb11c8672b91270d038755b3303`  
**Deployment report:** `/opt/ai-site-agent/deployments/20260804_182928-e9dbaab.json`  
**Related (separate):** `docs/releases/1.0-step-067-verify-release-rca.md` (`/tmp` curl exit-23 false-negative)  
**Authorities:** S001 Implementation Package; RFC-101 Execution Strategy / Master Program / Roadmap; `deploy/manage_deploy.sh`; `deploy/lib/deploy_source.sh`; `deploy/lib/verify_release.sh`

RFC-100 and Step 067 remain frozen. This package does **not** reopen them.

---

## 1. Incident summary

Canonical `deploy full` for S001 reported **SUCCESS**. Metadata identity surfaces (`.build-info.json`, `dashboard/dist/.deploy-identity.json`, `/api/build`) all resolve to tip `e9dbaab`. Nginx continues to serve a **July 30** dashboard bundle (`index-Dp9nYDKv.js`) that lacks S001 routes, Engineering Mode, and scaffold chunks. Runtime Validation therefore failed: **DEPLOYED_METADATA_ONLY**.

S001 Product Readiness for the **deployed runtime** is **FAIL** until a superseding frontend publication deploy proves served-bundle provenance.

---

## 2. Proven facts

| Fact | Evidence |
|------|----------|
| Tip / report / `.build-info` / `/api/build` = `e9dbaab` | Report JSON; `/opt/.build-info.json`; live `/api/build` |
| S001 dashboard **was built** in deploy worktree | Deploy log stage 5: `building dashboard`, Vite output listing `HomeScreen-*`, `GeneralScreen-*`, `index-DuajgPLY.js`, layouts |
| Worktree path | `/tmp/ai-site-agent-deploy-t9QI57` (log); cleaned by EXIT trap |
| Release rsync **excludes** `dashboard/dist/` | `manage_deploy.sh` `update_source_code` rsync `--exclude 'dashboard/dist/'` |
| Rsync source → dest | `from: /tmp/ai-site-agent-deploy-t9QI57` → `to: /opt/ai-site-agent` (log `deploy-20260804_182908.log`) |
| Skip message refers to **`/opt/.../dashboard/dist/index.html`** | After `PROJECT_ROOT=/opt`, `FRONTEND_BUILD_DIR=$PROJECT_ROOT/dashboard/dist`; log: `frontend artifact already present — skip duplicate npm build` |
| Identity stamped on **stale** `/opt` dist after sync | `.deploy-identity.json` mtime `2026-08-04T18:29:16Z`; `index.html` / `index-Dp9nYDKv.js` mtime `2026-07-30T20:08:42Z` |
| Served bundle lacks S001 markers | Live `index-Dp9nYDKv.js`: no `/settings/general`, `/home`, Mode key; still references `SettingsPage` |
| Nginx root correct | `/etc/nginx/sites-enabled/ai-site-agent` → `root /opt/ai-site-agent/dashboard/dist;` |
| `dashboard/dist` not in git | `git ls-files dashboard/dist` → 0 files |
| verify-release / smoke did not inspect bundle content | `verify_release.sh` JSON + `index.html` existence; `smoke-staging.sh` API-only |

---

## 3. Identity layers (must not be equated)

| Layer | What it is | S001 deploy result |
|-------|------------|-------------------|
| **Metadata identity** | `.build-info.json`, `.deploy-identity.json`, `/api/build` commit fields | `e9dbaab` (aligned) |
| **Source identity** | `origin/main` / worktree commit | `e9dbaab` |
| **Built artifact identity** | Vite output under deploy worktree `dashboard/dist` | Produced at stage 5 (S001 chunks); then discarded with worktree |
| **Served artifact identity** | Files nginx actually reads under `/opt/.../dashboard/dist` | Pre-S001 July 30 bundle |

---

## 4. Artifact lifecycle trace

```
origin/main (e9dbaab)
  → [deploy_source.sh §5] git worktree add → /tmp/ai-site-agent-deploy-XXXXXX
  → write-build-info.sh → worktree/.build-info.json (e9dbaab, build_time 18:28:59Z)
  → npm run build → worktree/dashboard/dist (S001 assets, e.g. index-DuajgPLY.js)
  → md_write_frontend_identity(worktree) → worktree/dashboard/dist/.deploy-identity.json
  → [deploy_source.sh §6] DEV_CHECKOUT=worktree; MD_RELEASE_DEPLOY=1
  → manage_deploy.sh --mode full --sync-from-dev
       → update_source_code: rsync worktree → /opt
            EXCLUDES dashboard/dist/   ← built UI does not travel
            INCLUDES .build-info.json ← metadata travels
       → mode_full:
            deploy_backend (no UI rebuild)
            if /opt/dashboard/dist/index.html exists:
              skip npm build
              write_frontend_deploy_identity  ← stamps e9dbaab onto OLD /opt dist
            nginx reload
  → post-sync assert_frontend_identity(/opt) checks JSON only → PASS
  → verify-release: tip == build-info == FE JSON == /api/build → PASS
  → smoke: API endpoints only → PASS
  → worktree removed (cleanup) → correct S001 dist destroyed
  → nginx serves July 30 assets
```

### Edge table (critical edges)

| Edge | Producer | Source | Destination | Exclusion / skip | Result |
|------|----------|--------|-------------|------------------|--------|
| Build Vite | `deploy_source.sh` stage 5 | tip source in worktree | `$WT/dashboard/dist` | none | S001 dist created |
| Stamp FE id (build) | `md_write_frontend_identity` | tip commit | `$WT/dashboard/dist/.deploy-identity.json` | — | Correct stamp on correct dist |
| Rsync code | `update_source_code` | `$WT/` | `/opt/ai-site-agent/` | **`--exclude 'dashboard/dist/'`** | New dist **not** published |
| Rsync build-info | same rsync | `$WT/.build-info.json` | `/opt/.build-info.json` | not excluded | Metadata updated |
| Skip rebuild | `mode_full` | existence of **`/opt/.../index.html`** | — | treats any prior dist as “already present” | Rebuild skipped |
| Stamp FE id (sync) | `write_frontend_deploy_identity` | `MD_DEPLOY_COMMIT` | **`/opt/.../.deploy-identity.json`** | no content check | False identity on stale bundle |
| FE assert | `deploy_guard_assert_frontend_identity` | JSON `git_commit` | — | no hash/route check | PASS |
| verify-release | `verify_release.sh` | JSON + file exists | — | no bundle markers | PASS |
| smoke | `smoke-staging.sh` | `/api/*` | — | no SPA checks | PASS |

### Exact meaning of “frontend artifact already present — skip duplicate npm build”

- Evaluated when `MD_RELEASE_DEPLOY=1` and `-f "$FRONTEND_BUILD_DIR/index.html"`.
- With `PROJECT_ROOT=/opt/ai-site-agent`, `FRONTEND_BUILD_DIR=/opt/ai-site-agent/dashboard/dist`.
- The message refers to the **destination** `/opt` dist (stale July 30 `index.html`), **not** the worktree dist, not a backup artifact, not the operator checkout.
- Comment above the skip claims stage 2 “already built+**rsynced** dist”. Stage 5 builds dist; rsync **excludes** it. The comment’s rsync claim is **false relative to the code**.

---

## 5. Sync / rsync analysis

### Why `dashboard/dist` is excluded

Intentional for **source sync**: `dist` is not a git-tracked source tree; excluding it avoids wiping or syncing empty/absent `dist` from checkouts and preserves runtime static files across code-only syncs.

### Is exclusion itself the defect?

**No — not alone.** Exclusion is a source-sync policy. The defect is the **missing/broken separate frontend artifact publication step** after worktree build:

1. Code comments and skip logic **assume** worktree dist was rsynced into `/opt`.
2. Rsync **does not** publish dist.
3. Skip logic then refuses to rebuild at `/opt` whenever **any** prior `index.html` exists.
4. Identity is rewritten onto that prior dist.

**Answer required by RCA:**  
`dist` exclusion is a necessary half of a two-step design that was never completed (or was broken). The **defect is the missing/broken publication handoff**, amplified by incorrect “already present” detection and provenance-free identity stamping.

---

## 6. Identity stamp analysis

| File | Written when | Path written |
|------|--------------|--------------|
| `.build-info.json` | Stage 5 via `write-build-info.sh` on **worktree**; then rsynced to `/opt` | Worktree → `/opt` (synced) |
| `.deploy-identity.json` (correct) | Stage 5 `md_write_frontend_identity` on **worktree dist** | Worktree only (never synced) |
| `.deploy-identity.json` (false) | Stage 6 `mode_full` `write_frontend_deploy_identity` after skip | `/opt/dashboard/dist/` **on stale files** |

`write_frontend_deploy_identity` / `md_write_frontend_identity` write commit/release JSON only. They do **not** bind to asset hashes, `index.html` script tags, or build timestamps of JS/CSS.

**Invariant that should have prevented this:**  
Identity may be stamped only onto an artifact tree whose content was produced from the target commit in the same deploy (provenance), and publication of that tree to the nginx root must succeed before SUCCESS. Existence of `index.html` alone is insufficient.

---

## 7. Why deploy verification passed

### verify-release (`deploy/lib/verify_release.sh`)

Checks:

- tip / build-info / FE JSON / `/api/build` commit equality  
- FE identity file exists  
- `dashboard/dist/index.html` exists  

Does **not** check:

- `index.html` referenced asset names vs tip build  
- JS content markers (e.g. `/settings/general`, Mode key)  
- asset mtimes vs `build_time`  
- worktree→`/opt` dist provenance  

### smoke (`scripts/release/smoke-staging.sh`)

API health/metrics/build/login/settings + golden unit tests. **No** SPA/HTML/asset checks.

### Separate known issue

Standalone verify-release `/tmp/vr-*.json` root ownership → curl exit 23 = **tooling false-negative** (Step 067 RCA). **Not** the cause of metadata SUCCESS with stale UI.

---

## 8. Root cause candidates

| ID | Candidate | Supporting | Contradicting | Verdict | Confidence |
|----|-----------|------------|---------------|---------|------------|
| A | Build did not execute | — | Stage 5 Vite log with S001 chunk names | **Reject** | High |
| B | Build wrong path | — | Build under `$WT/dashboard`; index.html asserted there | **Reject** | High |
| C | Rsync exclusion removed only publication path | Exclude present; worktree dist never at `/opt` | Exclusion intentional for source | **Contributing cause** | High |
| D | Separate frontend-copy stage missing | No dedicated dist publish; comment falsely claims rsync | — | **Primary structural gap** | High |
| E | Frontend-copy/skip skipped incorrectly | Skip on `/opt` stale `index.html` | — | **Primary behavioral bug** | High |
| F | Existing-artifact detection wrong location | Detects `/opt` not worktree | — | **Confirm** | High |
| G | Identity stamp independent of provenance | Stamp after skip on old dist; mtimes prove it | — | **Confirm** | High |
| H | verify/smoke lack bundle validation | Code inspection | — | **Confirm (detection gap)** | High |
| I | Nginx wrong root | — | root = `/opt/.../dashboard/dist` | **Reject** | High |
| J | Ownership blocked replace | — | Files never targeted for replace | **Reject** | High |
| K | Other | Worktree cleanup deletes correct dist | — | Contributing cleanup | High |

---

## 9. Proven root cause (causal chain)

**Trigger:** S001 `deploy full` for tip `e9dbaab` (dashboard-changing commit).

→ **Broken deploy invariant:** Stage 5 builds+stamps frontend in the clean worktree, but stage 6 rsync excludes `dashboard/dist/`, and `mode_full` treats any existing `/opt/dashboard/dist/index.html` as “already published for this release,” skipping rebuild and calling `write_frontend_deploy_identity` on the destination tree.

→ **Stale artifact preserved:** July 30 `index.html` / `index-Dp9nYDKv.js` remain the nginx payload.

→ **New identity stamped:** `/opt/.../.deploy-identity.json` and synced `.build-info.json` / restarted backend report `e9dbaab`.

→ **Verification failed to detect mismatch:** verify-release and post-sync FE assert compare JSON commits and file existence only; smoke never reads the SPA bundle.

→ **Runtime served old UI:** nginx root correctly pointed at `/opt/.../dist`, which still contained the pre-S001 bundle.

**Unknowns:** None required for this causal chain. The ephemeral worktree dist is gone (cleanup); its prior existence is established by the stage 5 build log asset list (`index-DuajgPLY.js`, S001 screens), not by residual files on disk.

---

## 10. Remediation requirements (implement later — not in this task)

1. Built frontend artifacts are published **atomically** to the nginx root.  
2. `dashboard/dist` source-sync exclusion **must not** preserve stale runtime assets across commits that require a new UI.  
3. Identity is stamped **only** onto the artifact produced from the target commit.  
4. Deploy **fails before SUCCESS** if frontend publication fails (full/frontend modes).  
5. Old and new bundle files must not be mixed (replace tree / atomic swap).  
6. Rollback restores the **matching** previous frontend artifact with metadata.  
7. verify-release proves **served bundle provenance**, not metadata alone.  
8. Smoke confirms representative canonical S001 routes load (at least static markers / asset references).  
9. Backend-only deploy remains valid when mode is backend.  
10. No manual rsync/copy becomes the canonical operator solution.

### Forbidden fixes

- Manual copy of dist to `/opt` as the process  
- Blind removal of all rsync exclusions  
- Stamping identity without provenance validation  
- Treating smoke PASS as sufficient for UI publication  
- Accepting S001 on metadata alone  
- Changing nginx root as a workaround  
- Disabling frontend build checks  
- Committing built `dist` unless repository contract explicitly requires it  
- Starting S002 before S001 acceptance  

---

## 11. Expected implementation scope (for future remediation step)

| Area | Modules (expected) |
|------|---------------------|
| Publication handoff | `deploy/lib/deploy_source.sh`, `deploy/manage_deploy.sh` (`update_source_code` / `mode_full` / `deploy_frontend` / identity writers) |
| Guards | `deploy/lib/deploy_guard.sh` (provenance assert beyond JSON) |
| verify-release | `deploy/lib/verify_release.sh` |
| smoke | `scripts/release/smoke-staging.sh` (bounded SPA/static checks) |
| Tests | Deploy-script unit/integration tests proving: worktree build → `/opt` dist content match; skip path cannot stamp stale dist; backend-only leaves UI policy explicit |
| Docs | Remediation evidence + updated deploy notes; **do not rewrite** historical S001 SUCCESS report contents |

Out of scope: RFC-100, Step 067 product reopen, S002 feature work, nginx root relocation, Product Completion feature packages.

---

## 12. Test requirements

- Unit/contract: rsync (or dedicated publish) of worktree `dashboard/dist` → nginx root for `full`/`frontend`.  
- Negative: with stale `/opt` dist and new worktree dist, SUCCESS is impossible unless destination content matches tip markers.  
- Identity: cannot write `.deploy-identity.json` claiming tip unless provenance check passes.  
- verify-release fails if `index.html` script src / content marker ≠ tip build.  
- smoke fails if representative canonical route asset/marker missing.  
- Backend-only mode does not require UI publish (explicit).  
- Rollback drill restores prior dist + matching identity.

---

## 13. Deployment verification requirements (post-remediation)

- Report SUCCESS only with served-bundle provenance.  
- Live `index.html` asset names match the tip build’s dist.  
- Served JS contains S001 markers agreed in smoke/verify (e.g. `/settings/general`, Mode storage key, or build-id file).  
- Metadata chain remains aligned **and** bound to that bundle.  
- Historical S001 report `20260804_182928-e9dbaab.json` remains as evidence of the defect era; superseding deploy gets a new report.

---

## 14. Rollback requirements

- Ordinary code+artifact rollback to previous deploy tip’s published frontend tree.  
- No DB restore required for UI-only remediation.  
- Matching `.build-info` / FE identity for the rolled-back artifact.

---

## 15. Historical evidence preservation

**Do not edit:**

- `/opt/ai-site-agent/deployments/20260804_182928-e9dbaab.json`  
- S001 implementation evidence / Gate records as historical implementation artifacts  
- Step 067 verify-release RCA  

**Add** this package + future remediation evidence as superseding trail.

---

## 16. Product Readiness effect

| Scope | Status |
|-------|--------|
| S001 implementation (source) | Implemented / committed / pushed |
| S001 deployed runtime (served UI) | **FAIL** — metadata-only deploy |
| Gate for acceptance | Blocked until remediation deploy proves served S001 UI |

Debt DEBT-S001-01/02 remains relevant only **after** the correct UI is served.

---

## 17. Acceptance sequence (after remediation)

1. Remediation implementation + tests  
2. Review / commit / push (authorized)  
3. `deploy full`  
4. Runtime validation proving served S001 bundle  
5. Final Acceptance Review  
6. Only then S001 ACCEPTED → S002 may start  

---

## 18. Status snapshot (at RCA time)

```
S001:
  IMPLEMENTED
  COMMITTED
  PUSHED
  DEPLOYED_METADATA_ONLY
  RUNTIME_VALIDATION_FAIL
  NOT_ACCEPTED

S002:
  NOT_STARTED

Product Readiness:
  FAIL for deployed S001 runtime until superseding frontend deployment evidence exists.
```
