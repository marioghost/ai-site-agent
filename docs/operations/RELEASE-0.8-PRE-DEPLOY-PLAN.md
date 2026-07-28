# Release 0.8 — Pre-Deploy Plan (read-only / approval gate)

**Status:** Planning only — **do not deploy**, **do not migrate**, **do not change Settings**, **do not touch Qdrant** until this plan is explicitly approved for **execution**.  
**Date:** 2026-07-28  
**Operator entry point (only):** `bash deploy/manage_deploy.sh <command>`  
**Syntax:** `bash deploy/manage_deploy.sh help`  
**Governance:** After approved schema-first deploy + runtime validation, next program is [POST-0.8-MACHINE-MIGRATION.md](POST-0.8-MACHINE-MIGRATION.md). Release **0.9** remains blocked.

---

## 0. Push / commit gates

### 0.1 Engineering tip on `origin/main` (completed)

| Check | Result |
|-------|--------|
| `main` / `origin/main` | `29320cfdef3d54f8396448b46d8e4f238277140e` |
| Closure feature | `4bec81f` on `origin/main` |
| Closure merge | `29320cf` on `origin/main` |

### 0.2 This plan document

Must be committed, pushed, and present on `origin/main` with a **clean** working tree before any operational deploy.  
**Do not** run `deploy full` from a dirty tree (including an untracked plan file).

**Deploy / migrate still require separate execution approval.**

---

## Approved operator sequence (schema-first)

**Normal Release 0.8 cutover order:**

1. `status`
2. Verify local `main` == `origin/main` and working tree **clean**
3. Read-only baseline collection where available (do not fabricate)
4. `backup db`
5. `migrate` (0018 → 0019 / head **0019**)
6. Verify Alembic head == `0019_legacy_doc_type_canonical_enabled`
7. `deploy full`
8. `health`
9. `build-info`
10. `smoke`
11. `verify-release`
12. Manual dashboard / Sources / Chat / Understanding checks
13. Preset API **410** checks
14. Step 055 overview/news quality evaluation
15. Corpus / Qdrant before–after comparison

### Canonical commands (after execution approval only)

```bash
bash deploy/manage_deploy.sh status
bash deploy/manage_deploy.sh backup db
bash deploy/manage_deploy.sh migrate
sudo bash deploy/manage_deploy.sh deploy full
bash deploy/manage_deploy.sh health
bash deploy/manage_deploy.sh build-info
bash deploy/manage_deploy.sh smoke
bash deploy/manage_deploy.sh verify-release
```

Do **not** invent unsupported commands. Do **not** use standalone deploy scripts.

---

## Why migration comes before `deploy full`

**PROVEN BY CURRENT CODE** — migrations `0018_allow_legacy_kp_presets` and `0019_legacy_doc_type_canonical_enabled`:

- Additive only: `op.add_column` on `settings`
- `nullable=False` with `server_default=sa.false()`
- Downgrades are `op.drop_column` only
- Structural unit tests assert additive + `server_default=sa.false()` (`test_step_054_*`, `test_step_055_*`)

**Compatibility direction:**

| Order | Risk |
|-------|------|
| **Schema first** (migrate while `/opt` still runs Release **0.7**) | Safe expected path: old ORM maps only known columns; extra DB columns are ignored by SQLAlchemy selects. New boolean columns default **false** via server default — no Settings rewrite required. |
| **Deploy first** (start Release **0.8** code before 0018/0019) | **Unsafe:** Release 0.8 ORM / Settings / feature-flag helpers expect `allow_legacy_kp_presets` and `legacy_doc_type_canonical_enabled`. Missing columns can break Settings-backed endpoints or service startup when the new process loads the model. |

Therefore **schema-first is the safer compatibility direction**. No evidence was found that Release 0.7 code fails when these additive columns exist; if live migrate proves otherwise, **stop** and report evidence — do not guess.

`deploy full` still performs its own mandatory backup → build → deploy → verify → restart → smoke from a clean `origin/main` worktree. That is fine **after** migrate succeeds.

---

## Migration failure gate

If `bash deploy/manage_deploy.sh migrate` **fails**:

1. **Do not** run `deploy full`
2. Leave the existing `/opt` Release **0.7** deployment **unchanged**
3. Record full migration output / logs
4. Verify current backend/runtime remains on the old release where possible (`status`, `build-info` if API up)
5. **Do not** retry with manual SQL
6. **Do not** downgrade automatically
7. **Stop** for operator review

### After a successful migrate (before deploy)

Verify:

- Alembic head = `0019_legacy_doc_type_canonical_enabled`
- Columns `allow_legacy_kp_presets` and `legacy_doc_type_canonical_enabled` exist
- Existing Settings rows resolve to **false** (server default / no manual PUT)
- Corpus tables/counts unchanged vs pre-migrate measurement (or honest “unverified” if API down)
- No Qdrant mutation

**Do not** change Settings values manually.

---

## 1. Current `origin/main` commit

| Field | Value |
|-------|--------|
| Tip | `29320cfdef3d54f8396448b46d8e4f238277140e` (+ this plan commit once pushed) |
| Confirm | `bash deploy/manage_deploy.sh status` / `git rev-parse origin/main` |

---

## 2. Current `/opt` deployed commit

