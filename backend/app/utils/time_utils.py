"""Time helpers — naive UTC for SQLite MVP compatibility."""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """Current UTC time as a naive datetime (no tzinfo)."""
    return datetime.utcnow()  # noqa: DTZ003 — SQLite stores naive UTC


def utcnow() -> datetime:
    """Current UTC time as naive datetime (SQLite-compatible)."""
    return utcnow_naive()


def to_naive_utc(value: datetime | None) -> datetime | None:
    """Normalize aware or naive datetimes to naive UTC for safe comparison."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def is_expired(expires_at: datetime | None, *, now: datetime | None = None) -> bool:
    """True when ``expires_at`` is in the past (handles naive/aware mix safely)."""
    exp = to_naive_utc(expires_at)
    if exp is None:
        return False
    current = to_naive_utc(now) if now is not None else utcnow_naive()
    return exp < current


def isoformat_now() -> str:
    """Return current naive UTC time as ISO-8601 with Z suffix."""
    return utcnow_naive().isoformat() + "Z"
