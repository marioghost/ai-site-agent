"""Test database helpers (PostgreSQL only) — isolation-hardened.

Rules (post-incident):
- ``POSTGRES_TEST_URL`` is required for any DB-backed test helper.
- Never fall back to ``DATABASE_URL``.
- Reject a test DSN identical to the application ``DATABASE_URL``.
- ``make_engine(fresh=True)`` only on disposable DBs whose name matches
  ``*_test``, ``*_integration_test``, or ``*_migration_test``.
"""
from __future__ import annotations

import os
import re
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from app.core.database import Base
from app.core.db_extras import apply_fulltext_extras

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEST_DB = "ai_site_agent_migration_test"

_SAFE_TEST_DB_RE = re.compile(
    r"(_test|_integration_test|_migration_test)$",
    re.IGNORECASE,
)


class DatabaseIsolationError(RuntimeError):
    """Raised when a test would touch a non-isolated / application database."""


def _load_repo_env() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    for key, value in dotenv_values(env_path).items():
        if value is not None and key not in os.environ:
            os.environ[key] = value


_load_repo_env()


def is_usable_postgres_test_url(url: str | None) -> bool:
    """Return True when ``url`` looks like a real PostgreSQL DSN (not a doc placeholder)."""
    if not url or not url.strip():
        return False
    raw = url.strip()
    if raw in {"postgresql+psycopg://...", "postgresql://..."}:
        return False
    if "@.../" in raw or raw.endswith("@...") or raw.endswith("://..."):
        return False
    try:
        parsed = make_url(raw)
    except Exception:
        return False
    if not parsed.drivername.startswith("postgresql"):
        return False
    host = (parsed.host or "").strip()
    if not host or host == "...":
        return False
    database = (parsed.database or "").strip()
    if not database or database == "...":
        return False
    return True


def _identity(url: str) -> tuple[str, int | None, str, str | None]:
    parsed = make_url(url.strip())
    return (
        (parsed.host or "").lower(),
        parsed.port,
        (parsed.database or "").lower(),
        (parsed.username or "").lower() if parsed.username else None,
    )


def is_safe_test_database_name(database: str | None) -> bool:
    name = (database or "").strip()
    if not name:
        return False
    return bool(_SAFE_TEST_DB_RE.search(name))


def application_database_url() -> str | None:
    """Return configured application DATABASE_URL when usable (never used as test target)."""
    url = (os.environ.get("DATABASE_URL") or "").strip()
    return url if is_usable_postgres_test_url(url) else None


def resolve_postgres_test_url() -> str | None:
    """Resolve POSTGRES_TEST_URL only — no DATABASE_URL fallback."""
    explicit = (os.environ.get("POSTGRES_TEST_URL") or "").strip()
    if is_usable_postgres_test_url(explicit):
        return explicit
    return None


def assert_isolated_from_app_database(url: str) -> None:
    """Fail if ``url`` targets the same DB identity as DATABASE_URL."""
    app = application_database_url()
    if not app:
        return
    if _identity(url) == _identity(app):
        raise DatabaseIsolationError(
            "POSTGRES_TEST_URL must not point at the application DATABASE_URL "
            f"(database={make_url(url).database!r})."
        )


def assert_destructive_database_allowed(url: str) -> None:
    """Fail unless database name is a disposable test DB."""
    parsed = make_url(url)
    name = parsed.database or ""
    if not is_safe_test_database_name(name):
        raise DatabaseIsolationError(
            "Destructive test operations require a disposable database name ending in "
            f"_test / _integration_test / _migration_test (got {name!r})."
        )


def derive_migration_test_url(database_url: str) -> str:
    """Derive a disposable migration-test DSN from credentials (different DB name)."""
    test_db = os.environ.get("POSTGRES_TEST_DB", DEFAULT_TEST_DB)
    if not is_safe_test_database_name(test_db):
        raise DatabaseIsolationError(
            f"POSTGRES_TEST_DB must be a disposable test name (got {test_db!r})."
        )
    return make_url(database_url.strip()).set(database=test_db).render_as_string(
        hide_password=False
    )


POSTGRES_TEST_URL = resolve_postgres_test_url()


