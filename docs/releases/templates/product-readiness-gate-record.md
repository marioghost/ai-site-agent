# Product Readiness Gate Record (template)

**Package:** G9-P1  
**Authority:** `docs/RFC-PRODUCT-READINESS.md` §6.8

Copy this template for each Product Completion Step / user-facing package.

```yaml
gate_record:
  step_or_change: ""
  program: RFC-101 Product Completion
  package_ids: []
  date: ""
  reviewer: ""

  1_scope: ""
  2_rfc101_compliance: ""
  3_engineering_mode_isolation: ""
  4_simplicity_duplication: ""
  5_decision: PASS | PASS WITH DEBT | FAIL | N/A
  6_product_debt: none | accepted | must_resolve_before_1_0_acceptance
  7_debt_description: ""
  8_evidence_paths: []
  9_notes: ""
```

## Decision meanings

| Result | Meaning |
|--------|---------|
| PASS | Compliant; debt none |
| PASS WITH DEBT | Acceptable with declared debt class |
| FAIL | Must not accept |
| N/A | Not user-facing / justified non-product change |
