"""Short-lived database session helpers for workers and background tasks.

Each worker thread must open and close its own session. Never share ORM
objects or sessions across threads.
"""
from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.core.database import SessionLocal


@contextmanager
def worker_session() -> Generator[Session, None, None]:
    """Yield a session for a worker batch; rollback on error, always close."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def read_session() -> Generator[Session, None, None]:
    """Read-only session scope (no commit on success)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
