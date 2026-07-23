"""Alembic migration environment (PostgreSQL only).

The database URL is taken from the application configuration (``DATABASE_URL``)
unless it has been set explicitly on the Alembic config (e.g. by tooling that
targets a specific database).
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the backend package is importable when Alembic runs standalone.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_config  # noqa: E402
from app.core.database import Base  # noqa: E402
from app import models  # noqa: E402,F401  (register all models on Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Resolve the database URL: prefer an explicitly-set value, else app config.
_url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL")
if not _url:
    _url = get_config().database_url
if not _url or not _url.startswith("postgresql"):
    raise RuntimeError(
        "Alembic requires a PostgreSQL DATABASE_URL "
        "(e.g. postgresql+psycopg://user:pass@host:5432/db)."
    )
config.set_main_option("sqlalchemy.url", _url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
