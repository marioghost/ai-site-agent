"""Global concurrency limits and lightweight performance metrics.

Protects local Ollama from overload by limiting concurrent chat, LLM and
embedding requests. Tracks active/queued counts and recent latencies for the
performance API.

Step 066 limiter remediation: each limiter kind uses one logical admission
domain (condition + counter). configure() never replaces the domain; unchanged
limits are a no-op; increases/decreases adjust the target without capacity
inflation across generations.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")

_OVERLOAD_MSG = (
    "Система тимчасово перевантажена. Спробуйте ще раз за кілька секунд."
)
_logger = logging.getLogger(__name__)


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
    answer_cache_hits: int = 0
    answer_cache_misses: int = 0
    retrieval_cache_hits: int = 0
    retrieval_cache_misses: int = 0
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

    def record_answer_cache(self, hit: bool) -> None:
        with self._lock:
            if hit:
                self.answer_cache_hits += 1
            else:
                self.answer_cache_misses += 1

    def record_retrieval_cache(self, hit: bool) -> None:
        with self._lock:
            if hit:
                self.retrieval_cache_hits += 1
            else:
                self.retrieval_cache_misses += 1

    def record_request_cache(self, *, overall_hit: bool, cache_info=None) -> None:
        """Record aggregate + layer hit rates from a turn's CacheStatusInfo."""
        self.record_cache(overall_hit)
        if cache_info is None:
            return
        if getattr(cache_info, "answer_lookup_attempted", False):
            self.record_answer_cache(bool(cache_info.answer_cache_hit))
        if getattr(cache_info, "retrieval_lookup_attempted", False):
            self.record_retrieval_cache(bool(cache_info.retrieval_cache_hit))

    def latency_stats(self) -> tuple[float, float]:
        with self._lock:
            if not self.latencies_ms:
                return 0.0, 0.0
            sorted_vals = sorted(self.latencies_ms)
            avg = sum(sorted_vals) / len(sorted_vals)
            p95_idx = max(0, int(len(sorted_vals) * 0.95) - 1)
            return avg, sorted_vals[p95_idx]

    @staticmethod
    def _rate(hits: int, misses: int) -> float:
        total = hits + misses
        return hits / total if total else 0.0

    def cache_hit_rate(self) -> float:
        with self._lock:
            return self._rate(self.cache_hits, self.cache_misses)

    def answer_cache_hit_rate(self) -> float:
        with self._lock:
            return self._rate(self.answer_cache_hits, self.answer_cache_misses)

    def retrieval_cache_hit_rate(self) -> float:
        with self._lock:
            return self._rate(self.retrieval_cache_hits, self.retrieval_cache_misses)


@dataclass(frozen=True)
class _NormalizedLimits:
    max_concurrent_chat_requests: int
    max_concurrent_llm_requests: int
    max_concurrent_embedding_requests: int
    max_concurrent_background_embedding_requests: int

    @classmethod
    def from_limits(cls, limits: ConcurrencyLimits) -> _NormalizedLimits:
        llm = max(1, int(limits.max_concurrent_llm_requests))
        return cls(
            max_concurrent_chat_requests=max(1, int(limits.max_concurrent_chat_requests)),
            max_concurrent_llm_requests=llm,
            max_concurrent_embedding_requests=max(
                1, int(limits.max_concurrent_embedding_requests)
            ),
            max_concurrent_background_embedding_requests=max(
                1, int(limits.max_concurrent_background_embedding_requests)
            ),
        )

    def as_concurrency_limits(self) -> ConcurrencyLimits:
        return ConcurrencyLimits(
            max_concurrent_chat_requests=self.max_concurrent_chat_requests,
            max_concurrent_llm_requests=self.max_concurrent_llm_requests,
            max_concurrent_embedding_requests=self.max_concurrent_embedding_requests,
            max_concurrent_background_embedding_requests=(
                self.max_concurrent_background_embedding_requests
            ),
        )

    @property
    def bg_llm_limit(self) -> int:
        return max(1, self.max_concurrent_llm_requests - 1)


