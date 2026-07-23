# Performance and benchmark tests

Optional wall-clock checks that are **excluded** from `make release-check`. They are informational for local profiling, not engineering gates.

## What runs in release-check

`make release-check` runs backend unit tests with:

```bash
pytest ... -m "unit and not benchmark"
```

Structural routing tests (no timing) live in `tests/test_chat_stream_executive_routing.py`:

| Test | Purpose |
|------|---------|
| `test_stream_dispatch_flag_off_uses_rag_streaming` | Legacy path when Executive flag OFF |
| `test_stream_dispatch_flag_on_uses_executive` | Executive path when flag ON |
| `test_stream_golden_parity_legacy_vs_executive` | Event parity between paths |

These prove dispatch routing without wall-clock thresholds.

## Optional benchmarks

| File | Marker | Description |
|------|--------|-------------|
| `tests/test_chat_stream_dispatch_benchmark.py` | `benchmark` | Legacy vs executive time-to-first-event (soft 50ms median budget) |

### Run manually

```bash
# From repo root
bash scripts/release/test-backend-benchmarks.sh

# Or directly
cd backend && .venv/bin/pytest tests/test_chat_stream_dispatch_benchmark.py -m benchmark -v
```

### Why excluded

Wall-clock comparisons in a loaded pytest process are unstable across hosts (WSL, CI, parallel suites). Release 0.4 documented this as test debt — see `RELEASE-0.4-ACCEPTANCE-REPORT.md` §6.

## Adding new benchmarks

1. Mark with `@pytest.mark.benchmark` in `pytest.ini`.
2. Do **not** add to `scripts/release/test-backend-unit.sh`.
3. Document in this file.
4. Prefer structural tests for release gates; use benchmarks for manual investigation only.
