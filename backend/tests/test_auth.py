"""Authentication tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.repositories.user_repository import UserRepository


def test_login_default_admin(client: TestClient):
    res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "фвьшт"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "admin"
    assert body["user"]["role"] == "admin"
    assert "password" not in body["user"]


def test_login_invalid_credentials(client: TestClient):
    res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert res.status_code == 401


def test_protected_settings_requires_auth(client: TestClient):
    res = client.get("/api/settings")
    assert res.status_code == 401


def test_settings_with_token(client: TestClient, admin_token: str):
    res = client.get(
        "/api/settings",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200


def test_user_management_admin_only(client: TestClient, admin_token: str):
    res = client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    users = res.json()
    assert any(u["username"] == "admin" for u in users)


def test_seed_does_not_reset_existing_admin(client: TestClient):
    db = SessionLocal()
    try:
        repo = UserRepository(db)
        admin = repo.get_by_username("admin")
        assert admin is not None
        old_hash = admin.password_hash
        repo.seed_default_admin()
        db.refresh(admin)
        assert admin.password_hash == old_hash
    finally:
        db.close()
