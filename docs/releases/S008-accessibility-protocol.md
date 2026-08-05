# S008 — Accessibility Pass Protocol

```
Program: docs/releases/1.0-rfc-101-master-program.md
Package IDs: G9-P3
Inventory findings: A15.1
Execution Strategy: docs/releases/1.0-rfc-101-execution-strategy.md
```

**Step:** S008
**Authority:** `docs/releases/S008-implementation-package.md`
**Status:** **Protocol only.** This document defines a repeatable accessibility checklist for the final RFC-101 screen set. It does **not** claim an automated scan or manual audit has been run. Execution (running an axe/Lighthouse-style scan, or a manual keyboard/screen-reader pass) is a separate, later, explicitly authorized task.

---

## 1. Purpose

Inventory finding A15.1 ("No durable a11y audit evidence for Dashboard") and `RFC-PRODUCT-READINESS.md`'s quality bar require accessibility evidence (or declared debt) for primary journeys before the screens they cover can claim Gate PASS on the Accessibility gate (Master Program §9). This protocol is the fixed checklist for that evidence.

## 2. Scope — screens covered

Every canonical Mode-off product screen plus the six Engineering destinations (Mode-on):

| Area | Screens |
|------|---------|
| Product | Home, Library, Update, Site, Ask, Performance, Activity, General, Models, Answers, Access |
| Engineering (Mode on) | Status, Ask details, Knowledge, Tensions, Advanced, Build |

Legacy redirect-only pages (`/overview`, `/chat`, `/users`, `/analytics`, `/logs`, `/sources`, `/indexing`, `/knowledge-profile`) render no content of their own (pure client-side `Navigate`) and are out of scope for this checklist — there is nothing to audit on a screen that never paints.

## 3. Checklist dimensions

For each screen listed in §2, a future execution pass must record pass/fail plus notes for each dimension below.

### 3.1 Keyboard

- [ ] Every interactive element (button, link, form field, tab, menu item) is reachable via `Tab`/`Shift+Tab` in a logical order
- [ ] No keyboard trap — focus can always leave a modal/drawer via `Esc` or a reachable close control
- [ ] Primary CTA on the screen is reachable and activatable (`Enter`/`Space`) without a mouse
- [ ] Visible focus indicator is present on every focusable element (not suppressed by CSS)

### 3.2 Labels

- [ ] Every form input has an associated, programmatically-linked label (`<label for>`, `aria-label`, or `aria-labelledby`) — not placeholder text alone
- [ ] Every icon-only button has an accessible name (`aria-label` or visually-hidden text)
- [ ] Every image conveying information has appropriate `alt` text; purely decorative images are marked so assistive tech skips them
- [ ] Page/section headings use a logical, non-skipping heading hierarchy

### 3.3 Contrast

- [ ] Body text meets at least WCAG AA contrast (4.5:1) against its background in both the app's light theme states
- [ ] Large text / headings meet at least AA contrast for large text (3:1)
- [ ] State-only color cues (error red, success green, status badges) are paired with a non-color signal (icon, text label) — not color alone
- [ ] Focus indicators themselves meet at least 3:1 contrast against adjacent colors

## 4. Per-role notes

- `viewer` role: verify read-only screens do not expose disabled-but-focusable controls without an explanation (disabled controls should either be skipped by tab order or have an accessible reason)
- `admin`/`operator`: verify destructive actions (delete/reindex-all/etc.) have an accessible confirmation step, not just a visual one

## 5. Recording results

A future execution task must attach, per screen in §2:

- Pass/fail per dimension in §3
- Tool used (manual keyboard walkthrough, screen reader, automated scanner) and version
- Any declared debt for a failing item, filed in `docs/releases/1.0-rfc-101-product-debt-register.md` per Product Readiness debt policy (class `accepted` or `must_resolve_before_1_0_acceptance` as appropriate)
- Reviewer identity/date
- Link back to this protocol document

No result table is pre-filled in this document. Declaring a claimed PASS without an actual run would be a false Gate PASS, which the Master Program's risk model (§10) explicitly forbids.

## 6. Relationship to Product Readiness Gate

This protocol satisfies the **protocol-authoring** half of package `G9-P3`. The **execution** half (per-screen a11y evidence or declared debt) remains open per screen until a later, separately authorized execution task runs this checklist and records results. `docs/releases/S008-product-readiness-gate.md` records this distinction explicitly.
