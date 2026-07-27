"""RFC-100 Steps 025 / 037 — operational gauges (versions + tension hypotheses)."""
from __future__ import annotations

import ast
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.main import app
from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from app.models.settings import Settings
from app.services.epistemic_memory import EpistemicMemoryService
from app.services.memory_version_service import MemoryVersionService
from app.services.operational_metrics_service import OperationalMetricsService
from app.services.tension_surfacing import (
    METRICS_CLAIM_SCAN_LIMIT,
    TensionCountSummary,
    TensionSurfacingService,
)

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
METRICS_SERVICE = APP_ROOT / "services/operational_metrics_service.py"
METRICS_API = APP_ROOT / "api/metrics.py"
NOW = datetime.now(timezone.utc)


def _fake_repo(state: Settings):
    class FakeRepo:
        def get_or_create(self) -> Settings:
            return state

        def save(self, settings: Settings) -> Settings:
            return settings

    return FakeRepo


def _zero_tension_summary() -> TensionCountSummary:
    return TensionCountSummary(
        open_tensions=0,
        support_deficit_tensions=0,
        conflict_tensions=0,
        claim_scan_limit=METRICS_CLAIM_SCAN_LIMIT,
    )


def _patch_versions_and_empty_tensions(monkeypatch, state: Settings) -> None:
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.operational_metrics_service.EpistemicMemoryService",
        lambda db: MagicMock(),
    )
    monkeypatch.setattr(
        "app.services.operational_metrics_service.TensionSurfacingService",
        lambda memory: MagicMock(summarize_counts=lambda **kw: _zero_tension_summary()),
    )


@pytest.fixture()
def metrics_client(monkeypatch) -> TestClient:
    state = Settings(knowledge_version=11, memory_version=3)
    _patch_versions_and_empty_tensions(monkeypatch, state)

    def override_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.unit
def test_operational_metrics_json_reports_current_memory_version(metrics_client: TestClient):
    res = metrics_client.get("/api/metrics/operational")
    assert res.status_code == 200
    body = res.json()
    assert body["memory_version"] == 3
    assert body["knowledge_version"] == 11
    assert body["open_tensions"] == 0
    assert body["support_deficit_tensions"] == 0
    assert body["conflict_tensions"] == 0
    assert body["tension_claim_scan_limit"] == METRICS_CLAIM_SCAN_LIMIT


