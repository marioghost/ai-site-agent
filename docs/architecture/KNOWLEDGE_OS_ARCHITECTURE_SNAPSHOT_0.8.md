# Knowledge OS Architecture Snapshot — Release 0.8 (post–Step 057 engineering closure)

| Field | Value |
|-------|-------|
| **Status** | Official engineering baseline (Release 0.8 Engineering Ready) |
| **Scope** | Release 0.7 baseline + Steps 052–057 |
| **Date** | 2026-07-28 |
| **App release marker** | `APP_RELEASE = "0.8"`; `closed_0_8: true` |
| **Alembic head (code)** | `0019_legacy_doc_type_canonical_enabled` |
| **Staging validated** | **false** |
| **Production ready** | **false** |
| **Prior snapshot** | [KNOWLEDGE_OS_ARCHITECTURE_SNAPSHOT_0.7.md](KNOWLEDGE_OS_ARCHITECTURE_SNAPSHOT_0.7.md) |
| **Rule** | Describes **implemented** behaviour. Live DB may lag until approved deploy applies 0018/0019. |

---

## Delta from Release 0.7

| Area | 0.7 | 0.8 |
|------|-----|-----|
| Settings boost API fields | Present on API | **Removed** from API (ORM retained) — Step 052 |
| Dashboard boost inputs | Present | **Removed** — Step 053 |
| KP industry preset APIs | Available (deprecation path) | Default **410** via `allow_legacy_kp_presets=false` — Step 054 |
| Doc-type CanonicalSourceService reorder | Always available when canonical selection on | Gated by `legacy_doc_type_canonical_enabled` (default **false**) — Step 055 |
| Golden CI profile | Declared generic; loader did not enforce | Fail-closed `fixture_profile=generic_corporate` — Step 056 |
| Memory Assist / Shadow | Default OFF | **Unchanged** default OFF |
| Memory authority | Not implemented | **Still not implemented** |

---

## Known quality risk

Step 055 default-off may yield overview candidate order **news → about → homepage**. Rollback: Settings `legacy_doc_type_canonical_enabled=true`. See acceptance report.

---

## Capability vocabulary

`code_present` ≠ `configured` ≠ `enabled` ≠ `effective` ≠ `deployed` ≠ `staging_validated`.

Live `/api/build` updates only after deploy + restart via `bash deploy/manage_deploy.sh` (public operator entry point).

## Post-0.8 governance

Do **not** start Release 0.9 until approved 0.8 deploy + [POST-0.8-MACHINE-MIGRATION.md](../operations/POST-0.8-MACHINE-MIGRATION.md) acceptance.

---

## References

- [RELEASE-0.8-ACCEPTANCE-REPORT.md](../releases/RELEASE-0.8-ACCEPTANCE-REPORT.md)
- [0.8-rollback.md](../releases/0.8-rollback.md)
- [FEATURE_FLAGS.md](../FEATURE_FLAGS.md)
- [POST-0.8-MACHINE-MIGRATION.md](../operations/POST-0.8-MACHINE-MIGRATION.md)
