"""Database engine, session factory and Base declarative class.

PostgreSQL-only. There is no SQLite support, no runtime auto-create and no
"light migration" column patching — the schema is owned by Alembic migrations
(see ``backend/migrations``). Startup validates the connection and that the
database is migrated to the latest Alembic revision; otherwise it fails fast.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import ConfigError, get_config
from app.core.logging import get_logger

logger = get_logger(__name__)

_config = get_config()

# Refuse to build an engine for anything other than PostgreSQL.
_config.validate_database_url()

engine = create_engine(
    _config.database_url,
    pool_size=_config.db_pool_size,
    max_overflow=_config.db_max_overflow,
    pool_timeout=_config.db_pool_timeout_seconds,
    pool_recycle=_config.db_pool_recycle_seconds,
    pool_pre_ping=_config.db_pool_pre_ping,
    future=True,
)

from app.core.slow_query import install_slow_query_logging  # noqa: E402

install_slow_query_logging(engine, float(_config.db_slow_query_ms))

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Startup validation (no auto-create; Alembic owns the schema)
# ---------------------------------------------------------------------------
def pool_diagnostics() -> dict[str, int | str]:
    """Return connection pool usage for health/admin endpoints."""
    try:
        pool = engine.pool
        return {
            "size": int(pool.size()),  # type: ignore[attr-defined]
            "checked_out": int(pool.checkedout()),  # type: ignore[attr-defined]
            "overflow": int(pool.overflow()),  # type: ignore[attr-defined]
            "checked_in": int(pool.checkedin()),  # type: ignore[attr-defined]
        }
    except Exception:  # noqa: BLE001
        return {}


def check_connection() -> None:
    """Verify the database is reachable. Raises on failure (fail fast)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise ConfigError(
            f"Cannot connect to PostgreSQL at the configured DATABASE_URL: {exc}\n"
            "Check that PostgreSQL is running and the credentials/database exist."
        ) from exc


def current_db_revision() -> str | None:
    """Return the Alembic revision stamped in the database, or None."""
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).first()
            return row[0] if row else None
    except Exception:  # noqa: BLE001
        return None


def expected_head_revision() -> str | None:
    """Return the latest Alembic head revision defined in code, or None."""
    try:
        from alembic.script import ScriptDirectory

        from app.core.alembic_config import make_alembic_config

        cfg = make_alembic_config(_config.database_url)
        script = ScriptDirectory.from_config(cfg)
        return script.get_current_head()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not resolve Alembic head revision: %s", exc)
        return None


def check_migrations() -> None:
    """Fail fast unless the database is migrated to the latest Alembic head."""
    head = expected_head_revision()
    current = current_db_revision()
    if head is None:
        logger.warning(
            "No Alembic head revision found in code — skipping migration check"
        )
        return
    if current is None:
        raise ConfigError(
            "Database schema is not initialised (no alembic_version table).\n"
            "Run migrations before starting the backend:\n"
            "  cd backend && alembic upgrade head"
        )
    if current != head:
        raise ConfigError(
            f"Database schema is out of date (at {current!r}, expected {head!r}).\n"
            "Run pending migrations:\n"
            "  cd backend && alembic upgrade head"
        )


def verify_database() -> None:
    """Run all startup database checks in order. Raises ``ConfigError``."""
    _config.validate_database_url()
    check_connection()
    check_migrations()


# ---------------------------------------------------------------------------
# Data bootstrap (runs after the schema exists / is verified)
# ---------------------------------------------------------------------------
def seed_default_admin() -> None:
    """Create the default admin account when no users exist."""
    from app.repositories.user_repository import UserRepository

    db = SessionLocal()
    try:
        created = UserRepository(db).seed_default_admin()
        if created:
            logger.info("Created default admin user (username=admin)")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Default admin seed skipped: %s", exc)
    finally:
        db.close()


def backfill_source_scheduling_metadata() -> None:
    """Initialize scheduling timestamps for sources created before the planner."""
    from datetime import timedelta

    from sqlalchemy import select

    from app.models.source import Source
    from app.utils.time_utils import utcnow

    db = SessionLocal()
    try:
        now = utcnow()
        default_hours = 168
        rows = list(db.scalars(select(Source)).all())
        changed = 0
        for source in rows:
            touched = False
            if source.first_seen_at is None:
                source.first_seen_at = source.created_at or now
                touched = True
            if source.last_seen_at is None:
                source.last_seen_at = source.updated_at or source.first_seen_at or now
                touched = True
            if source.next_refresh_at is None:
                if source.status == "indexed" and source.indexed_at:
                    source.next_refresh_at = source.indexed_at + timedelta(hours=default_hours)
                elif source.status in {"pending", "error", "skipped"}:
                    source.next_refresh_at = now
                touched = True
            if touched:
                changed += 1
        if changed:
            db.commit()
            logger.info("Backfilled scheduling metadata for %d source(s)", changed)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Source scheduling backfill skipped: %s", exc)
        db.rollback()
    finally:
        db.close()


def purge_poisoned_caches() -> None:
    """Remove empty retrieval cache and fallback answer cache on startup."""
    from app.repositories.settings_repository import DEFAULT_FALLBACK, SettingsRepository
    from app.services.cache_invalidation_service import CacheInvalidationService

    db = SessionLocal()
    try:
        settings = SettingsRepository(db).get_or_create()
        fallback = settings.fallback_answer or DEFAULT_FALLBACK
        stats = CacheInvalidationService.purge_poisoned_entries(
            db, fallback_answer=fallback
        )
        if any(stats.values()):
            logger.info("Startup cache purge: %s", stats)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Startup cache purge skipped: %s", exc)
        db.rollback()
    finally:
        db.close()


def bootstrap_data() -> None:
    """Run idempotent data bootstrap after the schema is verified."""
    backfill_source_scheduling_metadata()
    seed_default_admin()
    purge_poisoned_caches()


def init_db() -> None:
    """Create the schema directly from ORM metadata (tests / local dev only).

    Production uses Alembic migrations (``alembic upgrade head``) — this helper
    exists so the test suite and quick local setups can build a fresh schema
    against a (PostgreSQL) database without running the migration chain. It also
    applies the full-text ``search_vector`` extras and seeds the default admin.
    """
    from app import models  # noqa: F401
    from app.core.db_extras import apply_fulltext_extras

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        apply_fulltext_extras(conn)
    backfill_source_scheduling_metadata()
    seed_default_admin()
    purge_poisoned_caches()