@pytest.mark.unit
def test_prometheus_metrics_exports_memory_version_gauge(metrics_client: TestClient):
    res = metrics_client.get("/api/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    text = res.text
    assert "# TYPE kos_memory_version gauge" in text
    assert re.search(r"^kos_memory_version 3$", text, re.MULTILINE)
    assert "# TYPE kos_knowledge_version gauge" in text
    assert re.search(r"^kos_knowledge_version 11$", text, re.MULTILINE)
    assert "# TYPE kos_open_tensions gauge" in text
    assert re.search(r"^kos_open_tensions 0$", text, re.MULTILINE)
    assert "# TYPE kos_support_deficit_tensions gauge" in text
    assert "# TYPE kos_conflict_tensions gauge" in text


@pytest.mark.unit
def test_bumping_memory_version_changes_exported_value(monkeypatch):
    state = Settings(knowledge_version=5, memory_version=1)
    _patch_versions_and_empty_tensions(monkeypatch, state)
    svc = OperationalMetricsService(db=None)
    assert svc.collect_gauges().memory_version == 1
    MemoryVersionService(db=None).bump()
    assert svc.collect_gauges().memory_version == 2
    assert svc.collect_gauges().knowledge_version == 5


@pytest.mark.unit
def test_knowledge_version_remains_separate_from_memory_version(monkeypatch):
    state = Settings(knowledge_version=99, memory_version=2)
    _patch_versions_and_empty_tensions(monkeypatch, state)
    gauges = OperationalMetricsService(db=None).collect_gauges()
    assert gauges.memory_version == 2
    assert gauges.knowledge_version == 99
    assert gauges.memory_version != gauges.knowledge_version


@pytest.mark.unit
def test_uninitialized_memory_version_reports_one_via_service(monkeypatch):
    state = Settings(knowledge_version=1)
    object.__setattr__(state, "memory_version", None)
    _patch_versions_and_empty_tensions(monkeypatch, state)
    assert OperationalMetricsService(db=None).collect_gauges().memory_version == 1


@pytest.mark.unit
def test_metrics_service_does_not_mutate_memory_version(monkeypatch):
    state = Settings(knowledge_version=1, memory_version=4)
    _patch_versions_and_empty_tensions(monkeypatch, state)
    svc = OperationalMetricsService(db=None)
    for _ in range(5):
        svc.collect_gauges()
        svc.render_prometheus()
    assert state.memory_version == 4
    assert state.knowledge_version == 1


@pytest.mark.unit
def test_metrics_service_uses_version_services_not_direct_settings_reads():
    source = METRICS_SERVICE.read_text(encoding="utf-8")
    assert "MemoryVersionService" in source
    assert "KnowledgeVersionService" in source
    assert "TensionSurfacingService" in source
    assert "settings.memory_version" not in source
    assert ".bump(" not in source


@pytest.mark.unit
def test_metrics_api_does_not_mutate_versions():
    api_source = METRICS_API.read_text(encoding="utf-8")
    service_source = METRICS_SERVICE.read_text(encoding="utf-8")
    assert ".bump(" not in api_source
    assert ".bump(" not in service_source
    tree = ast.parse(service_source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                name = ast.unparse(target)
                assert "memory_version" not in name
                assert "knowledge_version" not in name


@pytest.mark.unit
def test_metrics_layer_does_not_import_epistemic_orm():
    source = METRICS_SERVICE.read_text(encoding="utf-8")
    for banned in (
        "app.models.epistemic_memory",
        "EpistemicClaim",
        "EvidenceLink",
        "ObservationRef",
        "session.query",
        "session.execute",
    ):
        assert banned not in source


@pytest.mark.unit
def test_empty_memory_exports_zero_tension_counts(monkeypatch):
    state = Settings(knowledge_version=1, memory_version=1)
    _patch_versions_and_empty_tensions(monkeypatch, state)
    gauges = OperationalMetricsService(db=None).collect_gauges()
    assert gauges.open_tensions == 0
    assert gauges.support_deficit_tensions == 0
    assert gauges.conflict_tensions == 0
    assert gauges.open_tensions == (
        gauges.support_deficit_tensions + gauges.conflict_tensions
    )


@pytest.mark.unit
def test_tension_gauge_counts_from_summarize_counts(monkeypatch):
    state = Settings(knowledge_version=1, memory_version=7)
    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.operational_metrics_service.EpistemicMemoryService",
        lambda db: MagicMock(),
    )
    summary = TensionCountSummary(
        open_tensions=3,
        support_deficit_tensions=2,
        conflict_tensions=1,
        claim_scan_limit=METRICS_CLAIM_SCAN_LIMIT,
    )
    monkeypatch.setattr(
        "app.services.operational_metrics_service.TensionSurfacingService",
        lambda memory: MagicMock(summarize_counts=lambda **kw: summary),
    )
    gauges = OperationalMetricsService(db=None).collect_gauges()
    assert gauges.memory_version == 7
    assert gauges.knowledge_version == 1
    assert gauges.open_tensions == 3
    assert gauges.support_deficit_tensions == 2
    assert gauges.conflict_tensions == 1
    assert gauges.open_tensions == (
        gauges.support_deficit_tensions + gauges.conflict_tensions
    )
    text = OperationalMetricsService(db=None).render_prometheus()
    assert re.search(r"^kos_open_tensions 3$", text, re.MULTILINE)
    assert re.search(r"^kos_support_deficit_tensions 2$", text, re.MULTILINE)
    assert re.search(r"^kos_conflict_tensions 1$", text, re.MULTILINE)
    assert re.search(r"^kos_memory_version 7$", text, re.MULTILINE)


def _session():
    from tests._dbutil import make_engine

    engine = make_engine(fresh=False)
    session = sessionmaker(bind=engine)()
    return session, EpistemicMemoryService(session), engine


@pytest.mark.unit
def test_summarize_counts_support_deficit_and_conflict_fixture():
    session, memory, engine = _session()
    try:
        token = uuid.uuid4().hex[:12]
        deficit = EpistemicClaim(
            proposition=f"Metrics deficit {token}",
            attributed_to="fixture",
            provenance_kind="test",
        )
        from tests._dbutil import ensure_source_ids

        ensure_source_ids(session, 970)
        obs = ObservationRef(
            observation_key=f"obs:metrics:cross:{token}",
            content_hash=f"hash-metrics-{token}",
            source_id=970,
            observed_at=NOW,
            provenance_kind="test",
        )
        claim_a = EpistemicClaim(
            proposition=f"Metrics A {token}",
            attributed_to="fixture",
            provenance_kind="test",
        )
        claim_b = EpistemicClaim(
            proposition=f"Metrics B {token}",
            attributed_to="fixture",
            provenance_kind="test",
        )
        session.add_all([deficit, obs, claim_a, claim_b])
        session.flush()
        session.add_all(
            [
                EvidenceLink(
                    claim_id=claim_a.id,
                    observation_ref_id=obs.id,
                    role="support",
                    provenance_kind="test",
                ),
                EvidenceLink(
                    claim_id=claim_b.id,
                    observation_ref_id=obs.id,
                    role="conflict",
                    provenance_kind="test",
                ),
            ]
        )
        session.commit()

        summary = TensionSurfacingService(memory).summarize_counts()
        tensions = TensionSurfacingService(memory).surface_tensions()
        # Shared DB may contain other fixtures — assert our claims contribute correctly.
        our_deficits = [
            t
            for t in tensions
            if t.tension_type == "support_deficit" and deficit.id in t.claim_ids
        ]
        our_conflicts = [
            t
            for t in tensions
            if t.tension_type == "conflict"
            and set(t.claim_ids) == {claim_a.id, claim_b.id}
        ]
        assert len(our_deficits) == 1
        assert len(our_conflicts) == 1
        assert summary.open_tensions == (
            summary.support_deficit_tensions + summary.conflict_tensions
        )
        assert summary.open_tensions == len(tensions)
        assert summary.claim_scan_limit == METRICS_CLAIM_SCAN_LIMIT
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_summarize_counts_ignores_superseded_claims():
    session, memory, engine = _session()
    try:
        token = uuid.uuid4().hex[:12]
        active = EpistemicClaim(
            proposition=f"Metrics active {token}",
            attributed_to="fixture",
            provenance_kind="test",
        )
        session.add(active)
        session.flush()
        old = EpistemicClaim(
            proposition=f"Metrics superseded {token}",
            attributed_to="fixture",
            provenance_kind="test",
            superseded_by_id=active.id,
        )
        session.add(old)
        session.commit()

        tensions = TensionSurfacingService(memory).surface_tensions()
        assert all(old.id not in t.claim_ids for t in tensions)
        summary = TensionSurfacingService(memory).summarize_counts()
        assert summary.open_tensions == len(tensions)
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_repeated_metric_reads_do_not_mutate_memory(monkeypatch):
    state = Settings(knowledge_version=2, memory_version=9)
    calls = {"summarize": 0}

    def _summarize(**kwargs):
        calls["summarize"] += 1
        return TensionCountSummary(
            open_tensions=1,
            support_deficit_tensions=1,
            conflict_tensions=0,
            claim_scan_limit=METRICS_CLAIM_SCAN_LIMIT,
        )

    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_version_service.SettingsRepository",
        lambda db: _fake_repo(state)(),
    )
    monkeypatch.setattr(
        "app.services.operational_metrics_service.EpistemicMemoryService",
        lambda db: MagicMock(),
    )
    monkeypatch.setattr(
        "app.services.operational_metrics_service.TensionSurfacingService",
        lambda memory: MagicMock(summarize_counts=_summarize),
    )
    svc = OperationalMetricsService(db=None)
    for _ in range(3):
        gauges = svc.collect_gauges()
        assert gauges.open_tensions == 1
    assert state.memory_version == 9
    assert state.knowledge_version == 2
    assert calls["summarize"] == 3
