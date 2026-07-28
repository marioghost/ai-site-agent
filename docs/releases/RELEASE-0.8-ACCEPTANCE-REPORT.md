# Release 0.8 — Engineering Acceptance Report

**Date:** 2026-07-28  
**RFC:** RFC-100 Production Migration Strategy  
**Closure step:** Step 057  
**Architecture review:** `docs/releases/0.8-step-057-architecture-review.md`  
**Baseline tip (pre-closure merge):** `9387c303b1eb9dbeb8b32902670afb27860d65d6`

---

## 1. Executive summary

Release 0.8 delivers **legacy surface cleanup**: Settings API and dashboard boost field removal, Knowledge Profile industry preset APIs default-disabled (HTTP 410), legacy document-type canonical reorder gated behind a Settings flag (default OFF), and CI golden fail-closed on `fixture_profile=generic_corporate`.

**Engineering Ready: PASS.** Staging Validated: **false**. Production Ready: **false**.  
Migrations **0018/0019** exist in code; they are **not** claimed applied to live `ai_site_agent`. No deploy was performed as part of this closure.

---

## 2. Lifecycle state

| Classification | Verdict |
|----------------|---------|
| **Engineering Ready** | **PASS** |
| **Staging Validated** | **false** |
| **Production Ready** | **false** |
| Deployment | **not executed** |
| Migrations 0018/0019 on `ai_site_agent` | **not applied** (this closure) |
| Machine migration | **planned, not executed** |

Repository metadata: `APP_RELEASE="0.8"`, `accepted="0.8"`, `closed_0_8=true`, `engineering_ready=true`, `staging_validated=false`, `production_ready=false`, `in_progress=null`.

---

## 3. Commit inventory (Steps 052–056 anchors)

| Step | Feature | Feature merge | Docs merge (if any) |
|------|---------|---------------|---------------------|
| 052 | `6d3444e` | `290d5d8` | `1ffac43` |
| 053 | `e7f519e` | `f18f4e7` | — |
| 054 | `eb4b043` | `b550b4b` | `570facc` |
| 055 | `5c10f58` | `76ad58a` | `2ae8561` |
| 056 | `7c6a5ff` | `a03e6d6` | `9215d92` |
| 057 review | `822d0aa` | `9387c30` | — |

Full tip before this closure commit: **`9387c30`**.

---

## 4. Steps 052–056 deliverables

| Step | Deliverable |
|------|-------------|
| **052** | Removed five boost fields from Settings API (`SettingsRead`/`SettingsUpdate`); ORM columns retained for scorer/cache |
| **053** | Removed boost controls from dashboard types, presets UI, i18n/help |
| **054** | `allow_legacy_kp_presets` default **false** (migration **0018**); preset GET/POST → **410**; dashboard 410 UX |
| **055** | `legacy_doc_type_canonical_enabled` default **false** (migration **0019**); RPS finalize skips doc-type reorder when false |
| **056** | `load_golden_smoke()` requires `fixture_profile=="generic_corporate"`; schema defense in depth; CI script updated |
| **057** | This engineering closure |

---

## 5. Migration chain through 0019

```text
0017_memory_canonical_shadow_enabled
  → 0018_allow_legacy_kp_presets
  → 0019_legacy_doc_type_canonical_enabled   ← code Alembic head
```

| Claim | Status |
|-------|--------|
| Exactly one Alembic head in repo | **0019_legacy_doc_type_canonical_enabled** |
| Applied to live `ai_site_agent` in this closure | **No** |
| Steps 052 / 053 / 056 | No migration |

---

## 6. Feature-flag defaults

| Flag | Default | Closure expectation |
|------|---------|---------------------|
| `allow_legacy_kp_presets` | **false** | Remain false for normal 0.8 ops |
| `legacy_doc_type_canonical_enabled` | **false** | Remain false unless ops rollback for overview quality |
| `memory_evidence_assist_enabled` | false | **OFF** |
| `memory_canonical_shadow_enabled` | false | **OFF** |
| `cache_namespace_v2_enabled` | false | Unchanged |
| Reasoning / EA / Executive / speech-act env flags | false | Unchanged |

