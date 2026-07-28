# Demo readiness — Knowledge OS product surface

**Date:** 2026-07-28  
**Scope:** Presentation polish + Epistemic Health honesty. **No RFC step advance.**  
**Release 0.6:** not closed.

## Confirmations

1. **No test data was deleted.** Cleanup tooling is dry-run only (`scripts/recovery/cleanup_epistemic_test_rows.py`).
2. **Chat / retrieval / prompts / LLM behavior were not changed.** Chat UI only shows sources loading more clearly; migration diagnostics remain in the engineering drawer.
3. **Migration flags were not enabled.** Shadow write remains OFF.
4. **Step 045 was not deployed** by this work. `/api/build` reports per-process `deployed_capabilities.supported`.
5. **Qdrant / reindex / corpus** untouched.

## What changed

### Backend
- Provenance scope model (`real` | `test` | `all`) for Epistemic Memory / Tension Surfacing
- `GET /api/understanding/tensions?provenance_scope=` (default **`real`**)
- `GET /api/understanding/summary` (+ `/api/epistemic-health/*` aliases)
- Honest `GET /api/build`: `APP_RELEASE=0.5`, `release_status`, `deployed_capabilities`
- Sources list: `exclude_fixtures=true` by default

### Dashboard
- Nav: **Diagnostics → Epistemic Health** (experimental); Chat Diagnostics → Chat
- Redirect `/understanding` → `/diagnostics/epistemic-health`
- Epistemic Health page: summary cards, provenance filters, maturity, architecture visual
- Overview: Knowledge OS panel (live APIs)
- Settings: Migration flags & deploy identity panel
- EN + UK localization

### Tooling / docs
- `scripts/recovery/audit_epistemic_test_rows.py`
- `scripts/recovery/cleanup_epistemic_test_rows.py` (dry-run default)
- `scripts/recovery/EPISTEMIC_TEST_CLEANUP.md`
- Audit + dry-run reports under `scripts/recovery/reports/`
- This package + [DEMO-SCRIPT.md](DEMO-SCRIPT.md)

## Navigation before / after

| Before | After |
|--------|--------|
| Understanding | Diagnostics → Epistemic Health (experimental) |
| (none) | Diagnostics → Chat Diagnostics → `/chat` |

## Overview statistics (live APIs)

Sources, chunks, vectors, SI coverage, health, analytics, build release / memory_version / knowledge_version, real open tensions (admin). **No hardcoded corpus counts.**

## Epistemic Health behavior

- Default view: **real** provenance only
- Real operational summary from `/summary`
- Test counts in a secondary section
- Tensions are hypotheses; chat impact **not active**
- Empty real state when only test fixtures exist (current recovery DB: **0 real tensions**, 27 test)

## Real / test filtering

Server-side `provenance_scope`. Client type filter (support_deficit / conflict) applies after fetch for the selected scope.

## Maturity representation

Statuses only: Active / Available behind flag / Experimental / Diagnostic-only / Not active / Planned. **No fake %.**

## Feature-flag / deployment status

Settings panel reads `/api/build`. Unsupported flags show “Not deployed” (e.g. Step 045 speech-acts on older `/opt`).

## Localization

EN + UK for Epistemic Health, Overview KOS, maturity, architecture, migration flags, nav.

## Cleanup dry-run (recovery DB snapshot)

From `scripts/recovery/reports/epistemic_cleanup_dry_run.json`:

| | Before | Would delete | After projected |
|--|--------|--------------|-----------------|
| claims | 39 | 33 test | 6 (SI) |
| evidence_links | 21 | 15 | 6 |
| observation_refs | 13 | 10 | 3 |
| SI claims | 6 | 0 | 6 |

**Execute requires separate explicit approval.**

## Known limitations

- Epistemic Memory does not influence chat answers
- Shadow write OFF — few real SI claims (6)
- Most tensions are test fixtures until cleanup is approved
- Release 0.6 not closed; Step 045 may be repo-only
- Automated screenshot workflow not in-repo (use browser review after deploy of this branch)

## Next roadmap milestone (not implemented here)

Release **0.7** — memory-assisted evidence (`memory_evidence_assist_enabled`) — first Memory→answer coupling.
