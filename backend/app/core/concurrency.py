"""Global concurrency limits and lightweight performance metrics.

Protects local Ollama from overload by limiting concurrent chat, LLM and
embedding requests. Tracks active/queued counts and recent latencies for the
performance API.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, TypeVar

T = TypeVar("T")

_OVERLOAD_MSG = (
    "Система тимчасово перевантажена. Спробуйте ще раз за кілька секунд."
)


class OverloadedError(Exception):
    """Raised when a concurrency slot cannot be acquired within the wait window."""

    message = _OVERLOAD_MSG


@dataclass
class ConcurrencyLimits:
    max_concurrent_chat_requests: int = 20
    max_concurrent_llm_requests: int = 2
    max_concurrent_embedding_requests: int = 2
    # Background (indexing / reprocess) embedding runs on a separate, smaller
    # pool so a long-running job can never consume the interactive embedding
    # slots that chat query-embedding needs.
    max_concurrent_background_embedding_requests: int = 1


@dataclass
class PerformanceMetrics:
    active_chat: int = 0
    queued_chat: int = 0
    latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=500))
    cache_hits: int = 0
    cache_misses: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_latency(self, ms: float) -> None:
        with self._lock:
            self.latencies_ms.append(ms)

    def record_cache(self, hit: bool) -> None:
        with self._lock:
            if hit:
                self.cache_hits += 1
            else:
                self.cache_misses += 1

    def latency_stats(self) -> tuple[float, float]:
        with self._lock:
            if not self.latencies_ms:
                return 0.0, 0.0
            sorted_vals = sorted(self.latencies_ms)
            avg = sum(sorted_vals) / len(sorted_vals)
            p95_idx = max(0, int(len(sorted_vals) * 0.95) - 1)
            return avg, sorted_vals[p95_idx]

    def cache_hit_rate(self) -> float:
        with self._lock:
            total = self.cache_hits + self.cache_misses
            return self.cache_hits / total if total else 0.0


class ConcurrencyManager:
    def __init__(self) -> None:
        self.limits = ConcurrencyLimits()
        self.metrics = PerformanceMetrics()
        self._chat_sem = threading.Semaphore(20)
        self._llm_sem = threading.Semaphore(2)
        self._embed_sem = threading.Semaphore(2)
        self._bg_embed_sem = threading.Semaphore(1)
        # Background LLM may hold at most (N-1) of the N shared LLM slots, so an
        # interactive chat generation can always reach a slot. Total Ollama load
        # stays bounded by max_concurrent_llm_requests.
        self._bg_llm_sem = threading.Semaphore(1)
        self._lock = threading.Lock()

    def configure(self, limits: ConcurrencyLimits) -> None:
        with self._lock:
            self.limits = limits
            self._chat_sem = threading.Semaphore(max(1, limits.max_concurrent_chat_requests))
            self._llm_sem = threading.Semaphore(max(1, limits.max_concurrent_llm_requests))
            self._embed_sem = threading.Semaphore(
                max(1, limits.max_concurrent_embedding_requests)
            )
            self._bg_embed_sem = threading.Semaphore(
                max(1, limits.max_concurrent_background_embedding_requests)
            )
            self._bg_llm_sem = threading.Semaphore(
                max(1, limits.max_concurrent_llm_requests - 1)
            )

    def chat_slot(self, wait_seconds: float = 2.0):
        return _Slot(self._chat_sem, self.metrics, "chat", wait_seconds)

    def llm_slot(self, wait_seconds: float = 5.0):
        return _Slot(self._llm_sem, self.metrics, "llm", wait_seconds)

    def embed_slot(self, wait_seconds: float = 5.0):
        return _Slot(self._embed_sem, self.metrics, "embed", wait_seconds)

    def background_embed_slot(self):
        """Blocking slot for bulk indexing/reprocess embeddings.

        Background work waits for its dedicated pool instead of raising, so it
        never competes with the interactive embedding slots used by chat.
        """
        return _BlockingSlot(self._bg_embed_sem)

    def background_llm_slot(self):
        """Blocking slot for background LLM work (Source Intelligence).

        Acquires the background reservation first, then a shared LLM slot, so
        total Ollama concurrency stays bounded and at least one LLM slot remains
        reachable by interactive chat generation.
        """
        return _NestedBlockingSlot(self._bg_llm_sem, self._llm_sem)


class _Slot:
    def __init__(
        self,
        sem: threading.Semaphore,
        metrics: PerformanceMetrics,
        kind: str,
        wait_seconds: float,
    ) -> None:
        self._sem = sem
        self._metrics = metrics
        self._kind = kind
        self._wait = wait_seconds
        self._acquired = False

    def __enter__(self) -> _Slot:
        if self._kind == "chat":
            with self._metrics._lock:
                self._metrics.queued_chat += 1
        deadline = time.monotonic() + self._wait
        while time.monotonic() < deadline:
            if self._sem.acquire(blocking=False):
                self._acquired = True
                if self._kind == "chat":
                    with self._metrics._lock:
                        self._metrics.queued_chat -= 1
                        self._metrics.active_chat += 1
                return self
            time.sleep(0.05)
        if self._kind == "chat":
            with self._metrics._lock:
                self._metrics.queued_chat -= 1
        raise OverloadedError()

    def __exit__(self, *args: object) -> None:
        if self._acquired:
            self._sem.release()
            if self._kind == "chat":
                with self._metrics._lock:
                    self._metrics.active_chat -= 1


class _BlockingSlot:
    """Acquire a semaphore, blocking until available (no overload error)."""

    def __init__(self, sem: threading.Semaphore) -> None:
        self._sem = sem
        self._acquired = False

    def __enter__(self) -> _BlockingSlot:
        self._sem.acquire()
        self._acquired = True
        return self

    def __exit__(self, *args: object) -> None:
        if self._acquired:
            self._sem.release()


class _NestedBlockingSlot:
    """Acquire an outer reservation then an inner shared semaphore (blocking).

    Releases in reverse order. Used so background LLM work reserves capacity but
    still counts against the shared LLM limit, leaving headroom for chat.
    """

    def __init__(self, outer: threading.Semaphore, inner: threading.Semaphore) -> None:
        self._outer = outer
        self._inner = inner
        self._outer_acquired = False
        self._inner_acquired = False

    def __enter__(self) -> _NestedBlockingSlot:
        self._outer.acquire()
        self._outer_acquired = True
        self._inner.acquire()
        self._inner_acquired = True
        return self

    def __exit__(self, *args: object) -> None:
        if self._inner_acquired:
            self._inner.release()
        if self._outer_acquired:
            self._outer.release()


concurrency = ConcurrencyManager()