Distinguish carefully:

| Term | Meaning |
|------|---------|
| `code_present` | Feature exists in this repository revision |
| `configured` / Settings value | What the running DB row says (requires migration applied + deploy) |
| `enabled` | Flag value true |
| `effective` / `active` | Flag true **and** prerequisites met |
| `deployed` | Process actually serving the closed code (`/api/build` after deploy+restart) |
| `staging_validated` | Ops gate — **false** here |

---

## 7. Runtime changes

1. **Settings API boost fields removed** (052) — clients no longer read/write five boost fields via API.  
2. **Dashboard boost controls removed** (053).  
3. **Preset API 410 by default** (054) when `allow_legacy_kp_presets=false`.  
4. **Legacy doc-type canonical path disabled by default** (055).  
5. **Generic-only CI golden enforcement** (056) — production Knowledge Profiles unaffected.

---

## 8. Explicitly unchanged

- Memory **authority** selector — **not implemented**
- Memory Assist / Canonical Shadow — remain default **OFF**; no chat influence under defaults
- **DocumentScorer** boost column reads — unchanged (ORM retained)
- Qdrant / corpus content — **not mutated** by engineering closure
- Ollama / indexing pipelines — unchanged by this step

---

## 9. Known Step 055 overview / news quality risk

With `legacy_doc_type_canonical_enabled=false`, overview-style pools that previously demoted news via doc-type reorder may retain order such as **news → about → homepage**.

| Item | Detail |
|------|--------|
| Expected | Intentional default of Option A |
| Risk | Overview answers may cite news more often on live corpus |
| Mitigation | Settings PUT `legacy_doc_type_canonical_enabled=true` |
| Golden CI | Mocked fixtures did not show serious unit regression |
| Staging | Must evaluate on real corpus before Production Ready |

**This risk is accepted for Engineering Ready and is not hidden.**

---

## 10. Rollback plan

See [0.8-rollback.md](0.8-rollback.md).

- Level 1: Settings flags (`allow_legacy_kp_presets=true`, `legacy_doc_type_canonical_enabled=true`)
- Level 2: place known-good tip on `origin/main`, then  
  `sudo bash deploy/manage_deploy.sh deploy full` → `bash deploy/manage_deploy.sh verify-release`  
  (CLI deploys **only** from `origin/main` clean worktree; no arbitrary-commit flag)
- Level 3: schema downgrade only under explicit ops approval (normally unnecessary)

Do **not** use `ai_site_agent_recovery` as feature rollback. Do **not** clear Qdrant or reindex merely to roll back 0.8 behavior. Do **not** use emergency deploy overrides for routine rollback.

---

## 11. Test results (closure validation)

| Suite | Result |
|-------|--------|
| Step 052 settings boost API tests | PASS (run at closure) |
| Step 053 dashboard (vitest / TS / production build via release-check) | PASS |
| Step 054 preset 410 tests | PASS |
| Step 055 legacy doc-type canonical tests | PASS |
| Step 056 golden loader + schema + parity | PASS |
| Build-info / release metadata tests | PASS |
| Golden `test-golden.sh` | PASS |
| `make release-check` | PASS |
| Migrations applied to `ai_site_agent` | **Not performed** |
| Live Settings / Qdrant / corpus writes | **None** |

---

## 12. Engineering Ready verdict

**PASS** — Steps 052–057 engineering deliverables complete in repository; `make release-check` green; metadata records `closed_0_8=true`.

---

## 13. Staging Validated = false

No approved Release 0.8 deploy, no live 0018/0019 apply proof, no live overview quality certification in this closure.

---

## 14. Production Ready = false

