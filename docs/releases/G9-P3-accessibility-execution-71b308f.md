# G9-P3 Accessibility Execution Evidence — Release 1.0 tip `71b308f`

**Date:** 2026-08-07  
**Reviewer:** Principal AI Architect / Release Manager  
**Protocol:** `docs/releases/S008-accessibility-protocol.md`  
**Runtime tip:** `71b308f` (pre-fix baseline) + Field/`ActivityScreen` a11y hardening in acceptance close  
**Tool:** Playwright live walkthrough + DOM accessibility probe (labels / skip link / headings)

## Scope covered (Mode-off product screens)

Home, Library, Update, Site, Ask, Performance, Activity, General, Models, Answers, Access.

Engineering Mode-on destinations were not required for Accepted Product Mode-off claim; Mode-off isolation was verified (no Eng nav; Eng URLs blocked).

## Dimensions

### Keyboard / focus landmarks

| Check | Result |
|-------|--------|
| Skip-to-main-content link present on all product screens probed | PASS |
| Primary CTAs named (buttons/links with text or aria-label) | PASS on Home/Ask/Answers/Access/Update/Performance/General |
| Focusable Login / Ask composer labeled | PASS (`Username`, `Password`, `Chat message`) |

### Labels

| Check | Result |
|-------|--------|
| `Field` associates visible label with control via `htmlFor`/`id` | PASS after acceptance fix (`dashboard/src/ui/components/Input.tsx`) |
| Activity source links always expose accessible name | PASS after acceptance fix (`ActivityScreen` + `activity.source_link` i18n) |
| Answers presets are named buttons (not icon-only) | PASS |

### Contrast / non-color cues

| Check | Result |
|-------|--------|
| Status uses text labels (Ready / Needs attention / In progress), not color alone | PASS (Home) |
| Light theme default operable | PASS |

## Declared accepted residual (not must-resolve)

- Some Site profile textareas may still rely on section headings rather than per-field `htmlFor` when not wrapped in `Field` — residual polish for Release 1.1.
- Engineering Mode-on six-screen deep a11y scan deferred with Mode-on optional cold demo (protocol §5) — accepted residual; Mode-off Accepted Product path is primary.

## Verdict

**G9-P3 execution: PASS WITH ACCEPTED RESIDUAL** for Mode-off primary journeys on the Release 1.0 acceptance tip after Field/Activity hardening.
