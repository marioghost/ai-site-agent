# Epistemic test-row cleanup plan (demo readiness)

**Status:** dry-run tooling only — **no deletion executed** as part of demo prep.

## Scripts

| Script | Purpose |
|--------|---------|
| [`audit_epistemic_test_rows.py`](audit_epistemic_test_rows.py) | Read-only inventory + real/test stats |
| [`cleanup_epistemic_test_rows.py`](cleanup_epistemic_test_rows.py) | Dry-run plan; optional `--execute` behind guards |

## Identification rules

A claim is **test-owned** when:

- `provenance_kind = 'test'` **or**
- `attributed_to = 'fixture'`

**Never** delete `provenance_kind = 'source_intelligence'`.

Observations / evidence with `provenance_kind = 'test'`, or evidence linked to test claims, are included in the cleanup set.

## Safe delete order

1. `pg_dump -Fc -t observation_ref -t claim -t evidence_link` (backup)
2. `DELETE` matching `evidence_link` rows
3. `DELETE` matching test `claim` rows (SI excluded)
4. `DELETE` test `observation_ref` rows that are no longer referenced

## Never touch

sources, chunks, Qdrant, chat_logs, chat_sessions, chat_messages, settings, users, index_jobs, job_events.

## Execute gates

```bash
# 1) Dry-run
python scripts/recovery/cleanup_epistemic_test_rows.py --dry-run --out /tmp/cleanup-plan.json

# 2) Only after explicit human approval, with counts from dry-run:
python scripts/recovery/cleanup_epistemic_test_rows.py \
  --execute --i-understand \
  --expected-evidence N --expected-claims M --expected-obs K
```

Mismatch between expected and actual counts → **abort + rollback**.
