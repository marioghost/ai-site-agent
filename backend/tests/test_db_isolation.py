"""Isolation guards — prove tests cannot target the application database."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from sqlalchemy.engine import make_url

from tests._dbutil import (
    DatabaseIsolationError,
    assert_destructive_database_allowed,
    assert_isolated_from_app_database,
    ensure_source_ids,
    is_safe_test_database_name,
    resolve_postgres_test_url,
)


@pytest.mark.unit
def test_resolve_does_not_fall_back_to_database_url(monkeypatch):
    monkeypatch.delenv("POSTGRES_TEST_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://ai_agent:x@localhost:5432/ai_site_agent",
    )
    # Re-import resolution uses os.environ live — call function directly.
    assert resolve_postgres_test_url() is None


@pytest.mark.unit
def test_identical_app_url_rejected(monkeypatch):
    app = "postgresql+psycopg://ai_agent:secret@localhost:5432/ai_site_agent"
    monkeypatch.setenv("DATABASE_URL", app)
    monkeypatch.setenv("POSTGRES_TEST_URL", app)
    with pytest.raises(DatabaseIsolationError):
        assert_isolated_from_app_database(app)


@pytest.mark.unit
def test_fresh_true_refuses_application_db_name():
    with pytest.raises(DatabaseIsolationError):
        assert_destructive_database_allowed(
            "postgresql+psycopg://u:p@localhost:5432/ai_site_agent"
        )


@pytest.mark.unit
def test_fresh_true_allows_test_suffixes():
    for name in (
        "ai_site_agent_test",
        "ai_site_agent_integration_test",
        "ai_site_agent_migration_test",
    ):
        assert is_safe_test_database_name(name)
        assert_destructive_database_allowed(
            f"postgresql+psycopg://u:p@localhost:5432/{name}"
        )


@pytest.mark.unit
def test_ensure_source_ids_refuses_app_session_bind():
    session = MagicMock()
    session.get_bind.return_value.url = make_url(
        "postgresql+psycopg://u:p@localhost:5432/ai_site_agent"
    )
    with pytest.raises(DatabaseIsolationError):
        ensure_source_ids(session, 1)


@pytest.mark.unit
def test_missing_postgres_test_url_is_not_silently_app(monkeypatch):
    monkeypatch.delenv("POSTGRES_TEST_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://ai_agent:x@127.0.0.1:5432/ai_site_agent",
    )
    assert os.environ.get("DATABASE_URL")
    assert resolve_postgres_test_url() is None
