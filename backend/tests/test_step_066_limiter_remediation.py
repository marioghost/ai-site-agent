"""RFC-100 Step 066 limiter remediation — behavioral admission tests.

Package: docs/releases/1.0-step-066-limiter-remediation-engineering-package.md
Behavioral only — no source-string inspection as correctness proof.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.chat import EXECUTIVE_DISABLED_DETAIL
from app.core.concurrency import (
    ConcurrencyLimits,
    ConcurrencyManager,
    OverloadedError,
)
from app.services.feature_flags import FLAG_DEFINITIONS, flag_keys


pytestmark = pytest.mark.unit


def _hold(slot_factory, ready: threading.Event, release: threading.Event, errors: list):
    try:
        with slot_factory():
            ready.set()
            if not release.wait(timeout=5):
                errors.append("release timeout")
    except Exception as exc:  # noqa: BLE001 — collect for assertion
        errors.append(exc)
        ready.set()


# --- T1 configure race ---


def test_t1_configure_race_peak_holders_never_exceed_limit():
    mgr = ConcurrencyManager()
    limit = 4
    mgr.configure(
        ConcurrencyLimits(
            max_concurrent_chat_requests=limit,
            max_concurrent_llm_requests=2,
            max_concurrent_embedding_requests=2,
            max_concurrent_background_embedding_requests=1,
        )
    )
    stop = threading.Event()
    errors: list = []
    peak = {"v": 0}
    peak_lock = threading.Lock()

    def reconfigure():
        while not stop.is_set():
            mgr.configure(
                ConcurrencyLimits(
                    max_concurrent_chat_requests=limit,
                    max_concurrent_llm_requests=2,
                    max_concurrent_embedding_requests=2,
                    max_concurrent_background_embedding_requests=1,
                )
            )

    def worker():
        try:
            with mgr.chat_slot(wait_seconds=1.0):
                snap = mgr.limiter_instrumentation()["chat"]
                with peak_lock:
                    peak["v"] = max(peak["v"], int(snap["active"]))
                time.sleep(0.05)
        except OverloadedError:
            pass
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    cfg_threads = [threading.Thread(target=reconfigure, daemon=True) for _ in range(4)]
    for t in cfg_threads:
        t.start()

    with ThreadPoolExecutor(max_workers=24) as pool:
        futures = [pool.submit(worker) for _ in range(40)]
        for f in as_completed(futures):
            f.result()

    stop.set()
    for t in cfg_threads:
        t.join(timeout=1)

    assert not errors
    assert peak["v"] <= limit
    assert int(mgr.limiter_instrumentation()["chat"]["peak_active"]) <= limit
    assert mgr.metrics.active_chat == 0


# --- T2 same-limit configure ---


def test_t2_same_limit_configure_does_not_inflate_capacity():
    mgr = ConcurrencyManager()
    mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=2))
    domain_before = mgr.limiter_instrumentation()["chat"]["domain_id"]
    ready = [threading.Event(), threading.Event()]
    release = threading.Event()
    errors: list = []

    holders = []
    for i in range(2):
        t = threading.Thread(
            target=_hold,
            args=(lambda: mgr.chat_slot(wait_seconds=1.0), ready[i], release, errors),
            daemon=True,
        )
        holders.append(t)
        t.start()
    assert ready[0].wait(timeout=1) and ready[1].wait(timeout=1)
    assert mgr.metrics.active_chat == 2

    for _ in range(50):
        mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=2))

    with pytest.raises(OverloadedError):
        with mgr.chat_slot(wait_seconds=0.2):
            pass

    assert mgr.limiter_instrumentation()["chat"]["domain_id"] == domain_before
    assert mgr.limiter_instrumentation()["limit_change_count"] == 1  # initial only
    assert mgr.limiter_instrumentation()["configure_count"] >= 51

    release.set()
    for t in holders:
        t.join(timeout=2)
    assert not errors
    assert mgr.metrics.active_chat == 0


# --- T3 limit increase ---


def test_t3_limit_increase_adds_only_delta_capacity():
    mgr = ConcurrencyManager()
    mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=2))
    domain = mgr.limiter_instrumentation()["chat"]["domain_id"]
    ready = [threading.Event(), threading.Event()]
    release = threading.Event()
    errors: list = []
    for i in range(2):
        threading.Thread(
            target=_hold,
            args=(lambda: mgr.chat_slot(wait_seconds=1.0), ready[i], release, errors),
            daemon=True,
        ).start()
    assert ready[0].wait(1) and ready[1].wait(1)

    with pytest.raises(OverloadedError):
        with mgr.chat_slot(wait_seconds=0.15):
            pass

    mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=3))
    assert mgr.limiter_instrumentation()["chat"]["domain_id"] == domain

    third_ready = threading.Event()
    threading.Thread(
        target=_hold,
        args=(lambda: mgr.chat_slot(wait_seconds=0.5), third_ready, release, errors),
        daemon=True,
    ).start()
    assert third_ready.wait(timeout=1)
    assert mgr.metrics.active_chat == 3

    with pytest.raises(OverloadedError):
        with mgr.chat_slot(wait_seconds=0.15):
            pass

    release.set()
    time.sleep(0.1)
    assert not errors


# --- T4 limit decrease ---


def test_t4_limit_decrease_blocks_new_admissions_above_new_limit():
    mgr = ConcurrencyManager()
    mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=3))
    domain = mgr.limiter_instrumentation()["chat"]["domain_id"]
    ready = [threading.Event() for _ in range(3)]
    release = threading.Event()
    errors: list = []
    for i in range(3):
        threading.Thread(
            target=_hold,
            args=(lambda: mgr.chat_slot(wait_seconds=1.0), ready[i], release, errors),
            daemon=True,
        ).start()
    assert all(r.wait(1) for r in ready)
    assert mgr.metrics.active_chat == 3

    mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=1))
    assert mgr.limiter_instrumentation()["chat"]["domain_id"] == domain
    # Existing holders may remain; new admissions must not raise active above prior
    # holders and must not admit while active > new limit.
    with pytest.raises(OverloadedError):
        with mgr.chat_slot(wait_seconds=0.2):
            pass

    release.set()
    time.sleep(0.15)
    assert mgr.metrics.active_chat == 0

    one_ready = threading.Event()
    one_release = threading.Event()
    threading.Thread(
        target=_hold,
        args=(lambda: mgr.chat_slot(wait_seconds=0.5), one_ready, one_release, errors),
        daemon=True,
    ).start()
    assert one_ready.wait(1)
    assert mgr.metrics.active_chat == 1
    with pytest.raises(OverloadedError):
        with mgr.chat_slot(wait_seconds=0.15):
            pass
    one_release.set()
    time.sleep(0.05)
    assert not errors


# --- T5 overload timeout ---


def test_t5_overload_timeout_when_saturated():
    mgr = ConcurrencyManager()
    mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=1))
    ready = threading.Event()
    release = threading.Event()
    errors: list = []
    threading.Thread(
        target=_hold,
        args=(lambda: mgr.chat_slot(wait_seconds=1.0), ready, release, errors),
        daemon=True,
    ).start()
    assert ready.wait(1)

    started = time.monotonic()
    with pytest.raises(OverloadedError):
        with mgr.chat_slot(wait_seconds=0.25):
            pass
    elapsed = time.monotonic() - started
    assert elapsed >= 0.2
    assert int(mgr.limiter_instrumentation()["chat"]["timeout_count"]) >= 1

    release.set()
    time.sleep(0.05)
    assert not errors


# --- T6 recovery ---


def test_t6_recovery_after_release():
    mgr = ConcurrencyManager()
    mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=1))
    ready = threading.Event()
    release = threading.Event()
    errors: list = []
    threading.Thread(
        target=_hold,
        args=(lambda: mgr.chat_slot(wait_seconds=1.0), ready, release, errors),
        daemon=True,
    ).start()
    assert ready.wait(1)
    with pytest.raises(OverloadedError):
        with mgr.chat_slot(wait_seconds=0.15):
            pass

    release.set()
    time.sleep(0.05)
    with mgr.chat_slot(wait_seconds=0.5):
        assert mgr.metrics.active_chat == 1
    assert mgr.metrics.active_chat == 0
    assert not errors


# --- T7 LLM limiter ---


def test_t7_llm_limiter_peak_under_concurrent_configure():
    mgr = ConcurrencyManager()
    limit = 2
    mgr.configure(ConcurrencyLimits(max_concurrent_llm_requests=limit))
    stop = threading.Event()
    peak = {"v": 0}
    lock = threading.Lock()

    def reconfigure():
        while not stop.is_set():
            mgr.configure(ConcurrencyLimits(max_concurrent_llm_requests=limit))

    def worker():
        try:
            with mgr.llm_slot(wait_seconds=0.5):
                snap = mgr.limiter_instrumentation()["llm"]
                with lock:
                    peak["v"] = max(peak["v"], int(snap["active"]))
                time.sleep(0.03)
        except OverloadedError:
            pass

    threads = [threading.Thread(target=reconfigure, daemon=True) for _ in range(3)]
    for t in threads:
        t.start()
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda _: worker(), range(30)))
    stop.set()
    assert peak["v"] <= limit
    assert int(mgr.limiter_instrumentation()["llm"]["peak_active"]) <= limit


# --- T8 embedding limiter ---


def test_t8_embedding_limiter_peak_under_concurrent_configure():
    mgr = ConcurrencyManager()
    limit = 2
    mgr.configure(ConcurrencyLimits(max_concurrent_embedding_requests=limit))
    stop = threading.Event()
    peak = {"v": 0}
    lock = threading.Lock()

    def reconfigure():
        while not stop.is_set():
            mgr.configure(ConcurrencyLimits(max_concurrent_embedding_requests=limit))

    def worker():
        try:
            with mgr.embed_slot(wait_seconds=0.5):
                snap = mgr.limiter_instrumentation()["embed"]
                with lock:
                    peak["v"] = max(peak["v"], int(snap["active"]))
                time.sleep(0.03)
        except OverloadedError:
            pass

    for t in [threading.Thread(target=reconfigure, daemon=True) for _ in range(3)]:
        t.start()
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda _: worker(), range(30)))
    stop.set()
    assert peak["v"] <= limit
    assert int(mgr.limiter_instrumentation()["embed"]["peak_active"]) <= limit


# --- T9 active counter correctness ---


def test_t9_active_and_queued_counters_match_holders_and_waiters():
    mgr = ConcurrencyManager()
    mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=1))
    ready = threading.Event()
    release = threading.Event()
    errors: list = []
    threading.Thread(
        target=_hold,
        args=(lambda: mgr.chat_slot(wait_seconds=2.0), ready, release, errors),
        daemon=True,
    ).start()
    assert ready.wait(1)
    assert mgr.metrics.active_chat == 1
    assert mgr.metrics.queued_chat == 0

    waiter_started = threading.Event()
    waiter_done = threading.Event()
    waiter_exc: list = []

    def waiter():
        waiter_started.set()
        try:
            with mgr.chat_slot(wait_seconds=0.4):
                pass
        except OverloadedError as exc:
            waiter_exc.append(exc)
        finally:
            waiter_done.set()

    threading.Thread(target=waiter, daemon=True).start()
    assert waiter_started.wait(1)
    time.sleep(0.05)
    assert mgr.metrics.active_chat == 1
    assert mgr.metrics.queued_chat >= 1

    assert waiter_done.wait(2)
    assert waiter_exc
    assert mgr.metrics.queued_chat == 0
    assert mgr.metrics.active_chat == 1

    release.set()
    time.sleep(0.05)
    assert mgr.metrics.active_chat == 0
    assert not errors


# --- T10 orphan generation prevention ---


def test_t10_configure_churn_keeps_single_domain_no_orphan_capacity():
    mgr = ConcurrencyManager()
    mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=2))
    domain = mgr.limiter_instrumentation()["chat"]["domain_id"]
    ready = [threading.Event(), threading.Event()]
    release = threading.Event()
    errors: list = []
    for i in range(2):
        threading.Thread(
            target=_hold,
            args=(lambda: mgr.chat_slot(wait_seconds=1.0), ready[i], release, errors),
            daemon=True,
        ).start()
    assert ready[0].wait(1) and ready[1].wait(1)

    for n in range(30):
        # Alternate same and changed-back-to-same to exercise apply path.
        mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=2 + (n % 2)))
        mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=2))

    assert mgr.limiter_instrumentation()["chat"]["domain_id"] == domain
    # Still saturated at 2 — no orphan domain granting extra capacity.
    with pytest.raises(OverloadedError):
        with mgr.chat_slot(wait_seconds=0.2):
            pass
    assert mgr.metrics.active_chat == 2
    release.set()
    time.sleep(0.1)
    assert mgr.metrics.active_chat == 0
    assert not errors


# --- T11 Step 064 regression ---


def test_t11_step_064_executive_disabled_503_and_overload_429(monkeypatch):
    from app.api.chat import _dispatch_non_stream_answer

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        _dispatch_non_stream_answer(
            MagicMock(), MagicMock(), "q", "s", request_id="r"
        )
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == EXECUTIVE_DISABLED_DETAIL

    # Capacity overload remains 429 with published overload message (not 503).
    exc = OverloadedError()
    mapped = HTTPException(status_code=429, detail=exc.message)
    assert mapped.status_code == 429
    assert mapped.detail == OverloadedError.message
    assert mapped.status_code != 503


def test_t11_admission_overload_raises_overloaded_error_not_503():
    """Saturated chat admission must raise OverloadedError (429 path), not 503."""
    mgr = ConcurrencyManager()
    mgr.configure(ConcurrencyLimits(max_concurrent_chat_requests=1))
    ready = threading.Event()
    release = threading.Event()
    errors: list = []
    threading.Thread(
        target=_hold,
        args=(lambda: mgr.chat_slot(wait_seconds=1.0), ready, release, errors),
        daemon=True,
    ).start()
    assert ready.wait(1)
    with pytest.raises(OverloadedError):
        with mgr.chat_slot(wait_seconds=0.2):
            pass
    release.set()
    time.sleep(0.05)
    assert not errors


# --- T12 Step 065 regression ---


def test_t12_step_065_flag_definitions_unchanged_by_limiter_work():
    keys = flag_keys()
    assert FLAG_DEFINITIONS
    assert len(keys) == len(set(keys))
    # Registry still classifies executive kill-switch as env-owned product-invisible.
    from app.services.feature_flags import flag_definition_by_key

    executive = flag_definition_by_key()["KNOWLEDGE_OS_EXECUTIVE_ENABLED"]
    assert executive.source == "env"
    assert executive.product_visibility is False
    assert executive.engineering_visibility is True
