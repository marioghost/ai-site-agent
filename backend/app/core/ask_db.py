"""Ask-path DB session helpers (RFC-100 Step 066 remediation).

Short-lived sessions and park/unpark around LLM waits so connections return
to the pool during model inference / SSE generation.
"""
from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.orm import Session

from app.core.concurrency import OverloadedError
from app.core.database import SessionLocal, pool_diagnostics
from app.core.logging import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_pool_timeout_count = 0
_park_count = 0
_unpark_count = 0
_cancel_cleanup_count = 0


def pool_timeout_count() -> int:
    with _lock:
        return _pool_timeout_count


def park_count() -> int:
    with _lock:
        return _park_count


def unpark_count() -> int:
    with _lock:
        return _unpark_count


def cancel_cleanup_count() -> int:
    with _lock:
        return _cancel_cleanup_count


def record_cancel_cleanup() -> None:
    global _cancel_cleanup_count
    with _lock:
        _cancel_cleanup_count += 1


def is_pool_timeout(exc: BaseException) -> bool:
    """True when SQLAlchemy could not check out a pooled connection in time."""
    if isinstance(exc, SATimeoutError):
        return True
    text = f"{type(exc).__name__}: {exc}".lower()
    return "queuepool" in text and "timeout" in text


def record_pool_timeout() -> None:
    global _pool_timeout_count
    with _lock:
        _pool_timeout_count += 1
    logger.warning(
        "ask_db_pool_timeout pool=%s",
        pool_diagnostics(),
    )


def raise_capacity_overload(exc: BaseException | None = None) -> None:
    """Map pool exhaustion to the same OverloadedError used for chat admission."""
    record_pool_timeout()
    raise OverloadedError() from exc


@contextmanager
def ask_session(*, commit: bool = True) -> Generator[Session, None, None]:
    """Operation-scoped Ask session — always closed (returns connection to pool)."""
    db = SessionLocal()
    try:
        yield db
        if commit:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def close_quietly(db: Session | None) -> None:
    if db is None:
        return
    try:
        db.close()
    except Exception:  # noqa: BLE001
        pass


def park_session_for_llm(owner: object) -> None:
    """Close owner.db / owner._db so the pool connection is released during LLM wait."""
    global _park_count
    db = getattr(owner, "db", None)
    if db is None:
        db = getattr(owner, "_db", None)
    if db is None:
        return
    try:
        db.commit()
    except Exception:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
    close_quietly(db)
    if hasattr(owner, "db"):
        owner.db = None  # type: ignore[attr-defined]
    if hasattr(owner, "_db"):
        owner._db = None  # type: ignore[attr-defined]
    _rebind_cache_services(owner, None)
    with _lock:
        _park_count += 1
    logger.info("ask_db_parked_for_llm pool=%s", pool_diagnostics())


def unpark_session_after_llm(owner: object) -> Session:
    """Open a fresh session on owner after LLM wait for persist/finalize."""
    global _unpark_count
    db = SessionLocal()
    if hasattr(owner, "db"):
        owner.db = db  # type: ignore[attr-defined]
    if hasattr(owner, "_db"):
        owner._db = db  # type: ignore[attr-defined]
    _rebind_cache_services(owner, db)
    with _lock:
        _unpark_count += 1
    logger.info("ask_db_unparked_after_llm pool=%s", pool_diagnostics())
    return db


def _rebind_cache_services(owner: object, db: Session | None) -> None:
    """Refresh RagService cache helpers that capture a Session at init."""
    settings = getattr(owner, "settings", None)
    if settings is None or not hasattr(owner, "retrieval_cache"):
        return
    if db is None:
        return
    from app.services.answer_cache_service import AnswerCacheService
    from app.services.retrieval_cache_service import RetrievalCacheService

    owner.retrieval_cache = RetrievalCacheService(db)  # type: ignore[attr-defined]
    owner.answer_cache = AnswerCacheService(db, settings)  # type: ignore[attr-defined]


def active_db(owner: object) -> Session | None:
    db = getattr(owner, "db", None)
    if db is not None:
        return db
    return getattr(owner, "_db", None)
