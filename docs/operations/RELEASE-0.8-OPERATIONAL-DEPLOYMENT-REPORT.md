# Release 0.8 — Operational Deployment Report

**Status:** Deployment **executed and accepted**  
**Deployment date:** 2026-07-29 (window 2026-07-28T20:32Z → 2026-07-29T07:03Z)  
**Deployed commit:** `39ebef1b76a4236a8e608d7300cbecf0107f75b4`  
**Related:** [RELEASE-0.8-PRE-DEPLOY-PLAN.md](RELEASE-0.8-PRE-DEPLOY-PLAN.md) ·
[RELEASE-0.8-ACCEPTANCE-REPORT.md](../releases/RELEASE-0.8-ACCEPTANCE-REPORT.md) ·
[POST-0.8-MACHINE-MIGRATION.md](POST-0.8-MACHINE-MIGRATION.md) ·
[RELEASE-CHECKLIST.md](../releases/RELEASE-CHECKLIST.md)

**Public operator entry point:**

```bash
bash deploy/manage_deploy.sh <command>
```

This document records the **operational deployment** of Release 0.8 onto the live host. It is the
companion to the engineering acceptance report: engineering closure proved the code, this document
proves the deployment. It records evidence only — it grants no lifecycle promotion.

> **This report does not mark `staging_validated` or `production_ready` true.** Both remain `false`.

---

## 1. Deployment date and commit

| Item | Value |
|------|-------|
| Deployment date | **2026-07-29** |
| Deployment window | 2026-07-28T20:32Z (Gate A) → 2026-07-29T07:03Z (Gate E close) |
| `origin/main` | `39ebef1b76a4236a8e608d7300cbecf0107f75b4` |
| Deployed commit | `39ebef1b76a4236a8e608d7300cbecf0107f75b4` |
| Commit subject | `merge(feat): schema-first migrate release for Release 0.8 cutovers` |
| Release | **0.8** |
| Build time (artifact) | `2026-07-29T06:57:54Z` |
| Previous live state | release **0.7**, commit `d3cf472724ce`, Alembic `0017_memory_canonical_shadow_enabled` |
| Deployment method | `bash deploy/manage_deploy.sh migrate release` → `deploy full` (canonical schema-first order) |
| Host | single-host Linux (WSL2), `/opt/ai-site-agent` |

Commit ancestry note: the Gate A baseline was captured at repository tip `4de1e38`
(`docs(ops): Release 0.8 pre-deploy plan`). `39ebef1` is its descendant merge, pushed to
`origin/main` before Gate C. This is expected ancestry, not drift.

---

## 2. Gate A–E results

| Gate | Command | Result | Evidence |
|------|---------|--------|----------|
| **A** | `status`, `health` | **PASS** (baseline recorded) | `/opt/ai-site-agent/logs/deploy-20260728_233233.log` |
| **B** | `backup db` | **PASS** (dump + checksum + restore-list) | see §3 |
| **C** | `migrate release` | **PASS** (`0017` → `0018` → `0019`) | `/opt/ai-site-agent/logs/migrate-release-20260729_002022.log` |
| **D** | `deploy full` | **PASS** (6/6 stages) | `/opt/ai-site-agent/logs/deploy-20260729_0958*.log` |
| **E** | `health`, `build-info`, `smoke`, `verify-release` | **PASS** (`PASS=15 FAIL=0 WARN=1`) | §9, §6 |

### Gate A — baseline (2026-07-28T20:32Z)

| Item | Baseline value |
|------|----------------|
| Repository | branch `main`, tree clean, tip `4de1e38` |
| `/opt` build-info | `d3cf472724ce`, release **0.7** |
| `/opt` frontend | `d3cf472724ce` |
| `/api/build` | `d3cf472724ce`, release **0.7** |
| Live Alembic revision | `0017_memory_canonical_shadow_enabled` |
| Flags | `memory_evidence_assist_enabled=off`, `memory_canonical_shadow_enabled=off`, `cache_namespace_v2_enabled=off`, `memory_shadow_write_enabled=off`, `REASONING_SERVICE_ENABLED=off` |
| Health | backend UP, Ollama OK, Qdrant OK, frontend build present |
| `index_job_status` | `completed` |

The `Overall: NOT OK` line in the Gate A `status` output was **expected**: it reflects the
intended pre-deploy drift (`/opt` at 0.7 while `origin/main` carried 0.8), not a fault.

