"""Tests for chat session persistence API."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_session_and_list(client: TestClient, auth_headers: dict[str, str]):
    created = client.post(
        "/api/chat/sessions",
        json={"close_current_session_id": None},
        headers=auth_headers,
    )
    assert created.status_code == 200
    sid = created.json()["session_id"]
    assert sid

    listed = client.get("/api/chat/sessions", headers=auth_headers)
    assert listed.status_code == 200
    ids = [s["session_id"] for s in listed.json()["items"]]
    assert sid in ids


def test_clear_session(client: TestClient, auth_headers: dict[str, str]):
    sid = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]
    cleared = client.post(f"/api/chat/sessions/{sid}/clear", headers=auth_headers)
    assert cleared.status_code == 200
    assert cleared.json()["status"] == "cleared"
    assert cleared.json()["messages"] == []


def test_new_session_closes_previous(client: TestClient, auth_headers: dict[str, str]):
    first = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]
    second = client.post(
        "/api/chat/sessions",
        json={"close_current_session_id": first},
        headers=auth_headers,
    ).json()["session_id"]
    assert first != second
    closed = client.get(f"/api/chat/sessions/{first}", headers=auth_headers).json()
    assert closed["status"] == "closed"