def _ensure_test_database(url: str) -> None:
    assert_isolated_from_app_database(url)
    assert_destructive_database_allowed(url)
    parsed = make_url(url)
    db_name = parsed.database
    if not db_name:
        return
    admin = parsed.set(database="postgres")
    engine = create_engine(admin, isolation_level="AUTOCOMMIT", future=True)
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        engine.dispose()


def ensure_postgres_test_database(url: str) -> None:
    """Create the target database when missing (optional; needs CREATEDB)."""
    if not is_usable_postgres_test_url(url):
        return
    assert_isolated_from_app_database(url)
    assert_destructive_database_allowed(url)
    _ensure_test_database(url)


def postgres_test_url_or_skip() -> str:
    """Return isolated test DB URL or skip the current test."""
    url = resolve_postgres_test_url()
    if not url:
        pytest.skip(
            "requires POSTGRES_TEST_URL (disposable PostgreSQL test database); "
            "DATABASE_URL fallback is disabled"
        )
    try:
        assert_isolated_from_app_database(url)
    except DatabaseIsolationError as exc:
        pytest.fail(str(exc))
    ensure_postgres_test_database(url)
    return url


def ensure_alembic_head() -> None:
    """Apply pending Alembic migrations on the isolated test database."""
    url = postgres_test_url_or_skip()
    assert_destructive_database_allowed(url)
    alembic = BACKEND_ROOT / ".venv" / "bin" / "alembic"
    if not alembic.is_file():
        pytest.skip("alembic not available in backend venv")
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    subprocess.run(
        [str(alembic), "upgrade", "head"],
        cwd=str(BACKEND_ROOT),
        env=env,
        check=True,
        capture_output=True,
    )


def make_engine(*, fresh: bool = True) -> Engine:
    """Return an engine bound to the isolated test PostgreSQL DB.

    ``fresh=True`` drops and recreates all tables — refused unless the database
    name matches the disposable test suffix rules.
    ``fresh=False`` still requires an isolated test DSN (never the app DB).
    """
    url = postgres_test_url_or_skip()
    assert_isolated_from_app_database(url)
    if fresh:
        assert_destructive_database_allowed(url)
    # Ensure all ORM tables (including Knowledge Understanding) are registered.
    from app import models as _models  # noqa: F401

    engine = create_engine(url, future=True)
    if fresh:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with engine.begin() as conn:
            apply_fulltext_extras(conn)
    else:
        # Non-destructive path still must not target the application DB.
        if not is_safe_test_database_name(make_url(url).database):
            raise DatabaseIsolationError(
                "Non-destructive DB tests still require a disposable test database name."
            )
        Base.metadata.create_all(bind=engine, checkfirst=True)
    return engine


def new_test_run_id() -> str:
    return uuid.uuid4().hex[:12]


def ensure_source_ids(
    session,
    *source_ids: int,
    test_run_id: str | None = None,
) -> str:
    """Insert missing ``sources`` rows for hardcoded fixture source_ids.

    Only allowed against an isolated test database. Rows are tagged with
    ``test_run_id`` in URL/title for owned cleanup.
    """
    bind = session.get_bind()
    db_name = getattr(getattr(bind, "url", None), "database", None)
    if not is_safe_test_database_name(db_name):
        raise DatabaseIsolationError(
            f"ensure_source_ids refused: session DB {db_name!r} is not a disposable test DB"
        )

    from app.models.source import Source

    run_id = test_run_id or new_test_run_id()
    needed = {int(sid) for sid in source_ids if sid is not None}
    if not needed:
        return run_id
    existing = {
        row[0]
        for row in session.query(Source.id).filter(Source.id.in_(needed)).all()
    }
    missing = sorted(needed - existing)
    if not missing:
        return run_id
    for sid in missing:
        session.add(
            Source(
                id=sid,
                source_type="page",
                url=f"https://fixture.example/run-{run_id}/src-{sid}",
                title=f"Fixture source {sid} [test_run={run_id}]",
            )
        )
    session.flush()
    session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('sources','id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM sources))"
        )
    )
    return run_id


def cleanup_sources_for_test_run(session, test_run_id: str) -> int:
    """Delete only sources owned by ``test_run_id``."""
    from app.models.source import Source

    if not test_run_id:
        return 0
    marker = f"test_run={test_run_id}"
    rows = (
        session.query(Source)
        .filter(Source.title.contains(marker))
        .all()
    )
    count = len(rows)
    for row in rows:
        session.delete(row)
    session.flush()
    return count
