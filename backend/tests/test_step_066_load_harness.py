"""Unit tests for Step 066 load harness metrics (no live /opt required)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "scripts/release/step066_load_harness.py"


def _load():
    name = "step066_load_harness"
    spec = importlib.util.spec_from_file_location(name, HARNESS)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pytestmark = pytest.mark.unit


def test_p95_and_5xx_rate():
    m = _load()
    phase = m.PhaseStats("t")
    for ms in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
        phase.samples.append(m.Sample("nonstream", True, 200, float(ms), phase="t"))
    phase.samples.append(m.Sample("nonstream", False, 500, 1.0, phase="t"))
    assert phase.p95("nonstream") == 90.0
    # 1 unexpected 5xx among 11 non-intentional
    assert 0.09 < phase.unexpected_5xx_rate() < 0.1


def test_evaluate_pass_and_fail_thresholds():
    m = _load()
    cfg = {
        "cancel_target": 2,
        "acceptance": {"max_unexpected_5xx_rate": 0.01, "p95_ratio_limit": 1.05},
    }
    warm = m.PhaseStats("warmup")
    sus = m.PhaseStats("sustained")
    for ms in [100, 110, 120, 100, 105]:
        warm.samples.append(m.Sample("nonstream", True, 200, float(ms)))
        warm.samples.append(m.Sample("stream", True, 200, float(ms)))
        sus.samples.append(m.Sample("nonstream", True, 200, float(ms)))
        sus.samples.append(m.Sample("stream", True, 200, float(ms)))
    sus.samples.append(m.Sample("stream_cancel", True, 200, 50.0, intentional=True))
    sus.samples.append(m.Sample("stream_cancel", True, 200, 50.0, intentional=True))
    probes = {"cancel_count": 2, "overload_controlled": True, "health_after_probes": True}
    ok = m.evaluate(cfg, warm, sus, probes)
    assert ok["verdict"] == "PASS"

    sus.samples.append(m.Sample("nonstream", False, 500, 200.0))
    sus.samples.append(m.Sample("nonstream", False, 500, 200.0))
    bad = m.evaluate(cfg, warm, sus, probes)
    assert bad["verdict"] == "FAIL"
    assert bad["unexpected_5xx_ok"] is False


def test_config_file_exists_and_frozen_keys():
    cfg = json.loads(
        (ROOT / "docs/releases/1.0-step-066-load-config.json").read_text(encoding="utf-8")
    )
    assert cfg["tip_sha"] == "a41198f28f59c2d22c78e63f0afec9448ca8fe0c"
    assert cfg["sustained_seconds"] == 3600
    assert cfg["steady_state_concurrency"] == 2
    assert cfg["session_prefix"] == "step066-load-"
    assert cfg["cancel_target"] == 20
    assert cfg["overload_burst"] == 20


def test_parse_prom_counter():
    m = _load()
    body = (
        "# HELP kos_investigations_planned x\n"
        "# TYPE kos_investigations_planned counter\n"
        "kos_investigations_planned 12\n"
        "kos_other 3\n"
    )
    assert m.parse_prom_counter(body, "kos_investigations_planned") == 12
    assert m.parse_prom_counter(body, "missing") == 0
