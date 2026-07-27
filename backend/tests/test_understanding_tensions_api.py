"""RFC-100 Step 035 — GET /api/understanding/tensions (admin, read-only)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.main import app
from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.models.source import Source
from app.services.tension_surfacing import (
    TENSION_CONFLICT,
    TENSION_SUPPORT_DEFICIT,
    TensionView,
)

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
NOW = datetime.now(timezone.utc)
ENDPOINT = "/api/understanding/tensions"


def _token() -> str:
    return uuid.uuid4().hex[:12]


def _admin_client(db_session) -> TestClient:
    def override_admin():
        return MagicMock(role="admin", username="admin")

    def override_db():
        yield db_session

    app.dependency_overrides[require_admin] = override_admin
    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _session():
    from tests._dbutil import make_engine

    engine = make_engine(fresh=False)
    session = sessionmaker(bind=engine)()
    return session, engine


@pytest.mark.unit
def test_tensions_requires_auth():
    client = TestClient(app)
    res = client.get(ENDPOINT)
    assert res.status_code == 401


@pytest.mark.unit
def test_tensions_requires_admin_role():
    viewer = MagicMock(role="viewer", is_active=True, username="viewer")
    app.dependency_overrides[get_current_user] = lambda: viewer
    app.dependency_overrides[get_db] = lambda: iter([MagicMock()])
    try:
        client = TestClient(app)
        res = client.get(ENDPOINT, headers={"Authorization": "Bearer fake-token"})
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
def test_tensions_empty_memory_returns_empty_page(monkeypatch):
    class EmptyMemory:
        def list_claims(self, **kwargs):
            return [], 0

    class EmptySurfacing:
        def __init__(self, memory):
            self._memory = memory

        def surface_tensions(self, **kwargs):
            return []

    monkeypatch.setattr(
        "app.api.understanding.EpistemicMemoryService",
        lambda db: EmptyMemory(),
    )
    monkeypatch.setattr(
        "app.api.understanding.TensionSurfacingService",
        EmptySurfacing,
    )
    app.dependency_overrides[require_admin] = lambda: MagicMock(role="admin")
    app.dependency_overrides[get_db] = lambda: iter([MagicMock()])
    try:
        client = TestClient(app)
        res = client.get(ENDPOINT, params={"page": 1, "page_size": 10})
        assert res.status_code == 200
        body = res.json()
        assert body == {"items": [], "total": 0, "page": 1, "page_size": 10}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
def test_tensions_support_deficit_and_provenance(monkeypatch):
    """Use a scoped claim scan so shared-DB claim volume cannot hide the fixture."""
    session, engine = _session()
    client = _admin_client(session)
    try:
        token = _token()
        claim = EpistemicClaim(
            proposition=f"API support deficit fixture {token}",
            attributed_to="fixture",
            provenance_kind="test",
            epistemic_status="proposal",
        )
        session.add(claim)
        session.commit()
        session.refresh(claim)

        from app.services.epistemic_memory import EpistemicMemoryService

        real_list = EpistemicMemoryService.list_claims

        def _scoped_list(self, **kwargs):
            # Ensure the fixture claim is always in the scanned window.
            claims, total = real_list(self, **kwargs)
            ours = next((c for c in claims if c.id == claim.id), None)
            if ours is None:
                from app.services.epistemic_memory.epistemic_memory_service import (
                    _claim_to_view,
                )

                row = session.get(EpistemicClaim, claim.id)
                if row is not None:
                    claims = [_claim_to_view(row), *claims]
            return claims, total

        monkeypatch.setattr(EpistemicMemoryService, "list_claims", _scoped_list)

        res = client.get(ENDPOINT, params={"page": 1, "page_size": 200, "claim_limit": 500})
        assert res.status_code == 200
        body = res.json()
        deficits = [
            item
            for item in body["items"]
            if item["tension_type"] == TENSION_SUPPORT_DEFICIT
            and claim.id in item["claim_ids"]
        ]
        assert len(deficits) == 1
        assert "Possible support deficit" in deficits[0]["summary"]
        assert deficits[0]["claim_ids"] == [claim.id]
    finally:
        app.dependency_overrides.clear()
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_tensions_conflict_with_evidence_provenance():
    session, engine = _session()
    client = _admin_client(session)
    try:
        token = _token()
        source = Source(
            url=f"https://fixture.example/tension-{token}",
            title="Tension fixture",
            source_type="page",
        )
        session.add(source)
        session.flush()
        obs = ObservationRef(
            observation_key=f"obs:api:tension:cross:{token}",
            content_hash=f"hash-api-cross-{token}",
            source_id=source.id,
            observed_at=NOW,
            provenance_kind="test",
        )
        claim_a = EpistemicClaim(
            proposition=f"API supported A {token}",
            attributed_to="fixture",
            provenance_kind="test",
        )
        claim_b = EpistemicClaim(
            proposition=f"API conflicting B {token}",
            attributed_to="fixture",
            provenance_kind="test",
        )
        session.add_all([obs, claim_a, claim_b])
        session.flush()
        support = EvidenceLink(
            claim_id=claim_a.id,
            observation_ref_id=obs.id,
            role="support",
            provenance_kind="test",
        )
        conflict = EvidenceLink(
            claim_id=claim_b.id,
            observation_ref_id=obs.id,
            role="conflict",
            provenance_kind="test",
        )
        session.add_all([support, conflict])
        session.commit()

        res = client.get(
            ENDPOINT, params={"page": 1, "page_size": 200, "claim_limit": 500}
        )
        assert res.status_code == 200
        conflicts = [
            item
            for item in res.json()["items"]
            if item["tension_type"] == TENSION_CONFLICT
            and set(item["claim_ids"]) == {claim_a.id, claim_b.id}
        ]
        assert len(conflicts) == 1
        assert obs.id in conflicts[0]["observation_ref_ids"]
        assert set(conflicts[0]["evidence_link_ids"]) >= {support.id, conflict.id}
        assert "Possible conflict" in conflicts[0]["summary"]
    finally:
        app.dependency_overrides.clear()
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_tensions_pagination_and_deterministic_ordering(monkeypatch):
    views = [
        TensionView(
            tension_type=TENSION_SUPPORT_DEFICIT,
            claim_ids=(20,),
            observation_ref_ids=(),
            evidence_link_ids=(),
            summary="Possible support deficit: claim 20",
        ),
        TensionView(
            tension_type=TENSION_CONFLICT,
            claim_ids=(1, 2),
            observation_ref_ids=(9,),
            evidence_link_ids=(3, 4),
            summary="Possible conflict: claims 1/2",
        ),
        TensionView(
            tension_type=TENSION_SUPPORT_DEFICIT,
            claim_ids=(10,),
            observation_ref_ids=(),
            evidence_link_ids=(),
            summary="Possible support deficit: claim 10",
        ),
    ]

    class FakeSurfacing:
        def __init__(self, memory):
            pass

        def surface_tensions(self, **kwargs):
            return views

    monkeypatch.setattr(
        "app.api.understanding.EpistemicMemoryService",
        lambda db: MagicMock(),
    )
    monkeypatch.setattr(
        "app.api.understanding.TensionSurfacingService",
        FakeSurfacing,
    )
    app.dependency_overrides[require_admin] = lambda: MagicMock(role="admin")
    app.dependency_overrides[get_db] = lambda: iter([MagicMock()])
    try:
        client = TestClient(app)
        res = client.get(ENDPOINT, params={"page": 1, "page_size": 2})
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["page_size"] == 2
        assert len(body["items"]) == 2
        # FakeSurfacing returns views in list order (no re-sort in API).
        assert body["items"][0]["claim_ids"] == [20]
        assert body["items"][1]["tension_type"] == TENSION_CONFLICT
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
def test_understanding_package_imports_clean():
    assert (APP_ROOT / "api" / "understanding.py").is_file()
    assert (APP_ROOT / "schemas" / "understanding.py").is_file()