`health` reported `nginx service: not active` and all module units as `unit missing` in both the
Gate A baseline and the Gate E re-run. **These lines are false negatives, not host conditions.**
Root cause: `module_unit_exists()` probes units via `run_root systemctl cat <unit>.service`, and
`run_root` shells out to `sudo` whenever the caller is not root. In a non-interactive shell `sudo`
cannot prompt, so the probe fails and the failure is rendered as `unit missing` rather than
"undetermined". The same applies to the nginx `is-active` probe.

Verified host state (all five units **enabled and active**): `ai-agent-backend`, `qdrant`,
`ollama`, `nginx`, `postgresql` — unit files present at `/etc/systemd/system/`
(`ai-agent-backend.service`, `qdrant.service`, `ollama.service`), `systemctl is-system-running`
reports `running`, and systemd is PID 1 under WSL2. Direct proof from Gate D, which ran as root and
therefore took the non-`sudo` branch:

```text
[OK]   Nginx service: OK
```

Gate D also performed real unit operations successfully (`Backend stopped`, `Backend is active`),
and `nginx -t` plus reload succeeded. So the deployment exercised systemd correctly; only the
unprivileged `health` invocations misreported.

**Deferred observability debt — DEBT-0.8-002:** `health` should distinguish "cannot determine
(insufficient privilege)" from "unit missing" / "not active" instead of collapsing both into a
failure label, because the current output invites the false conclusion that the host has no service
management. **Not implemented; no fix authorized in this task.** This affects operator readouts
only — no runtime behaviour — and it is environment-independent, so it does **not** block the
machine migration.

### Gate D — `deploy full` stage results

| Stage | Result | Detail |
|-------|--------|--------|
| 1/6 BACKUP | **OK** | `pg_dump` → `ai_site_agent.20260729_095751.dump` |
| 2/6 BUILD | **OK** | clean worktree `/tmp/ai-site-agent-deploy-pmGNlC` at `39ebef1`; `tsc --noEmit` + `vite build` (1974 modules, 3.14 s) |
| 3/6 DEPLOY | **OK** | rsync → `/opt`; pip deps satisfied; **internal Alembic upgrade was a no-op** (§5) |
| 4/6 VERIFY | **OK** | `APP_RELEASE=0.8` == `build-info=0.8` |
| 5/6 RESTART | **OK** | backend stop/start, HTTP ready, nginx reloaded |
| 6/6 SMOKE | **OK** | 6 HTTP checks + 41 golden parity tests (§9) |

Backup de-duplication behaved correctly: stage 3 logged
`Backup already completed in release stage 1 — skipping duplicate pg_dump`. Frontend artifact reuse
behaved correctly: `Release deploy: frontend artifact already present — skip duplicate npm build`.

---

## 3. Backup paths and checksums

All three dumps are custom-format PostgreSQL dumps of `ai_site_agent`, present on disk and
validated with `pg_restore --list` (217 entries, 19 `TABLE DATA` entries, `public.settings`
present in each).

| Dump | Role | Size (bytes) | SHA256 |
|------|------|--------------|--------|
| `ai_site_agent.20260728_233243.dump` | Gate B pre-deploy backup (2026-07-28T20:32:43Z) | 11 637 817 | `d7f779753244431011403b7b2229280cf028cdb71ac08a462a8687d3892a4ef0` |
| `ai_site_agent.20260729_001833.dump` | pre-`migrate release` backup (2026-07-28T21:18:33Z) | 11 637 585 | `28fe345138621744357e398b46bae2e338419ddc670734a1aa1b9bc358255240` |
| `ai_site_agent.20260729_095751.dump` | Gate D stage-1 mandatory backup (2026-07-29T06:57:51Z) | 11 636 846 | `819a07bdbe24bec80fe5d47e29d24032c1fd9dc2df0e810f8d1273b9020d3af6` |

Directory: `/opt/ai-site-agent/backups/`

Restore-list validation, per dump:

| Check | Result |
|-------|--------|
| `pg_restore --list` exit status | **0** (all three) |
| Table-of-contents entries | 217 (all three) |
| `TABLE DATA` entries | 19 (all three) |
| `public.settings` present | **yes** (all three) |

Rollback ordering: `ai_site_agent.20260728_233243.dump` and `ai_site_agent.20260729_001833.dump`
are **pre-0019** (schema at `0017`); `ai_site_agent.20260729_095751.dump` is **post-0019**. Choose
the target by the schema state you intend to return to. The separate incident database
`ai_site_agent_recovery` was **not** touched at any point in this deployment.