class _AdmissionGate:
    """Single-domain admission gate: process-wide holders ≤ limit.

    Limit changes adjust the target on this same domain. The domain is never
    replaced, so concurrent configure/acquire cannot inflate capacity via
    orphaned semaphore generations.
    """

    def __init__(self, name: str, limit: int, domain_id: int = 1) -> None:
        self.name = name
        self._domain_id = domain_id
        self._cond = threading.Condition()
        self._limit = max(1, limit)
        self._active = 0
        self._peak_active = 0
        self._timeout_count = 0
        self._last_queue_wait_ms = 0.0
        self._acquire_count = 0
        self._release_count = 0

    @property
    def domain_id(self) -> int:
        return self._domain_id

    def snapshot(self) -> dict[str, float | int | str]:
        with self._cond:
            return {
                "name": self.name,
                "domain_id": self._domain_id,
                "limit": self._limit,
                "active": self._active,
                "peak_active": self._peak_active,
                "timeout_count": self._timeout_count,
                "last_queue_wait_ms": self._last_queue_wait_ms,
                "acquire_count": self._acquire_count,
                "release_count": self._release_count,
            }

    def set_limit(self, limit: int) -> None:
        with self._cond:
            self._limit = max(1, limit)
            self._cond.notify_all()

    def acquire_timed(self, wait_seconds: float) -> bool:
        deadline = time.monotonic() + wait_seconds
        started = time.monotonic()
        with self._cond:
            while True:
                if self._active < self._limit:
                    self._active += 1
                    self._acquire_count += 1
                    if self._active > self._peak_active:
                        self._peak_active = self._active
                    self._last_queue_wait_ms = (time.monotonic() - started) * 1000.0
                    _logger.debug(
                        "limiter_acquire kind=%s domain_id=%s active=%s limit=%s",
                        self.name,
                        self._domain_id,
                        self._active,
                        self._limit,
                    )
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._timeout_count += 1
                    self._last_queue_wait_ms = (time.monotonic() - started) * 1000.0
                    _logger.debug(
                        "limiter_timeout kind=%s domain_id=%s active=%s limit=%s wait_ms=%.1f",
                        self.name,
                        self._domain_id,
                        self._active,
                        self._limit,
                        self._last_queue_wait_ms,
                    )
                    return False
                self._cond.wait(timeout=remaining)

    def acquire_blocking(self) -> None:
        with self._cond:
            while self._active >= self._limit:
                self._cond.wait()
            self._active += 1
            self._acquire_count += 1
            if self._active > self._peak_active:
                self._peak_active = self._active
            _logger.debug(
                "limiter_acquire kind=%s domain_id=%s active=%s limit=%s blocking=1",
                self.name,
                self._domain_id,
                self._active,
                self._limit,
            )

    def release(self) -> None:
        with self._cond:
            if self._active <= 0:
                return
            self._active -= 1
            self._release_count += 1
            _logger.debug(
                "limiter_release kind=%s domain_id=%s active=%s limit=%s",
                self.name,
                self._domain_id,
                self._active,
                self._limit,
            )
            self._cond.notify()