Blocked on Staging Validated and broader ops production criteria.

---

## 15. Deploy / migration plan (separate ops action)

Documented in [0.8-step-057-release-closure.md](0.8-step-057-release-closure.md), [RELEASE-0.8-PRE-DEPLOY-PLAN.md](../operations/RELEASE-0.8-PRE-DEPLOY-PLAN.md), and [RELEASE-CHECKLIST.md](RELEASE-CHECKLIST.md). **Not executed here.**

**HARD SAFETY:** Do **not** run `deploy full` until `migrate release` exits successfully and proves repository head **0019**, live DB post revision **0019**, and both new Settings columns. If not: **STOP. Do not deploy.**

Canonical Release 0.8 sequence (identical everywhere):

```text
status → backup db → migrate release → verify schema head
→ deploy full → health → build-info → smoke → verify-release
```

```bash
bash deploy/manage_deploy.sh status
bash deploy/manage_deploy.sh backup db
bash deploy/manage_deploy.sh migrate release
sudo bash deploy/manage_deploy.sh deploy full
bash deploy/manage_deploy.sh health
bash deploy/manage_deploy.sh build-info
bash deploy/manage_deploy.sh smoke
bash deploy/manage_deploy.sh verify-release
```

| Command | Role |
|---------|------|
| `migrate` / `migrate live` | `/opt` tree only — **not** schema-first; insufficient while `/opt` lacks 0018/0019 |
| `migrate release` | **Only** supported schema-first path (origin/main worktree → live DB) |
| `deploy full` inner `run_migrations` | Post-sync idempotent defense-in-depth (expected no-op after successful `migrate release`) |

Do **not** use `deploy full` → bare `migrate`. Do **not** skip `migrate release` when `/opt` does not yet contain the required migration files.

Live `/api/build` may remain stale until approved deploy + backend restart.

---

## 16. Post-release machine migration task

Planning only: [docs/operations/POST-0.8-MACHINE-MIGRATION.md](../operations/POST-0.8-MACHINE-MIGRATION.md). **Not executed.**

**Governance:** After approved Release 0.8 deployment + runtime validation, the next priority is machine migration. Do **not** begin Release **0.9** or other new product functionality until machine-migration acceptance.

---

## 17. Corpus / Qdrant expected baseline (from latest accepted operational report)

Engineering closure is **data-neutral**. Final before/after proof belongs to the later deployment gate. Do not treat the table below as a live query performed during this closure.

| Metric | Expected baseline (reported) |
|--------|------------------------------|
| sources | 5023 |
| chunks | 17958 |
| claims | 39 |
| observations | 13 |
| evidence links | 21 |
| knowledge_version | 26 |
| memory_version | 177 |
| fixture.example sources | 0 |
| Qdrant `site_knowledge` | 18780 |

---

## 18. Release decision

| Classification | Verdict |
|----------------|---------|
| **Engineering Ready** | **PASS** |
| **Staging Validated** | **false** |
| **Production Ready** | **false** |
| **Deployment** | not executed |
| **Migrations 0018/0019 live** | not applied |
| **Machine migration** | planned, not executed |

**Release 0.8 engineering closure: ACCEPTED** in repository metadata (`closed_0_8=true`).

---

## References

- [0.8-rollback.md](0.8-rollback.md)
- [0.8-step-057-architecture-review.md](0.8-step-057-architecture-review.md)
- [0.8-step-057-release-closure.md](0.8-step-057-release-closure.md)
- [FEATURE_FLAGS.md](../FEATURE_FLAGS.md)
- [POST-0.8-MACHINE-MIGRATION.md](../operations/POST-0.8-MACHINE-MIGRATION.md)
- [KNOWLEDGE_OS_ARCHITECTURE_SNAPSHOT_0.8.md](../architecture/KNOWLEDGE_OS_ARCHITECTURE_SNAPSHOT_0.8.md)