---

## 4. Schema-first migration evidence

`migrate release` advanced the live schema **exactly once**, from a clean `origin/main` worktree,
while the old backend was still running. Source: `migrate-release-20260729_002022.log`.

| Field | Value |
|-------|-------|
| Started | `2026-07-29T00:20:22+03:00` (2026-07-28T21:20:22Z) |
| `origin/main_commit` | `39ebef1b76a4236a8e608d7300cbecf0107f75b4` |
| Migration source | `/tmp/ai-site-agent-migrate-release-mWUpxz/backend` (clean worktree) |
| `/opt` backend used for Alembic? | **no** (`live_opt_backend_not_used=/opt/ai-site-agent/backend`) |
| Target database | `ai_site_agent` @ `localhost:5432` |
| Repository Alembic head | `0019_legacy_doc_type_canonical_enabled` |
| `pre_revision` | `0017_memory_canonical_shadow_enabled` |
| `post_revision` | `0019_legacy_doc_type_canonical_enabled` (head) |
| `migrate_exit_code` | `0` |
| Column verification | `OK: columns present; 2 settings row(s) both false` |
| `verification` | **PASS** |
| `opt_code_synced` | **no** |
| `services_restarted` | **no** |
| `qdrant_touched` | **no** |

Applied revisions, verbatim:

```text
INFO  [alembic.runtime.migration] Running upgrade 0017_memory_canonical_shadow_enabled -> 0018_allow_legacy_kp_presets, RFC-100 Step 054 — allow_legacy_kp_presets settings flag (default false).
INFO  [alembic.runtime.migration] Running upgrade 0018_allow_legacy_kp_presets -> 0019_legacy_doc_type_canonical_enabled, RFC-100 Step 055 — legacy_doc_type_canonical_enabled settings flag (default false).
```

Corpus was identical before and after the migration (`sources=5023, chunks=17958, claims=39,
observations=13, evidence_links=21` in both snapshots), and the report explicitly records
`NOTE: no Qdrant commands are invoked by migrate release`.

The command refused to run under emergency-override environment variables, as designed; no
override was used.

---

## 5. Internal `deploy full` Alembic no-op evidence

The approved semantics — `deploy full` retains its post-sync Alembic upgrade as an **idempotent
defense-in-depth check**, not as the schema-advancement mechanism — are now proven against the live
host rather than inferred.

Gate D stage 3, verbatim from `/tmp/release-08-deploy-full.log`:

```text
[INFO] Applying Alembic migrations (alembic upgrade head)...
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
OK: database migrated to head (revision 0019_legacy_doc_type_canonical_enabled)
[OK]   Database schema is up to date
```

**No `Running upgrade` line was emitted.** Compare with the Gate C log in §4, which emitted two.
Alembic was revision-aware: it read `alembic_version` as already at `0019`, found nothing to apply,
and reported head.

| Property | Evidence |
|----------|----------|
| Schema advanced exactly once | two `Running upgrade` lines in Gate C; zero in Gate D |
| Gate D behaviour | revision-aware **no-op** at `0019` |
| Duplicate DDL | **none** |
| Extra failure surface | **none observed** — stage 3 passed |
| Operator semantics | unchanged; `deploy full` remains safe to run after `migrate release` |

This validates the recorded policy in
[RELEASE-0.8-PRE-DEPLOY-PLAN.md](RELEASE-0.8-PRE-DEPLOY-PLAN.md): the internal migration is a
verification safety net, and `migrate release` remains the **only** supported schema-first command.

The known policy limitation is unchanged and still applies: the CLI **does not** hard-block
`deploy full` when the schema-first step was skipped. Enforcement remains operator workflow plus
documentation. The deferred preflight follow-up recorded in the pre-deploy plan is **still
deferred** and was **not** implemented as part of this deployment.

---

## 6. Backend / frontend / API identity chain

`verify-release` reported **FULL CHAIN ALIGNED**:

```text
origin/main : 39ebef1b76a4236a8e608d7300cbecf0107f75b4
build-info  : 39ebef1b76a4236a8e608d7300cbecf0107f75b4
frontend    : 39ebef1b76a4236a8e608d7300cbecf0107f75b4
/api/build  : 39ebef1b76a4236a8e608d7300cbecf0107f75b4
PASS  FULL CHAIN ALIGNED (origin/main == build-info == frontend == /api/build)
```