class ConcurrencyManager:
    def __init__(self) -> None:
        self.limits = ConcurrencyLimits()
        self.metrics = PerformanceMetrics()
        defaults = _NormalizedLimits.from_limits(self.limits)
        self._chat = _AdmissionGate("chat", defaults.max_concurrent_chat_requests)
        self._llm = _AdmissionGate("llm", defaults.max_concurrent_llm_requests)
        self._embed = _AdmissionGate("embed", defaults.max_concurrent_embedding_requests)
        self._bg_embed = _AdmissionGate(
            "bg_embed", defaults.max_concurrent_background_embedding_requests
        )
        self._bg_llm = _AdmissionGate("bg_llm", defaults.bg_llm_limit)
        self._lock = threading.Lock()
        self._configure_count = 0
        self._limit_change_count = 0
        self._applied = defaults

    def configure(self, limits: ConcurrencyLimits) -> None:
        """Apply limits to the single admission domain per kind.

        Unchanged limits are a no-op (no domain recreation). Increased/decreased
        limits adjust the target on the existing domain only.
        """
        normalized = _NormalizedLimits.from_limits(limits)
        with self._lock:
            self._configure_count += 1
            if normalized == self._applied:
                return
            self._limit_change_count += 1
            self._applied = normalized
            self.limits = normalized.as_concurrency_limits()
            self._chat.set_limit(normalized.max_concurrent_chat_requests)
            self._llm.set_limit(normalized.max_concurrent_llm_requests)
            self._embed.set_limit(normalized.max_concurrent_embedding_requests)
            self._bg_embed.set_limit(
                normalized.max_concurrent_background_embedding_requests
            )
            self._bg_llm.set_limit(normalized.bg_llm_limit)
            _logger.debug(
                "limiter_limit_change configure_count=%s change_count=%s limits=%s",
                self._configure_count,
                self._limit_change_count,
                normalized,
            )

    def limiter_instrumentation(self) -> dict[str, object]:
        """Proof-window instrumentation (no Dashboard)."""
        with self._lock:
            configure_count = self._configure_count
            limit_change_count = self._limit_change_count
        return {
            "configure_count": configure_count,
            "limit_change_count": limit_change_count,
            "chat": self._chat.snapshot(),
            "llm": self._llm.snapshot(),
            "embed": self._embed.snapshot(),
            "bg_embed": self._bg_embed.snapshot(),
            "bg_llm": self._bg_llm.snapshot(),
        }

    def chat_slot(self, wait_seconds: float = 2.0):
        return _Slot(self._chat, self.metrics, "chat", wait_seconds)

    def llm_slot(self, wait_seconds: float = 5.0):
        return _Slot(self._llm, self.metrics, "llm", wait_seconds)

    def embed_slot(self, wait_seconds: float = 5.0):
        return _Slot(self._embed, self.metrics, "embed", wait_seconds)

    def background_embed_slot(self):
        """Blocking slot for bulk indexing/reprocess embeddings.

        Background work waits for its dedicated pool instead of raising, so it
        never competes with the interactive embedding slots used by chat.
        """
        return _BlockingSlot(self._bg_embed)

    def background_llm_slot(self):
        """Blocking slot for background LLM work (Source Intelligence).

        Acquires the background reservation first, then a shared LLM slot, so
        total Ollama concurrency stays bounded and at least one LLM slot remains
        reachable by interactive chat generation.
        """
        return _NestedBlockingSlot(self._bg_llm, self._llm)


class _Slot:
    def __init__(
        self,
        gate: _AdmissionGate,
        metrics: PerformanceMetrics,
        kind: str,
        wait_seconds: float,
    ) -> None:
        self._gate = gate
        self._metrics = metrics
        self._kind = kind
        self._wait = wait_seconds
        self._acquired = False
        self.domain_id = gate.domain_id

    def __enter__(self) -> _Slot:
        if self._kind == "chat":
            with self._metrics._lock:
                self._metrics.queued_chat += 1
        if self._gate.acquire_timed(self._wait):
            self._acquired = True
            self.domain_id = self._gate.domain_id
            if self._kind == "chat":
                with self._metrics._lock:
                    self._metrics.queued_chat -= 1
                    self._metrics.active_chat += 1
            return self
        if self._kind == "chat":
            with self._metrics._lock:
                self._metrics.queued_chat -= 1
        raise OverloadedError()

    def __exit__(self, *args: object) -> None:
        if self._acquired:
            self._gate.release()
            if self._kind == "chat":
                with self._metrics._lock:
                    self._metrics.active_chat -= 1


class _BlockingSlot:
    """Acquire a gate, blocking until available (no overload error)."""

    def __init__(self, gate: _AdmissionGate) -> None:
        self._gate = gate
        self._acquired = False
        self.domain_id = gate.domain_id

    def __enter__(self) -> _BlockingSlot:
        self._gate.acquire_blocking()
        self._acquired = True
        self.domain_id = self._gate.domain_id
        return self

    def __exit__(self, *args: object) -> None:
        if self._acquired:
            self._gate.release()


class _NestedBlockingSlot:
    """Acquire an outer reservation then an inner shared gate (blocking).

    Releases in reverse order. Used so background LLM work reserves capacity but
    still counts against the shared LLM limit, leaving headroom for chat.
    """

    def __init__(self, outer: _AdmissionGate, inner: _AdmissionGate) -> None:
        self._outer = outer
        self._inner = inner
        self._outer_acquired = False
        self._inner_acquired = False

    def __enter__(self) -> _NestedBlockingSlot:
        self._outer.acquire_blocking()
        self._outer_acquired = True
        try:
            self._inner.acquire_blocking()
            self._inner_acquired = True
        except BaseException:
            self._outer.release()
            self._outer_acquired = False
            raise
        return self

    def __exit__(self, *args: object) -> None:
        if self._inner_acquired:
            self._inner.release()
        if self._outer_acquired:
            self._outer.release()


concurrency = ConcurrencyManager()
