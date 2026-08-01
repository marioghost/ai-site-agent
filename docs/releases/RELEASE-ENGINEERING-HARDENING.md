# Release Engineering Hardening — Milestone Report

**Status:** Engineering infrastructure only (not an RFC step; not Release 0.8)  
**Date:** 2026-07-28  
**Branch:** `chore/release-engineering-hardening`

## Purpose

Make `main → origin/main → build → /opt → /api/build` share one git commit, and make incorrect deploys fail closed.

## Architecture summary

| Layer | Role |
|-------|------|
| `deploy/manage_deploy.sh` | **Single public entry** (CLI + menu) |
| `deploy/lib/deploy_source.sh` | **One Command** orchestrator (`deploy full`) |
| `deploy/lib/migration_decision.sh` | Internal schema-first vs post-sync-only decision |
| `deploy/lib/verify_release.sh` | Shared verify-release core (deploy gate + CLI) |
| `deploy/lib/manifest.sh` | Deployment report (SUCCESS/FAILED) under `deployments/` |
| `deploy/lib/deploy_guard.sh` | Hard refusals + emergency mode |
| `deploy/lib/cli.sh` | `release` / `deploy` / diagnostics / recovery |
| `scripts/release/write-build-info.sh` | Auto build identity (never hand-edit) |
| `dashboard/dist/.deploy-identity.json` | Frontend commit stamp |
| `scripts/release/verify-release.sh` | Thin wrapper over shared verify core |

Product paths (chat, Memory, Reasoning, Language, Retrieval, Qdrant, flags) are untouched.

**Normal release command (only):**

```bash
sudo bash deploy/manage_deploy.sh deploy full
```

Standalone `migrate release`, `verify-release`, `smoke`, `health`, `build-info` are diagnostics/recovery — not required normal-release stages.

## Script classification

| Script | Classification | Notes |
|--------|----------------|-------|
| `deploy/manage_deploy.sh` | **KEEP** | Canonical entry |
| `deploy/lib/*` | **KEEP** | Shared libs |
| `deploy/deploy_from_main.sh` | **DEPRECATED wrapper** | → `deploy full` |
| `deploy/sync_to_opt.sh` | **DEPRECATED wrapper** | → `deploy full` |
| `scripts/deploy.sh` | **DEPRECATED wrapper** | → `deploy full` |
| `scripts/smoke.sh` | **DEPRECATED wrapper** | → `smoke` |
| `scripts/deploy-and-smoke.sh` | **DEPRECATED wrapper** | → deploy + smoke |
| `scripts/release/deploy-staging.sh` | **DEPRECATED wrapper** | → `deploy full` |
| `scripts/release/verify-release.sh` | **KEEP** | New verifier |
| `scripts/release/write-build-info.sh` | **KEEP** | Enhanced identity |
| `scripts/release/smoke-staging.sh` | **KEEP** | Smoke impl |
| `scripts/release/test-*.sh` | **KEEP** | Gates |
| `deploy/install_*.sh`, `prepare_staging.sh` | **KEEP** | Bootstrap / emergency staging |
| `scripts/start-dev.sh`, `run_*.sh` | **DEV-ONLY** | Local dev |
| `scripts/run_postgres_migration_once.sh` | **DEPRECATED** | Historical cutover |

## Bypasses removed (normal path)

- `ALLOW_DIRTY_SYNC=1` → refused (emergency only)  
- `DEPLOY_LOCAL_MAIN=1` → refused (emergency only)  
- `--mode update` → hard error  
- `--no-backup-db` on release deploy → hard error  
- Interactive menu items 1–3 → `origin/main` deploy only  
- Direct `--sync-from-dev` from operator checkout → refused unless `MD_RELEASE_DEPLOY=1` or emergency  

## Release identity

Deploy derives release from tip `APP_RELEASE` and validates it against `.build-info.json` / frontend identity / `/api/build`.  
If configured `RELEASE_VERSION` differs, deploy **warns and ignores** it (never deploys under the stale configured label).  
If an exact git tag (`v0.7` / `release-0.7` / `0.7`) exists on the commit, it must match tip `APP_RELEASE`.

## Single entrypoint

Future deploy/release-engineering features belong in `manage_deploy.sh` only.
No new standalone deployment scripts except bootstrap/recovery utilities.

## Validation commands

```bash
bash scripts/release/test-deploy-guard.sh
bash scripts/release/test-manage-deploy-cli.sh
bash deploy/manage_deploy.sh help
bash deploy/manage_deploy.sh verify-release   # after a real deploy + running API
```
