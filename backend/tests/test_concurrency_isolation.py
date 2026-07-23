"""Background vs interactive concurrency isolation."""
from __future__ import annotations

import threading

import pytest

from app.core.concurrency import ConcurrencyLimits, ConcurrencyManager

pytestmark = pytest.mark.unit


def test_background_embed_does_not_consume_interactive_slots():
    mgr = ConcurrencyManager()
    mgr.configure(
        ConcurrencyLimits(
            max_concurrent_embedding_requests=2,
            max_concurrent_background_embedding_requests=1,
        )
    )
    # Hold the only background embed slot.
    bg = mgr.background_embed_slot()
    bg.__enter__()
    try:
        # Both interactive embed slots must still be acquirable immediately.
        s1 = mgr.embed_slot(wait_seconds=0.5)
        s2 = mgr.embed_slot(wait_seconds=0.5)
        s1.__enter__()
        s2.__enter__()
        s1.__exit__()
        s2.__exit__()
    finally:
        bg.__exit__()


def test_background_llm_leaves_a_slot_for_interactive():
    mgr = ConcurrencyManager()
    mgr.configure(ConcurrencyLimits(max_concurrent_llm_requests=2))

    # Saturate the background LLM reservation (size N-1 = 1).
    held = mgr.background_llm_slot()
    started = threading.Event()
    release = threading.Event()

    def hold():
        with held:
            started.set()
            release.wait(timeout=2)

    t = threading.Thread(target=hold, daemon=True)
    t.start()
    assert started.wait(timeout=1)

    # Interactive chat LLM must still get a slot while background holds one.
    interactive = mgr.llm_slot(wait_seconds=0.5)
    interactive.__enter__()
    interactive.__exit__()

    release.set()
    t.join(timeout=2)
