"""Test database helpers (PostgreSQL only).

Unit tests that need a real schema build an engine against ``POSTGRES_TEST_URL``
and (re)create a fresh schema. When the variable is not set the test is skipped
— there is no SQLite fallback.

When ``POSTGRES_TEST_URL`` is unset, falls back to ``DATABASE_URL`` from repo ``.env``.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from app.core.database import Base
from app.core.db_extras import apply_fulltext_extras

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEST_DB = "ai_site_agent_migration_test"


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


def derive_migration_test_url(database_url: str) -> str:
    test_db = os.environ.get("POSTGRES_TEST_DB", DEFAULT_TEST_DB)
    return make_url(database_url.strip()).set(database=test_db).render_as_string(
        hide_password=False
    )


def resolve_postgres_test_url() -> str | None:
    explicit = (os.environ.get("POSTGRES_TEST_URL") or "").strip()
    if is_usable_postgres_test_url(explicit):
        return explicit
    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    if is_usable_postgres_test_url(database_url):
        return database_url
    return None


POSTGRES_TEST_URL = resolve_postgres_test_url()


def _ensure_test_database(url: str) -> None:
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
    test_db = os.environ.get("POSTGRES_TEST_DB", "").strip()
    if not test_db:
        return
    _ensure_test_database(url)


def postgres_test_url_or_skip() -> str:
    """Return a validated test DB URL or skip the current test."""
    url = resolve_postgres_test_url()
    if not url:
        pytest.skip(
            "requires POSTGRES_TEST_URL or DATABASE_URL in repo .env "
            "(PostgreSQL test database)"
        )
    ensure_postgres_test_database(url)
    return url


def ensure_alembic_head() -> None:
    """Apply pending Alembic migrations on the test database."""
    url = resolve_postgres_test_url()
    if not url:
        pytest.skip("requires DATABASE_URL for alembic migrations")
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
    """Return an engine bound to the test PostgreSQL DB.

    ``fresh=True`` (default) drops and recreates all tables — use only on disposable DBs.
    ``fresh=False`` ensures schema exists without destroying data (shared dev DB).
    """
    url = postgres_test_url_or_skip()
    engine = create_engine(url, future=True)
    if fresh:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with engine.begin() as conn:
            apply_fulltext_extras(conn)
    else:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    return engine


def ensure_source_ids(session, *source_ids: int) -> None:
    """Insert missing ``sources`` rows for hardcoded fixture source_ids.

    Shared PostgreSQL test DBs may lack rows after a wipe; observation_ref FKs
    require sources to exist. Idempotent — skips ids already present.
    """
    from app.models.source import Source

    needed = {int(sid) for sid in source_ids if sid is not None}
    if not needed:
        return
    existing = {
        row[0]
        for row in session.query(Source.id).filter(Source.id.in_(needed)).all()
    }
    missing = sorted(needed - existing)
    if not missing:
        return
    for sid in missing:
        session.add(
            Source(
                id=sid,
                source_type="page",
                url=f"https://fixture.example/src-{sid}",
                title=f"Fixture source {sid}",
            )
        )
    session.flush()
    # Keep serial ahead of explicitly assigned ids.
    session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('sources','id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM sources))"
        )
    )
