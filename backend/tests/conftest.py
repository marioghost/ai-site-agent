"""Pytest configuration (PostgreSQL only).

DB-backed tests require a PostgreSQL database supplied via ``POSTGRES_TEST_URL``.
When it is not set the whole suite is skipped (there is no SQLite fallback).

``DATABASE_URL`` is set from ``POSTGRES_TEST_URL`` before importing the app so
the engine is built against the test database. A scheme-valid placeholder is
used purely so imports succeed during collection when the suite will be skipped.
"""
from __future__ import annotations

import os
import sys

# Allow `import app...` when running pytest from the repo root or backend dir.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL")
from tests._dbutil import is_usable_postgres_test_url, resolve_postgres_test_url  # noqa: E402

RESOLVED_POSTGRES_TEST_URL = resolve_postgres_test_url()
POSTGRES_TEST_AVAILABLE = is_usable_postgres_test_url(RESOLVED_POSTGRES_TEST_URL)
# Prefer repo .env DATABASE_URL (loaded in _dbutil) over a passwordless placeholder.
os.environ["DATABASE_URL"] = (
    RESOLVED_POSTGRES_TEST_URL
    or os.environ.get("DATABASE_URL")
    or "postgresql+psycopg://localhost:5432/ai_site_agent_test"
)
if RESOLVED_POSTGRES_TEST_URL:
    os.environ.setdefault("POSTGRES_TEST_URL", RESOLVED_POSTGRES_TEST_URL)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402


def pytest_collection_modifyitems(config, items):
    if POSTGRES_TEST_AVAILABLE:
        return
    skip = pytest.mark.skip(
        reason="requires a valid POSTGRES_TEST_URL (PostgreSQL test database)"
    )
    for item in items:
        if "unit" in item.keywords:
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
def auth_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}