| Field | Last read-only observation (2026-07-28) | Re-check |
|-------|------------------------------------------|----------|
| `/opt` build-info | `d3cf472724ce` · `release=0.7` | `bash deploy/manage_deploy.sh status` |
| Frontend identity | `d3cf472724ce` | same |
| Repo code `APP_RELEASE` | `0.8` (not live until deploy) | status |

---

## 3. Current `/api/build` identity

| Field | Last observation | Re-check after services up |
|-------|------------------|----------------------------|
| API | **unreachable** (health DOWN) | `bash deploy/manage_deploy.sh build-info` |
| After successful migrate+deploy+restart | `accepted=0.8`, `closed_0_8=true`, `staging_validated=false`, `production_ready=false`, commit matches `origin/main` | `build-info` + `verify-release` |

Do **not** fabricate live `/api/build` values.

---

## 4. Current live Alembic revision

| Field | Note |
|-------|------|
| Code head | `0019_legacy_doc_type_canonical_enabled` |
| Live DB | **Not claimed** at 0018/0019; often still **0017** until migrate |
| Record | Capture live revision **before** migrate when DB is reachable |

---

## 5. Current Settings flags

Expected after successful migrate (defaults — no PUT):

| Flag | Expected |
|------|----------|
| `allow_legacy_kp_presets` | **false** |
| `legacy_doc_type_canonical_enabled` | **false** |
| Memory assist / shadow | **false** |

---

## 6–7. Corpus / Qdrant baselines (honesty)

The following are **historical expected baselines** from the latest accepted operational report — **not** current live proof:

| Metric | Historical expected |
|--------|---------------------|
| sources | 5023 |
| chunks | 17958 |
| claims | 39 |
| observations | 13 |
| evidence links | 21 |
| knowledge_version | 26 |
| memory_version | 177 |
| fixture.example sources | 0 |
| Qdrant `site_knowledge` | 18780 |

**Current live values are unverified** (API/Qdrant last observed DOWN/unreachable).

- Re-measure before migrate/deploy if services can be brought up **read-only**
- Never fabricate the pre-deploy state
- If the old backend is **intentionally down**, record that fact and continue **only** with operator approval

---

## 8. Fresh PostgreSQL backup

```bash
bash deploy/manage_deploy.sh backup db
```

Required **before** migrate. (`deploy full` also mandates a backup later in its own chain.)

---

## 9. Migrate (before deploy)

```bash
bash deploy/manage_deploy.sh migrate
```

Expect head **`0019_legacy_doc_type_canonical_enabled`**. Apply failure gate above on any error.

---

## 10. Deploy full (only after migrate success)

Preconditions:

```bash
bash deploy/manage_deploy.sh status
# require: main, clean tree, main == origin/main == approved tip
```

```bash
sudo bash deploy/manage_deploy.sh deploy full
```

From **clean `origin/main` worktree** only. Forbidden: feature branches, dirty trees, local-only commits, emergency overrides, standalone scripts.

Restart is included in `deploy full`. Separate bounce only if later required:

```bash
bash deploy/manage_deploy.sh restart backend
```

---

## 11–12. Health / build / smoke / verify-release

```bash
bash deploy/manage_deploy.sh health
bash deploy/manage_deploy.sh build-info
bash deploy/manage_deploy.sh smoke
bash deploy/manage_deploy.sh verify-release
```

---

## 13. Manual UI checks

Dashboard, Sources, Chat (+ follow-up), Understanding. Memory Assist/Shadow remain **OFF**.

---

## 14. Preset API 410

With defaults after 0018:

- `GET /api/knowledge-profile/presets` → **410**
- `POST …/presets/load` → **410**
- code `legacy_kp_presets_disabled`

---

## 15. `legacy_doc_type_canonical_enabled` default false

Settings GET **false**; do not set true unless approved Level-1 quality rollback.

---

## 16. Step 055 overview / news quality

Known risk: **news → about → homepage**. Document samples; Level-1 rollback = Settings `legacy_doc_type_canonical_enabled=true` ([0.8-rollback.md](../releases/0.8-rollback.md)).

---

## 17. Corpus / Qdrant before–after

Compare measured pre/post counts. Expect no corpus rewrite and no Qdrant mutation. Do not clear Qdrant or reindex for validation.

---

## 18. Rollback plan

See [0.8-rollback.md](../releases/0.8-rollback.md).

| Level | Action |
|-------|--------|
| 1 | Settings flags as documented |
| 2 | Known-good tip on `origin/main` → `sudo bash deploy/manage_deploy.sh deploy full` → `verify-release` |
| 3 | Schema downgrade only under explicit ops approval |

Forbidden: `ai_site_agent_recovery` feature rollback; Qdrant clear; reindex-as-rollback; emergency deploy for routine rollback.

---

## 19. Stop for approval (execution)

**This document does not authorize execution.**

Before any of the following, obtain an explicit go-ahead:

- [ ] Plan commit on `origin/main`; working tree clean
- [ ] Fresh `backup db`
- [ ] `migrate` (0018/0019)
- [ ] `deploy full`
- [ ] Any Settings PUT
- [ ] Machine migration

---

## Classification reminder

| State | Value |
|-------|-------|
| Engineering Ready | PASS |
| Staging Validated | false |
| Production Ready | false |
| Deployment (this plan) | **not executed** |
| Migrations 0018/0019 live | **not applied** (until approved) |
| Machine migration | planned, not executed |
| Release 0.9 | blocked |