| Surface | Source of truth | Commit | Release |
|---------|-----------------|--------|---------|
| `origin/main` | git | `39ebef1b76a4…` | — |
| Backend on disk | `/opt/ai-site-agent/.build-info.json` (`backend_commit`) | `39ebef1b76a4…` | 0.8 |
| Frontend artifact | `/opt/ai-site-agent/dashboard/dist/.deploy-identity.json` | `39ebef1b76a4…` | 0.8 |
| Running API | `GET /api/build` | `39ebef1b76a4…` | 0.8 |

`source_ref` is `origin/main` and `build_time` is `2026-07-29T06:57:54Z` on both the deployed
build-info and the API response. `verify-release` sub-results: on `main`, not detached, clean
working tree, `local main == origin/main`, build-info present and equal to `origin/main`, frontend
identity matches build-info, frontend `dist` present.

---

## 7. Alembic head 0019

| Surface | Reported revision |
|---------|-------------------|
| `alembic_version` table (live DB) | `0019_legacy_doc_type_canonical_enabled` |
| `GET /api/health` → `database` | `0019_legacy_doc_type_canonical_enabled` |
| `GET /api/build` → `alembic_head` | `0019_legacy_doc_type_canonical_enabled` |
| `manage_deploy.sh health` → `database_revision` | `0019_legacy_doc_type_canonical_enabled` |
| `verify-release` → `alembic` | `0019_legacy_doc_type_canonical_enabled` |
| Repository head | `0019_legacy_doc_type_canonical_enabled` |

Four independent runtime surfaces plus the repository agree. The two columns introduced by
`0018`/`0019` carry the intended DDL:

| Column | `column_default` | `is_nullable` |
|--------|------------------|---------------|
| `allow_legacy_kp_presets` | `false` | `NO` |
| `legacy_doc_type_canonical_enabled` | `false` | `NO` |

---

## 8. Settings and environment flag values

Every experimental flag is **OFF**. Values agree across `/api/build` `env_flags` /
`settings_flags` / `feature_flags`, the `deployed_capabilities` block
(`value=false`, `active=false`), `GET /api/settings`, and the `settings` table (both rows).

| Flag | Surface | Value | Active |
|------|---------|-------|--------|
| `KNOWLEDGE_OS_EXECUTIVE_ENABLED` | env | **false** | false |
| `REASONING_SERVICE_ENABLED` | env | **false** | false |
| `EVIDENCE_ASSEMBLY_ENABLED` | env | **false** | false |
| `REASONING_SPEECH_ACTS_ENABLED` | env | **false** | false |
| `enable_semantic_diagnostics_v2` | settings | **false** | false |
| `cache_namespace_v2_enabled` | settings | **false** | false |
| `memory_shadow_write_enabled` | settings | **false** | false |
| `memory_evidence_assist_enabled` | settings | **false** | false (`effective=false`) |
| `memory_canonical_shadow_enabled` | settings | **false** | false (`effective=false`) |
| `allow_legacy_kp_presets` | settings | **false** | false |
| `legacy_doc_type_canonical_enabled` | settings | **false** | false |

Release metadata on the running API:

| Field | Value |
|-------|-------|
| `release` | **0.8** |
| `release_status.accepted` | **0.8** |
| `release_status.in_progress` | `null` |
| `release_status.closed_0_6` / `closed_0_7` / `closed_0_8` | `true` / `true` / **`true`** |
| `release_status.engineering_ready` | **`true`** |
| `release_status.staging_validated` | **`false`** |
| `release_status.production_ready` | **`false`** |
| `memory_version` | 177 |
| `knowledge_version` | 26 |

`settings` table, both rows, all eleven flag columns `f` (false):

| id | knowledge_version | memory_version | all flag columns |
|----|-------------------|----------------|------------------|
| 1 | 26 | 177 | false |
| 2 | 20 | 10 | false |

Related non-experimental retrieval settings, recorded because §13 depends on them:
`enable_canonical_source_selection=true`,
`enable_news_deprioritization_for_overview_queries=true`.

**No Settings value was changed during this deployment.** No flag was enabled.

---

## 9. Smoke and golden results

`smoke` passed in Gate D stage 6 and again in the Gate E re-run:

