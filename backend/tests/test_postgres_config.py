"""PostgreSQL-only configuration validation tests."""
from __future__ import annotations

import pytest

from app.core.config import AppConfig, ConfigError

pytestmark = pytest.mark.unit


def test_missing_database_url_fails():
    cfg = AppConfig(DATABASE_URL="")
    with pytest.raises(ConfigError, match="DATABASE_URL is not set"):
        cfg.validate_database_url()


def test_non_postgresql_url_fails():
    cfg = AppConfig(DATABASE_URL="sqlite:///tmp/test.db")
    with pytest.raises(ConfigError, match="PostgreSQL URL"):
        cfg.validate_database_url()


def test_postgresql_url_accepted():
    cfg = AppConfig(DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/db")
    cfg.validate_database_url()


def test_pool_settings_defaults():
    cfg = AppConfig(
        DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/db",
        DB_POOL_SIZE=10,
        DB_MAX_OVERFLOW=20,
        DB_POOL_TIMEOUT_SECONDS=30,
    )
    assert cfg.db_pool_size == 10
    assert cfg.db_max_overflow == 20
    assert cfg.db_pool_timeout_seconds == 30
