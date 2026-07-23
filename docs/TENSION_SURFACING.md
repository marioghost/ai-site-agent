# Tension surfacing (Release 0.5 — Step 034)

**RFC-100 Step 034** — read-only detection from Epistemic Memory. No persistence, no API, no dashboard.

## Purpose

`TensionSurfacingService` scans active claims via `EpistemicMemoryService` and returns in-memory `TensionView` DTOs. This is the v1 subset of [Epistemic Maintenance](../KNOWLEDGE_OS_ARCHITECTURE_v1.md) tension detection — detection only, not agenda or investigation.

## Tension types (v1)

| Type | Code | Detection rule (conservative) |
|------|------|--------------------------------|
| Support deficit | `support_deficit` | Active claim with **no** evidence link `role=support` |
| Conflict | `conflict` | Explicit `role=conflict` evidence on a claim, **or** same observation has `support` for claim A and `conflict` for claim B (A ≠ B) |

## What is NOT detected (limitations)

- Semantic / NLP contradiction between propositions
- Conflicts inferred from confidence scores alone
- Superseded or inactive claims (`superseded_by_id` set)
- Gaps, ignorance records, belief-state tensions
- Cross-source conflict without explicit conflict evidence role
- Persisted tension store (no DB writes)

Prefer **false negatives over false positives**.

## API

```python
from app.services.epistemic_memory import EpistemicMemoryService
from app.services.tension_surfacing import TensionSurfacingService

memory = EpistemicMemoryService(db)
tensions = TensionSurfacingService(memory).surface_tensions()
```

Returns `list[TensionView]` — frozen dataclass with `tension_type`, `claim_ids`, `observation_ref_ids`, `evidence_link_ids`, `summary`.

## Ownership

| Concern | Owner |
|---------|--------|
| Epistemic reads | `EpistemicMemoryService` |
| Tension detection | `TensionSurfacingService` |
| Persistence | **Not implemented** (Step 035+ API may expose in-memory results) |

## Explicit non-goals (Step 034)

- No chat / retrieval / Executive / cache changes
- No dashboard (Step 036)
- No maintenance execution or investigation planning
- No feature flag wiring to production paths

## Tests

```bash
cd backend && .venv/bin/pytest tests/test_tension_surfacing_service.py -m unit -v
```

## Next steps (RFC-100)

- **035** — `GET /api/understanding/tensions` (read-only, admin)
- **036** — Dashboard panel
- **037** — Metrics gauges