```text
==> Smoke: http://127.0.0.1:8000
OK: GET /api/health
OK: GET /api/metrics (Prometheus)
OK: GET /api/metrics/operational
OK: GET /api/build
OK: POST /api/auth/login
OK: GET /api/settings (authenticated)
SKIP: POST /api/chat (set SMOKE_CHAT=1 to enable)
==> Golden unit parity
......................................... [100%]
OK: golden unit parity

OK: smoke passed
```

| Check | Result |
|-------|--------|
| HTTP smoke checks | **6 OK**, 1 intentional SKIP (`POST /api/chat`, gated behind `SMOKE_CHAT=1`) |
| Golden parity tests | **41 passed**, 0 failed (`test_golden_chat_parity.py`, `test_golden_queries_schema.py`) |
| `verify-release` | **VERDICT: PASS** — `PASS=15 FAIL=0 WARN=1` |

The single `verify-release` WARN is
`overview unreachable (auth may be required) — skipped corpus counts` — a pre-existing limitation
of the unauthenticated corpus probe, not a deployment fault. Corpus counts were obtained
independently by read-only SQL (§10). The skipped chat smoke was covered independently by the
authenticated chat probes in §13.

`/api/health` after deployment: `app=ok`, `ollama=ok`, `qdrant=ok`,
`database=ok (0019_legacy_doc_type_canonical_enabled)`.

---

## 10. Corpus before/after counts

Counts are identical across the entire deployment window — the pre-migration snapshot, the
post-migration snapshot, and a post-deploy read-only measurement.

| Metric | Before (`migrate release` pre) | After migration | Post-deploy (2026-07-29T07:02Z) | Delta |
|--------|-------------------------------|-----------------|----------------------------------|-------|
| sources | 5023 | 5023 | **5023** | **0** |
| chunks | 17958 | 17958 | **17958** | **0** |
| claims | 39 | 39 | **39** | **0** |
| observations (`observation_ref`) | 13 | 13 | **13** | **0** |
| evidence links (`evidence_link`) | 21 | 21 | **21** | **0** |
| `knowledge_version` | 26 | 26 | **26** | **0** |
| `memory_version` | 177 | 177 | **177** | **0** |

All values match the expected baseline recorded in the engineering acceptance report. Settings row
2 (`knowledge_version=20`, `memory_version=10`) is likewise unchanged.

---

## 11. Qdrant before/after counts

| Collection | Baseline (expected) | Post-deploy | Status | Delta |
|------------|---------------------|-------------|--------|-------|
| `site_knowledge` | 18780 | **18780** | `green` | **0** |
| `site_knowledge_answer_cache` | — | **7** | `green` | **0** across §13 probes |

Collections present: `site_knowledge`, `site_knowledge_answer_cache` — no collection was created,
dropped, or renamed. `migrate release` recorded `qdrant_touched=no`. No snapshot, no recreate, no
delete, and no upsert was issued by any gate.

The answer-cache collection held 7 points both before and after the §13 chat probes, because those
probes ran with `bypass_cache=true`; the trace confirms `semantic_answer_cache_lookup: skipped`.

---

## 12. No reindex / no Memory writes proof

### No reindex

| Evidence | Value |
|----------|-------|
| Newest `index_jobs` row | id **46**, `status=completed`, finished **2026-07-28 06:32** local |
| Relation to deployment | finished **before** Gate A (2026-07-28T20:32Z) began |
| Jobs created during deployment | **none** |
| `manage_deploy.sh health` → `index_job_status` | `completed` (identical in Gate A baseline and post-deploy) |
| Qdrant `site_knowledge` point count | unchanged at 18780 (§11) |
| Reindex / rebuild command issued | **none** |

### No Memory writes

| Evidence | Value |
|----------|-------|
| `claim` count | 39, unchanged (§10) |
| Newest `claim.created_at` | **2026-07-05 23:27:08** — 24 days before this deployment |
| `observation_ref` / `evidence_link` counts | 13 / 21, unchanged |
| `memory_version` | 177, unchanged |
| `memory_shadow_write_enabled` | **false** (§8) — the only write path into Epistemic Memory |
| `memory_evidence_assist_enabled`, `memory_canonical_shadow_enabled` | **false**, `effective=false` |

Memory write paths are gated behind `memory_shadow_write_enabled`, which is `false`. The absence of
any claim newer than 2026-07-05 is direct evidence that no write occurred, including during the
§13 chat probes.

---

## 13. Step 055 live quality findings

