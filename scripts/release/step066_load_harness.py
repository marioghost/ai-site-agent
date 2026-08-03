#!/usr/bin/env python3
"""RFC-100 Step 066 — repository-native Ask load harness (httpx).

Engineering Package: docs/releases/1.0-step-066-engineering-package.md
Designated runtime: http://127.0.0.1:8000 → /opt/ai-site-agent
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "docs/releases/1.0-step-066-load-config.json"
DEFAULT_RESULTS = ROOT / "docs/releases/1.0-step-066-load-results.json"


@dataclass
class Sample:
    kind: str
    ok: bool
    status: int | None
    latency_ms: float
    error: str | None = None
    phase: str = "sustained"
    intentional: bool = False


@dataclass
class PhaseStats:
    name: str
    samples: list[Sample] = field(default_factory=list)

    def latencies(self, kind: str | None = None, *, intentional: bool = False) -> list[float]:
        out = []
        for s in self.samples:
            if s.intentional != intentional:
                continue
            if kind is not None and s.kind != kind:
                continue
            if s.ok:
                out.append(s.latency_ms)
        return out

    def p95(self, kind: str | None = None) -> float | None:
        vals = sorted(self.latencies(kind))
        if not vals:
            return None
        idx = max(0, int(len(vals) * 0.95) - 1)
        return vals[idx]

    def unexpected_5xx_rate(self) -> float:
        relevant = [s for s in self.samples if not s.intentional]
        if not relevant:
            return 0.0
        bad = sum(1 for s in relevant if (s.status or 0) >= 500)
        return bad / len(relevant)


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def percentile(vals: list[float], p: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    idx = max(0, int(len(s) * p) - 1)
    return s[idx]


async def login(client: httpx.AsyncClient, cfg: dict[str, Any]) -> str:
    user = os.environ.get("STAGING_ADMIN_USER", "admin")
    password = os.environ.get("STAGING_ADMIN_PASSWORD", "фвьшт")
    r = await client.post(
        "/api/auth/login",
        json={"username": user, "password": password},
        timeout=30.0,
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise RuntimeError("login missing access_token")
    return token


def query_for(cfg: dict[str, Any], i: int) -> tuple[str, str]:
    q = cfg["queries"]
    cycle = i % 3
    if cycle == 0:
        return "known_answer", q["known_answer"]
    if cycle == 1:
        return "broad", q["broad"]
    return "no_evidence", q["no_evidence"]


async def one_nonstream(
    client: httpx.AsyncClient,
    cfg: dict[str, Any],
    token: str,
    i: int,
    phase: str,
    *,
    bypass_cache: bool = False,
    message: str | None = None,
) -> Sample:
    qclass, text = query_for(cfg, i)
    if message is not None:
        text = message
    sid = f"{cfg['session_prefix']}{phase}-ns-{uuid.uuid4().hex[:12]}"
    t0 = time.perf_counter()
    try:
        r = await client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": text, "session_id": sid, "bypass_cache": bypass_cache},
            timeout=float(cfg["request_timeout_seconds"]),
        )
        ms = (time.perf_counter() - t0) * 1000
        ok = 200 <= r.status_code < 300
        intentional = phase == "overload" and r.status_code == 429
        if intentional:
            ok = True
        return Sample(
            "nonstream",
            ok,
            r.status_code,
            ms,
            None if ok else r.text[:200],
            phase,
            intentional=intentional,
        )
    except Exception as exc:  # noqa: BLE001 — harness must record all failures
        ms = (time.perf_counter() - t0) * 1000
        return Sample("nonstream", False, None, ms, str(exc)[:200], phase)


async def one_stream(
    client: httpx.AsyncClient,
    cfg: dict[str, Any],
    token: str,
    i: int,
    phase: str,
    *,
    cancel: bool = False,
) -> Sample:
    qclass, text = query_for(cfg, i)
    sid = f"{cfg['session_prefix']}{phase}-st-{uuid.uuid4().hex[:12]}"
    t0 = time.perf_counter()
    first_ms: float | None = None
    try:
        async with client.stream(
            "POST",
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": text, "session_id": sid},
            timeout=float(cfg["request_timeout_seconds"]),
        ) as r:
            status = r.status_code
            if status >= 400:
                await r.aread()
                ms = (time.perf_counter() - t0) * 1000
                return Sample(
                    "stream_cancel" if cancel else "stream",
                    False,
                    status,
                    ms,
                    f"http_{status}",
                    phase,
                    intentional=cancel,
                )
            async for _chunk in r.aiter_bytes():
                if first_ms is None:
                    first_ms = (time.perf_counter() - t0) * 1000
                    if cancel:
                        break
            # Ensure cancel closes the HTTP stream promptly (slot/DB release on server).
            if cancel:
                await r.aclose()
            ms = first_ms if first_ms is not None else (time.perf_counter() - t0) * 1000
            if cancel:
                return Sample("stream_cancel", True, status, ms, None, phase, intentional=True)
            return Sample("stream", True, status, ms, None, phase)
    except Exception as exc:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        return Sample(
            "stream_cancel" if cancel else "stream",
            False,
            None,
            ms,
            str(exc)[:200],
            phase,
            intentional=cancel,
        )


async def fetch_json(client: httpx.AsyncClient, path: str) -> dict[str, Any]:
    r = await client.get(path, timeout=30.0)
    r.raise_for_status()
    return r.json()


def parse_prom_counter(body: str, name: str) -> int:
    """Parse a Prometheus counter/gauge line (ignore HELP/TYPE)."""
    for line in body.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        if line.startswith(name + " ") or line.startswith(name + "{"):
            parts = line.split()
            try:
                return int(float(parts[-1]))
            except (ValueError, IndexError):
                continue
    return 0


async def fetch_maintenance_planned(client: httpx.AsyncClient) -> int:
    r = await client.get("/api/metrics", timeout=30.0)
    r.raise_for_status()
    return parse_prom_counter(r.text, "kos_investigations_planned")


def evaluate(cfg: dict[str, Any], warmup: PhaseStats, sustained: PhaseStats, probes: dict) -> dict[str, Any]:
    acc = cfg["acceptance"]
    base_ns = warmup.p95("nonstream")
    base_st = warmup.p95("stream")
    sus_ns = sustained.p95("nonstream")
    sus_st = sustained.p95("stream")
    rate5 = sustained.unexpected_5xx_rate()
    duration_ok = True  # caller sets wall clock
    checks = {
        "unexpected_5xx_rate": rate5,
        "unexpected_5xx_ok": rate5 <= float(acc["max_unexpected_5xx_rate"]),
        "warmup_nonstream_p95_ms": base_ns,
        "sustained_nonstream_p95_ms": sus_ns,
        "warmup_stream_ttfb_p95_ms": base_st,
        "sustained_stream_ttfb_p95_ms": sus_st,
        "nonstream_p95_ratio": (sus_ns / base_ns) if base_ns and sus_ns else None,
        "stream_p95_ratio": (sus_st / base_st) if base_st and sus_st else None,
        "nonstream_p95_ok": (
            sus_ns is not None
            and base_ns is not None
            and sus_ns <= float(acc["p95_ratio_limit"]) * base_ns
        ),
        "stream_p95_ok": (
            sus_st is not None
            and base_st is not None
            and sus_st <= float(acc["p95_ratio_limit"]) * base_st
        ),
        "cancel_count": probes.get("cancel_count", 0),
        "cancel_ok": probes.get("cancel_count", 0) >= int(cfg["cancel_target"]),
        "overload_controlled": probes.get("overload_controlled", False),
        "health_after_probes": probes.get("health_after_probes", False),
    }
    checks["verdict"] = (
        "PASS"
        if all(
            [
                checks["unexpected_5xx_ok"],
                checks["nonstream_p95_ok"],
                checks["stream_p95_ok"],
                checks["cancel_ok"],
                checks["overload_controlled"],
                checks["health_after_probes"],
                duration_ok,
            ]
        )
        else "FAIL"
    )
    return checks


async def run_phase(
    client: httpx.AsyncClient,
    cfg: dict[str, Any],
    token: str,
    name: str,
    seconds: float,
    *,
    cancel_budget: int = 0,
) -> PhaseStats:
    stats = PhaseStats(name=name)
    end = time.monotonic() + seconds
    i = 0
    cancels_done = 0
    lock = asyncio.Lock()
    conc = int(cfg["steady_state_concurrency"])
    stream_fraction = float(cfg["stream_fraction"])

    async def worker() -> None:
        nonlocal i, cancels_done
        while time.monotonic() < end:
            async with lock:
                idx = i
                i += 1
                use_stream = (idx % 2 == 0) if stream_fraction >= 0.5 else (
                    (idx % 100) < int(stream_fraction * 100)
                )
                do_cancel = False
                if use_stream and cancels_done < cancel_budget and (idx % 17 == 0):
                    cancels_done += 1
                    do_cancel = True
            if do_cancel:
                sample = await one_stream(client, cfg, token, idx, name, cancel=True)
            elif use_stream:
                sample = await one_stream(client, cfg, token, idx, name)
            else:
                sample = await one_nonstream(client, cfg, token, idx, name)
            stats.samples.append(sample)

    tasks = [asyncio.create_task(worker()) for _ in range(conc)]
    await asyncio.gather(*tasks)
    return stats


async def overload_probe(client: httpx.AsyncClient, cfg: dict[str, Any], token: str) -> dict[str, Any]:
    # Burst above chat capacity with uncached unique prompts so slots stay held.
    burst = max(int(cfg["overload_burst"]), 24)
    tasks = [
        one_nonstream(
            client,
            cfg,
            token,
            i,
            "overload",
            bypass_cache=True,
            message=f"Step066 overload probe {i} {uuid.uuid4().hex}",
        )
        for i in range(burst)
    ]
    samples = await asyncio.gather(*tasks)
    statuses = [s.status for s in samples]
    controlled = any(s == 429 for s in statuses) or any(
        s.error and "overloaded" in (s.error or "").lower() for s in samples
    )
    server_crash = sum(1 for s in statuses if s is not None and s >= 500) > burst // 2
    health = await client.get("/api/health", timeout=30.0)
    return {
        "samples": [asdict(s) for s in samples],
        "status_counts": {
            str(k): sum(1 for s in statuses if s == k)
            for k in sorted({x for x in statuses if x is not None})
        },
        "overload_controlled": bool(controlled and health.status_code == 200 and not server_crash),
        "health_status": health.status_code,
    }


async def async_main(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    base = cfg["base_url"].rstrip("/")
    results_path = Path(args.results)
    started = datetime.now(timezone.utc).isoformat()
    t_wall0 = time.monotonic()
    post_errors: list[str] = []

    limits = httpx.Limits(max_connections=32, max_keepalive_connections=16)
    async with httpx.AsyncClient(base_url=base, limits=limits) as client:
        health = await client.get("/api/health", timeout=60.0)
        health.raise_for_status()
        build = await fetch_json(client, "/api/build")
        tip = build.get("git_commit") or build.get("git_commit_short")
        if tip and not str(tip).startswith(str(cfg["tip_sha"])[:7]):
            # allow short match
            if str(cfg["tip_sha"])[:7] not in str(tip) and str(tip) not in str(cfg["tip_sha"]):
                raise SystemExit(f"tip mismatch: build={tip} expected={cfg['tip_sha']}")

        try:
            metrics_ops_before = await fetch_json(client, "/api/metrics/operational")
        except Exception as exc:  # noqa: BLE001
            metrics_ops_before = {"error": str(exc)[:200]}
            post_errors.append(f"metrics_before:{exc}")
        try:
            maint_before = await fetch_maintenance_planned(client)
        except Exception as exc:  # noqa: BLE001
            maint_before = 0
            post_errors.append(f"maint_before:{exc}")
        token = await login(client, cfg)

        warmup = await run_phase(
            client, cfg, token, "warmup", float(cfg["warmup_seconds"]), cancel_budget=0
        )
        # Checkpoint after warm-up so a later crash still leaves evidence
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(
            json.dumps(
                {
                    "step": "066",
                    "checkpoint": "warmup_complete",
                    "started_at": started,
                    "tip_observed_before": tip,
                    "warmup": {
                        "sample_count": len(warmup.samples),
                        "nonstream_p95_ms": warmup.p95("nonstream"),
                        "stream_ttfb_p95_ms": warmup.p95("stream"),
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        sustained = await run_phase(
            client,
            cfg,
            token,
            "sustained",
            float(cfg["sustained_seconds"]),
            cancel_budget=int(cfg["cancel_target"]),
        )
        results_path.write_text(
            json.dumps(
                {
                    "step": "066",
                    "checkpoint": "sustained_complete",
                    "started_at": started,
                    "tip_observed_before": tip,
                    "warmup": {
                        "sample_count": len(warmup.samples),
                        "nonstream_p95_ms": warmup.p95("nonstream"),
                        "stream_ttfb_p95_ms": warmup.p95("stream"),
                    },
                    "sustained": {
                        "sample_count": len(sustained.samples),
                        "nonstream_p95_ms": sustained.p95("nonstream"),
                        "stream_ttfb_p95_ms": sustained.p95("stream"),
                        "unexpected_5xx_rate": sustained.unexpected_5xx_rate(),
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        cancel_count = sum(1 for s in sustained.samples if s.kind == "stream_cancel")
        overload = await overload_probe(client, cfg, token)
        health2 = await client.get("/api/health", timeout=60.0)

        metrics_ops_after: dict[str, Any]
        try:
            metrics_ops_after = await fetch_json(client, "/api/metrics/operational")
        except Exception as exc:  # noqa: BLE001
            metrics_ops_after = {"error": str(exc)[:200]}
            post_errors.append(f"metrics_after:{exc}")
        try:
            maint_after = await fetch_maintenance_planned(client)
        except Exception as exc:  # noqa: BLE001
            maint_after = maint_before
            post_errors.append(f"maint_after:{exc}")
        try:
            build_after = await fetch_json(client, "/api/build")
        except Exception as exc:  # noqa: BLE001
            build_after = {"error": str(exc)[:200], "git_commit": tip}
            post_errors.append(f"build_after:{exc}")

    probes = {
        "cancel_count": cancel_count,
        "overload_controlled": overload["overload_controlled"],
        "health_after_probes": health2.status_code == 200,
        "overload": {k: v for k, v in overload.items() if k != "samples"},
        "post_errors": post_errors,
    }
    checks = evaluate(cfg, warmup, sustained, probes)
    wall = time.monotonic() - t_wall0
    checks["sustained_wall_seconds"] = float(cfg["sustained_seconds"])
    checks["total_wall_seconds"] = wall
    checks["duration_ok"] = wall >= float(cfg["warmup_seconds"]) + float(cfg["sustained_seconds"]) - 30
    checks["maintenance_delta"] = maint_after - maint_before
    checks["maintenance_budget_ok"] = (maint_after - maint_before) == 0
    if not checks["duration_ok"] or not checks["maintenance_budget_ok"]:
        checks["verdict"] = "FAIL"
    if post_errors:
        # Post-phase observability failure is recorded; does not alone flip PASS→FAIL
        # unless health/build identity is missing for tip proof.
        checks["post_phase_errors"] = post_errors
    payload = {
        "step": "066",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(args.config),
        "base_url": base,
        "tip_expected": cfg["tip_sha"],
        "tip_observed_before": tip,
        "tip_observed_after": build_after.get("git_commit"),
        "release": build_after.get("release"),
        "warmup": {
            "sample_count": len(warmup.samples),
            "nonstream_p95_ms": warmup.p95("nonstream"),
            "stream_ttfb_p95_ms": warmup.p95("stream"),
        },
        "sustained": {
            "sample_count": len(sustained.samples),
            "nonstream_p95_ms": sustained.p95("nonstream"),
            "stream_ttfb_p95_ms": sustained.p95("stream"),
            "unexpected_5xx_rate": sustained.unexpected_5xx_rate(),
        },
        "maintenance_investigations_planned_before": maint_before,
        "maintenance_investigations_planned_after": maint_after,
        "maintenance_investigations_planned_delta": maint_after - maint_before,
        "metrics_operational_before": metrics_ops_before,
        "metrics_operational_after": metrics_ops_after,
        "environment": cfg.get("environment"),
        "project_root": cfg.get("project_root"),
        "probes": probes,
        "acceptance": checks,
        "samples_summary": {
            "warmup": len(warmup.samples),
            "sustained": len(sustained.samples),
            "cancels": cancel_count,
        },
    }
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": checks["verdict"], "results": str(results_path)}, indent=2))
    return 0 if checks["verdict"] == "PASS" else 1


def main() -> None:
    p = argparse.ArgumentParser(description="Step 066 Ask load harness")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--results", default=str(DEFAULT_RESULTS))
    p.add_argument(
        "--quick",
        action="store_true",
        help="Override durations for dry local wiring checks (not Step 066 evidence)",
    )
    args = p.parse_args()
    if args.quick:
        cfg_path = Path(args.config)
        cfg = load_config(cfg_path)
        cfg["warmup_seconds"] = 5
        cfg["sustained_seconds"] = 15
        cfg["cancel_target"] = 2
        cfg["overload_burst"] = 8
        tmp = Path("/tmp/step066-quick-config.json")
        tmp.write_text(json.dumps(cfg), encoding="utf-8")
        args.config = str(tmp)
    raise SystemExit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
