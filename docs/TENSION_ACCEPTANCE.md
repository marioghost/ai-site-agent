# Tension Surfacing — Cognitive Acceptance Suite

**RFC-100** — validate epistemic behavior before dashboard exposure (pre–Step 036).  
**Scope:** `TensionSurfacingService` detection rules only. No new tension types, no persistence, no service redesign.

## Semantic reminder

A **Tension** is an **epistemic hypothesis** — not knowledge, not a belief, not a fact.  
Acceptance checks that hypotheses are surfaced (and *not* surfaced) exactly as the conservative rules intend.

## How to run

```bash
cd backend && .venv/bin/pytest \
  tests/test_tension_surfacing_service.py \
  tests/test_tension_acceptance.py \
  -m unit -v
```

## Scenario matrix

| ID | Scenario | Expected tensions | Covered by |
|----|----------|-------------------|------------|
| T-01 | Empty memory | none | `test_acc_empty_memory` |
| T-02 | No tensions (supported claim only) | none for that claim | `test_no_support_deficit_when_support_link_exists` |
| T-03 | Support deficit | `support_deficit` for claim | `test_support_deficit_detected_for_claim_without_support` |
| T-04 | Explicit cross-claim conflict | one `conflict` spanning A+B | `test_cross_claim_conflict_explicit_via_evidence_roles` |
| T-05 | Superseded claims ignored | superseded ID never appears | `test_superseded_claims_ignored` |
| T-06 | Multiple supporting observations | no `support_deficit` | `test_acc_multiple_supporting_observations` |
| T-07 | Mixed support + conflict (same claim) | `conflict` only (no deficit) | `test_acc_mixed_support_and_conflict_same_claim` |
| T-08 | Duplicated conflict evidence | single `conflict` (deduped) | `test_acc_duplicated_conflict_evidence_deduped` |
| T-09 | Intra-claim conflict without support | `support_deficit` + `conflict` | `test_acc_intra_claim_conflict_without_support` |

---

### T-01 — Empty memory

| | |
|--|--|
| **Memory state** | No claims, no observations, no evidence links |
| **Expected tensions** | `[]` |
| **Expected non-tensions** | Any tension of any type |
| **Rationale** | No active claims → nothing to hypothesize about |
| **Test** | `tests/test_tension_acceptance.py::test_acc_empty_memory` |

---

### T-02 — No tensions (supported claim only)

| | |
|--|--|
| **Memory state** | One active claim with ≥1 `role=support` evidence link |
| **Expected tensions** | No `support_deficit` involving that claim; no `conflict` |
| **Expected non-tensions** | Support deficit for a well-supported claim |
| **Rationale** | Presence of support satisfies the deficit rule; no conflict role → no conflict hypothesis |
| **Test** | `tests/test_tension_surfacing_service.py::test_no_support_deficit_when_support_link_exists` |

---

### T-03 — Support deficit

| | |
|--|--|
| **Memory state** | Active claim with **zero** `role=support` links |
| **Expected tensions** | One `support_deficit` for that claim |
| **Expected non-tensions** | Treating the claim as confirmed knowledge; inventing conflicts |
| **Rationale** | Conservative: missing support is a possible problem signal |
| **Test** | `tests/test_tension_surfacing_service.py::test_support_deficit_detected_for_claim_without_support` |

---

### T-04 — Explicit cross-claim conflict

| | |
|--|--|
| **Memory state** | Observation O supports claim A and conflicts with claim B (A ≠ B) |
| **Expected tensions** | One `conflict` with `claim_ids` = `{A,B}`, observation O in provenance |
| **Expected non-tensions** | Semantic/NLP contradiction without explicit roles |
| **Rationale** | Conflict only when evidence roles make the opposition explicit |
| **Test** | `tests/test_tension_surfacing_service.py::test_cross_claim_conflict_explicit_via_evidence_roles` |

---

### T-05 — Superseded claims ignored

| | |
|--|--|
| **Memory state** | Claim S superseded by active claim A; S has no support |
| **Expected tensions** | None involving S |
| **Expected non-tensions** | Support deficit on superseded claims |
| **Rationale** | `list_claims(active_only=True)` excludes superseded rows |
| **Test** | `tests/test_tension_surfacing_service.py::test_superseded_claims_ignored` |

---

### T-06 — Multiple supporting observations

| | |
|--|--|
| **Memory state** | One active claim with **two** distinct `role=support` links (two observations) |
| **Expected tensions** | No `support_deficit` for that claim |
| **Expected non-tensions** | Deficit merely because support is “split” across observations |
| **Rationale** | Any non-zero support count clears the deficit rule |
| **Test** | `tests/test_tension_acceptance.py::test_acc_multiple_supporting_observations` |

---

### T-07 — Mixed support and conflict (same claim)

| | |
|--|--|
| **Memory state** | Claim C has one `support` link and one `conflict` link (possibly different observations) |
| **Expected tensions** | Intra-claim `conflict` for C; **no** `support_deficit` for C |
| **Expected non-tensions** | Support deficit when support exists |
| **Rationale** | Deficit rule is independent of conflict; conflict is explicit via role |
| **Test** | `tests/test_tension_acceptance.py::test_acc_mixed_support_and_conflict_same_claim` |

---

### T-08 — Duplicated conflict evidence

| | |
|--|--|
| **Memory state** | Two `conflict` evidence links for the same claim and same observation |
| **Expected tensions** | Exactly **one** `conflict` hypothesis for that `(claim, observation)` key |
| **Expected non-tensions** | Duplicate tension rows for the same epistemic signal |
| **Rationale** | Dedup key `(tension_type, claim_ids, observation_ref_ids)` |
| **Test** | `tests/test_tension_acceptance.py::test_acc_duplicated_conflict_evidence_deduped` |

---

### T-09 — Intra-claim conflict without support

| | |
|--|--|
| **Memory state** | Active claim with a `conflict` link and **no** `support` link |
| **Expected tensions** | `support_deficit` **and** intra-claim `conflict` |
| **Expected non-tensions** | Collapsing both into a single type; inventing cross-claim conflict |
| **Rationale** | Rules compose: missing support and explicit conflict are independent hypotheses |
| **Test** | `tests/test_tension_acceptance.py::test_acc_intra_claim_conflict_without_support` |

---

## Out of scope (by design)

- Semantic / NLP contradiction detection
- Persisted tension store
- Dashboard rendering (Step 036)
- New tension types (`incompleteness`, `authority_gap`, etc.) — may appear later; not accepted here

## Sign-off

When the suite above is green, Tension Surfacing is accepted for admin UI exposure.