Three authenticated read-only chat probes were run against the deployed 0.8 runtime with
`debug=true` and `bypass_cache=true`, inspecting `trace.retrieved_chunks` (which carries
`document_type`, `is_canonical`, `excluded_as_news`, `used_in_context`). The `sources` payload does
not expose those fields, so trace inspection is required for a meaningful check.

### Recorded finding

With `legacy_doc_type_canonical_enabled=false`:

- **homepage remained rank 1 and canonical** — the `homepage` chunk ranked first at
  `final_score=0.9400` with `is_canonical=true`;
- **`news_page` chunks reached lower answer-context ranks** — two `news_page` chunks entered the
  answer context at ranks 3 and 4 (`final_score` 0.5198 and 0.4677), both `used_in_context=true`;
- **KP `deprioritized_document_types` were computed** —
  `['news_page', 'blog_page', 'promotion_page', 'action_page', 'offer_page']`, alongside
  `boosted_document_types = ['category_page', 'product_page', 'faq_page', 'documentation_page']`;
- **the legacy doc-type reorder was skipped** — the computed lists were never enforced, which is
  exactly what the flag gates;
- **`excluded_as_news` remained `false`** on every retrieved chunk in every probe;
- **the answer remained accurate** in the tested English overview query — a correct description of
  UKRSIBBANK's internet-banking services for SMEs and sole proprietors.

Observed trace for the English overview probe (`query_intent = topic_overview`):

| Rank | `document_type` | `is_canonical` | `excluded_as_news` | `used_in_context` | `final_score` |
|------|-----------------|----------------|--------------------|-------------------|---------------|
| 1 | `homepage` | **true** | false | true | 0.9400 |
| 2 | `generic_page` | false | false | true | 0.5504 |
| 3 | `news_page` | false | **false** | true | 0.5198 |
| 4 | `news_page` | false | **false** | true | 0.4677 |

### Classification

| Classification | Verdict |
|----------------|---------|
| Expected Step 055 behavior | **yes** |
| Live quality risk confirmed | **yes** |
| Deployment failure | **no** |
| Requires later validation before Staging Validated | **yes** |
| Rollback available | **yes** — set `legacy_doc_type_canonical_enabled=true` |

This is the quality risk documented and accepted at Step 055, now confirmed on the live runtime.
It is a **flag-behaviour consequence**, not a deployment defect: the deployment delivered exactly
the gated behaviour that was specified and approved.

**Rollback path:** set Settings `legacy_doc_type_canonical_enabled=true` to restore the legacy
doc-type canonical reorder. **This flag was not changed and must not be changed automatically.**
Any change requires separate operator approval.

---

## 14. Russian intent-classification gap

Recorded separately from §13 because it is a **different defect class** with a different owner.

| Probe | Query | Classified `query_intent` | KP rules applied | Retrieved | Outcome |
|-------|-------|---------------------------|------------------|-----------|---------|
| Russian overview | «Что делает компания? Дай общий обзор.» | **`specific_fact`** | none (`boosted`/`deprioritized` both `[]`) | 1 chunk, `generic_page`, score 0.4126 (an Incoterms guide) | answer plausible but thinly grounded |
| Russian news | «Какие последние новости компании?» | **`unknown`** | none | 1 chunk, `homepage` | model correctly refused: «нет информации о последних новостях» |
| English overview (control) | "Give me a general overview of what this company does." | `topic_overview` | **applied** | 4 chunks | accurate answer |

### Recorded finding

- the Russian overview query classified as **`specific_fact`**;
- the Russian news query classified as **`unknown`**;
- Russian overview/news phrasings are **not adequately covered** by current intent classification
  or Knowledge Profile patterns (`overview_query_patterns` matched nothing —
  `applied_kp.matched_patterns = []` on both Russian probes);
- this is **not caused by the Release 0.8 deployment** — intent classification and KP pattern
  coverage were untouched by Steps 052–057, and the English control query classifies correctly on
  the same runtime;
- **no fix is authorized in this task.**

Notable positive: the Russian news probe **refused rather than fabricated**, which is the intended
grounding behaviour.

### Deferred debt entry — DEBT-0.8-001

**Title:** Russian-language overview/news intent and Knowledge Profile pattern coverage

**Status:** **Deferred — not implemented. Do not begin implementation without separate approval.**

