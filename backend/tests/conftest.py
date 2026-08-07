"""Pytest configuration (PostgreSQL isolation-hardened).

DB-backed tests require an explicit disposable ``POSTGRES_TEST_URL``.
There is no fallback to ``DATABASE_URL``.
"""
from __future__ import annotations

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tests._dbutil import (  # noqa: E402
    is_usable_postgres_test_url,
    resolve_postgres_test_url,
)

POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL")
RESOLVED_POSTGRES_TEST_URL = resolve_postgres_test_url()
POSTGRES_TEST_AVAILABLE = is_usable_postgres_test_url(RESOLVED_POSTGRES_TEST_URL)

# App import may need a DSN shape; never silently retarget app DATABASE_URL to tests.
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = (
        RESOLVED_POSTGRES_TEST_URL
        or "postgresql+psycopg://localhost:5432/ai_site_agent_test"
    )

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402


def pytest_collection_modifyitems(config, items):
    if POSTGRES_TEST_AVAILABLE:
        return
    skip = pytest.mark.skip(
        reason=(
            "requires disposable POSTGRES_TEST_URL "
            "(*_test / *_integration_test / *_migration_test); "
            "DATABASE_URL fallback disabled"
        )
    )
    for item in items:
        # Pure unit tests that never open Postgres keep running.
        if "unit" in item.keywords and "integration" not in item.keywords:
            # Still skip if the test module is known to call make_engine.
            path = str(getattr(item, "fspath", "") or "")
            if any(
                name in path
                for name in (
                    "test_boilerplate_retrieval.py",
                    "test_retrieval_hybrid.py",
                    "test_memory_version_service.py",
                    "test_source_intelligence",
                    "test_cache_safety.py",
                    "test_analytics_service.py",
                    "test_datetime_cache.py",
                    "test_epistemic_",
                    "test_tension_",
                    "test_understanding_tensions",
                    "test_understanding_builder",
                    "test_operational_metrics.py",
                )
            ):
                # These open Postgres via make_engine; skip without isolated URL.
                item.add_marker(skip)
            continue
        item.add_marker(skip)


@pytest.fixture()
def client() -> TestClient:
    init_db()
    return TestClient(app)


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "фвьшт"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture()
def auth_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}
