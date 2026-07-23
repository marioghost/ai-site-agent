"""Helpers for locating and building the Alembic configuration.

Centralised so the runtime (startup migration checks) and CLI tooling
(maintenance, deploy) resolve the same ``alembic.ini`` / migrations directory.
"""
from __future__ import annotations

from pathlib import Path


def backend_dir() -> Path:
    """Return the backend project root (where ``alembic.ini`` lives)."""
    # app/core/alembic_config.py -> app/core -> app -> backend
    return Path(__file__).resolve().parents[2]


def alembic_ini_path() -> Path:
    return backend_dir() / "alembic.ini"


def migrations_path() -> Path:
    return backend_dir() / "migrations"


def make_alembic_config(database_url: str | None = None):
    """Build an Alembic ``Config`` pointed at this project's migrations.

    If ``database_url`` is provided it overrides ``sqlalchemy.url`` so callers
    can run migrations against an explicit target.
    """
    from alembic.config import Config

    cfg = Config(str(alembic_ini_path()))
    cfg.set_main_option("script_location", str(migrations_path()))
    if database_url:
        cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def upgrade_to_head(database_url: str | None = None) -> None:
    """Run ``alembic upgrade head`` programmatically."""
    from alembic import command

    from app.core.config import get_config

    url = database_url or get_config().database_url
    command.upgrade(make_alembic_config(url), "head")
