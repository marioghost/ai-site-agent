# Architecture Decision Records (ADR)

Per `docs/DEVELOPMENT_CHARTER.md`, architectural changes require an ADR **before** implementation.

## When to write an ADR

Write an ADR when a change:

- Adds, removes, or merges a **subsystem**
- Changes **ownership** of epistemic state, events, or public APIs
- Introduces a new **cognitive or engineering concept** (rare — architecture is frozen)
- Deprecates a production path relied on by customers
- Cannot be executed within an existing RFC-100 step without reinterpretation

Do **not** write an ADR for:

- Routine bug fixes inside a subsystem
- RFC-100 steps executed as specified
- Tests, observability, copy, or docs that don't change boundaries

## Numbering

- `0001`, `0002`, … sequential
- Filename: `NNNN-short-kebab-title.md`
- Never reuse numbers; supersede with a new ADR that references the old one

## Status values

- **Proposed** — under review, no code yet
- **Accepted** — approved for implementation
- **Implemented** — shipped; link PR/release
- **Superseded** — replaced by ADR-XXXX
- **Rejected** — decided not to do; keep for history

## Template

Copy `0000-template.md` when creating a new ADR.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-shadow-observation-key-per-source.md) | Shadow observation identity keyed per source | Accepted |
| [0002](0002-tension-taxonomy-ownership.md) | Tension taxonomy ownership | Accepted |
| [0003](0003-bypass-answer-cache-when-memory-assist.md) | Bypass answer cache when Memory evidence assist is effective | Implemented |
| [0004](0004-exclude-legacy-boosts-from-cache-namespace.md) | Exclude legacy boost fields from cache namespace hash | Implemented |

*Update this table when ADRs are added.*
