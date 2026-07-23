"""Optional slow-query logging for PostgreSQL via SQLAlchemy events."""
from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.core.logging import get_logger

logger = get_logger(__name__)

_SENSITIVE = re.compile(
    r"(password|secret|token|api_key|authorization)\s*=\s*['\"]?[^'\"&\s]+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SlowQueryRecord:
    duration_ms: float
    statement: str
    context: str | None = None


_recent: deque[SlowQueryRecord] = deque(maxlen=50)
_lock = Lock()
_installed = False


def _sanitize(statement: str) -> str:
    text = (statement or "").strip().replace("\n", " ")
    if len(text) > 500:
        text = text[:500] + "…"
    return _SENSITIVE.sub(r"\1=***", text)


def install_slow_query_logging(engine: Engine, threshold_ms: float) -> None:
    """Attach before/after cursor listeners once per process."""
    global _installed  # noqa: PLW0603
    if _installed or threshold_ms <= 0:
        return
    threshold = threshold_ms / 1000.0

    @event.listens_for(engine, "before_cursor_execute")
    def _before(
        conn, cursor, statement, parameters, context, executemany
    ):  # noqa: ARG001
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after(
        conn, cursor, statement, parameters, context, executemany
    ):  # noqa: ARG001
        started = conn.info.get("query_start_time", [])
        if not started:
            return
        elapsed = time.perf_counter() - started.pop()
        if elapsed < threshold:
            return
        duration_ms = round(elapsed * 1000, 2)
        safe_stmt = _sanitize(statement)
        ctx = None
        if context is not None:
            ctx = getattr(context, "execution_options", {}).get("slow_query_context")
        record = SlowQueryRecord(
            duration_ms=duration_ms, statement=safe_stmt, context=ctx
        )
        with _lock:
            _recent.append(record)
        logger.warning(
            "Slow query %.1f ms%s: %s",
            duration_ms,
            f" [{ctx}]" if ctx else "",
            safe_stmt,
        )

    _installed = True


def recent_slow_queries(limit: int = 10) -> list[dict]:
    with _lock:
        rows = list(_recent)[-limit:]
    return [
        {
            "duration_ms": r.duration_ms,
            "statement": r.statement,
            "context": r.context,
        }
        for r in rows
    ]
