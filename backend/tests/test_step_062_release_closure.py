"""RFC-100 Step 062 — Release 0.9 engineering closure metadata (unit)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_config
from app.services.build_info_service import APP_RELEASE, BuildInfoService
from app.services.operational_metrics_service import OperationalMetricsService
from app.services.tension_surfacing.tension_surfacing_service import TensionCountSummary


@pytest.mark.unit
def test_app_release_is_0_9():
    assert APP_RELEASE == "0.9"


@pytest.mark.unit
def test_release_0_9_closure_metadata():
    svc = BuildInfoService.__new__(BuildInfoService)
    svc._db = MagicMock()
    svc._config = get_config()
    monkey_settings = MagicMock(
        enable_semantic_diagnostics_v2=False,
        cache_namespace_v2_enabled=False,
        memory_shadow_write_enabled=False,
        memory_evidence_assist_enabled=False,
        memory_canonical_shadow_enabled=False,
        allow_legacy_kp_presets=False,
        legacy_doc_type_canonical_enabled=False,
    )
    with (
        patch("app.services.build_info_service.SettingsRepository") as SR,
        patch("app.services.build_info_service.MemoryVersionService") as MV,
        patch("app.services.build_info_service.KnowledgeVersionService") as KV,
        patch(
            "app.services.build_info_service.current_db_revision",
            return_value="0019_legacy_doc_type_canonical_enabled (head)",
        ),
    ):
        SR.return_value.get_or_create.return_value = monkey_settings
        MV.return_value.get.return_value = 1
        KV.return_value.get.return_value = 1
        data = svc.collect()

    rs = data["release_status"]
    assert rs["accepted"] == "0.9"
    assert rs["closed_0_6"] is True
    assert rs["closed_0_7"] is True
    assert rs["closed_0_8"] is True
    assert rs["closed_0_9"] is True
    assert rs["engineering_ready"] is True
    assert rs["staging_validated"] is False
    assert rs["production_ready"] is False
    assert rs["in_progress"] is None
    assert [s["step"] for s in rs["steps_058_062"]] == [
        "058",
        "059",
        "060",
        "061",
        "062",
    ]
    caps9 = rs["release_0_9_capabilities"]
    assert caps9["index_integrate_compose"]["code_present"] is True
    assert caps9["investigation_metrics"]["code_present"] is True
    assert "kos_tension_resolved_total deferred" in caps9["investigation_metrics"]["note"]


@pytest.mark.unit
def test_metrics_still_only_three_investigation_counters(monkeypatch):
    """Step 062 must not introduce kos_tension_resolved_total."""
    monkeypatch.setattr(
        "app.services.operational_metrics_service.MemoryVersionService",
        lambda db: MagicMock(get=lambda: 1),
    )
    monkeypatch.setattr(
        "app.services.operational_metrics_service.KnowledgeVersionService",
        lambda db: MagicMock(get=lambda: 1),
    )
    monkeypatch.setattr(
        "app.services.operational_metrics_service.EpistemicMemoryService",
        lambda db: MagicMock(),
    )
    monkeypatch.setattr(
        "app.services.operational_metrics_service.TensionSurfacingService",
        lambda memory: MagicMock(
            summarize_counts=lambda **kw: TensionCountSummary(
                open_tensions=0,
                support_deficit_tensions=0,
                conflict_tensions=0,
                claim_scan_limit=100,
            )
        ),
    )
    text = OperationalMetricsService(db=None).render_prometheus()
    assert "kos_maintenance_cycles_total" in text
    assert "kos_investigations_planned" in text
    assert "kos_investigations_failed_total" in text
    assert "kos_tension_resolved_total" not in text


@pytest.mark.unit
def test_required_closure_docs_exist():
    root = Path(__file__).resolve().parents[2]
    releases = root / "docs" / "releases"
    assert (releases / "RELEASE-0.9-ACCEPTANCE-REPORT.md").is_file()
    assert (releases / "0.9-rollback.md").is_file()
    assert (releases / "0.9-step-062-release-closure.md").is_file()