| Field | Value |
|-------|-------|
| Identifier | **DEBT-0.8-001** |
| Opened | 2026-07-29 (Release 0.8 operational deployment) |
| Class | retrieval / intent-classification quality debt |
| Caused by Release 0.8 | **no** — pre-existing |
| Blocks Engineering Ready | **no** |
| Blocks **Staging Validated** | **yes** — must be validated or explicitly waived first |
| Blocks machine migration | **no** — environment-independent |
| Evidence | §14 probe table above |
| Scope sketch (not a design) | Russian `overview_query_patterns` / intent coverage; requires its own architecture review before any code change |
| Explicitly out of scope now | code changes, Settings changes, KP edits, reindex |

Related deferred items, deliberately kept separate from `DEBT-0.8-001`:

| Item | Where recorded | Status |
|------|----------------|--------|
| `deploy full` preflight hard-block | [RELEASE-0.8-PRE-DEPLOY-PLAN.md](RELEASE-0.8-PRE-DEPLOY-PLAN.md), restated in §5 | **still deferred** |
| **DEBT-0.8-002** — `health` misreports unit state without privilege | §2 | **deferred**, operator readout only |

---

## 15. Final lifecycle classification

| Classification | Verdict |
|----------------|---------|
| **Engineering Ready** | **PASS** |
| **Deployed** | **PASS** |
| **Runtime Validated** | **PASS** |
| **Staging Validated** | **false** |
| **Production Ready** | **false** |
| **Machine Migration** | **not started** |
| **Release 0.9** | **blocked** |

### What each verdict rests on

| Verdict | Basis |
|---------|-------|
| Engineering Ready **PASS** | `engineering_ready=true`, `closed_0_8=true`, `accepted=0.8` on the running API |
| Deployed **PASS** | full identity chain aligned across `origin/main`, backend, frontend, `/api/build` (§6); Alembic at `0019` (§7); Gate D 6/6 (§2) |
| Runtime Validated **PASS** | health, `build-info`, smoke (6 checks), 41 golden parity tests, `verify-release` `PASS=15 FAIL=0` (§9); authenticated chat/retrieval probes returned grounded answers (§13) |
| Staging Validated **false** | unresolved §13 live quality risk and §14 `DEBT-0.8-001`; no staging validation gate has been executed |
| Production Ready **false** | gated behind Staging Validated |
| Machine Migration **not started** | see [POST-0.8-MACHINE-MIGRATION.md](POST-0.8-MACHINE-MIGRATION.md) |
| Release 0.9 **blocked** | blocked until machine-migration acceptance is recorded |

**This report does not promote the release.** `staging_validated` and `production_ready` remain
`false` in repository metadata and on the running API, and this deployment did **not** change them.

### Explicit non-actions during this deployment

- No Settings value changed; no flag enabled.
- No reindex; no Qdrant snapshot, delete, recreate, or upsert.
- No Memory write; `memory_shadow_write_enabled` stayed `false`.
- No second deployment; no emergency override used.
- `ai_site_agent_recovery` untouched.
- Machine migration not started; Release 0.9 not started.
- `DEBT-0.8-001` and `DEBT-0.8-002` recorded only — neither implemented.

### Next approved program

**Post-0.8 machine / environment migration** — architecture review first, execution only after
that review is approved. Release **0.9** planning remains blocked until machine-migration
acceptance is recorded.

---

## Evidence index

| Artifact | Path |
|----------|------|
| Gate A baseline (`health`) | `/opt/ai-site-agent/logs/deploy-20260728_233233.log` |
| Gate B backup | `/opt/ai-site-agent/logs/deploy-20260728_233243.log` |
| Gate C `migrate release` report | `/opt/ai-site-agent/logs/migrate-release-20260729_002022.log` |
| Gate D deploy logs | `/opt/ai-site-agent/logs/deploy-20260729_095751.log`, `…_095812.log`, `…_095825.log`, `…_095839.log` |
| Gate D deployment manifest | `/opt/ai-site-agent/deployments/20260729_065838-39ebef1.json` |
| Deployed build identity | `/opt/ai-site-agent/.build-info.json` |
| Deployed frontend identity | `/opt/ai-site-agent/dashboard/dist/.deploy-identity.json` |
| Backups | `/opt/ai-site-agent/backups/ai_site_agent.2026072{8_233243,9_001833,9_095751}.dump` |

---

## Sign-off (fill at review time)

| Role | Name | Date |
|------|------|------|
| Ops lead | | |
| Engineering | | |
| Deployment acceptance | | |
