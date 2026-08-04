"""RFC-100 Step 067 — Release 1.0 engineering closure metadata (unit)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_config
from app.services.build_info_service import APP_RELEASE, RELEASE_1_0_STEPS, BuildInfoService


@pytest.mark.unit
def test_app_release_is_1_0():
    assert APP_RELEASE == "1.0"


@pytest.mark.unit
def test_release_1_0_steps_include_063_through_067():
    assert [s["step"] for s in RELEASE_1_0_STEPS] == [
        "063",
        "064",
        "065",
        "066",
        "067",
    ]


@pytest.mark.unit
def test_release_1_0_closure_metadata(tmp_path: Path):
    svc = BuildInfoService.__new__(BuildInfoService)
    svc._db = MagicMock()
    svc._config = get_config()
    monkey_settings = MagicMock(
        enable_semantic_diagnostics_v2=True,
        cache_namespace_v2_enabled=True,
        memory_shadow_write_enabled=True,
        memory_evidence_assist_enabled=True,
        memory_canonical_shadow_enabled=True,
        allow_legacy_kp_presets=False,
        legacy_doc_type_canonical_enabled=False,
    )
    with (
        patch("app.services.build_info_service._project_root", lambda: tmp_path),
        patch("app.services.build_info_service.SettingsRepository") as SR,
        patch("app.services.build_info_service.MemoryVersionService") as MV,
        patch("app.services.build_info_service.KnowledgeVersionService") as KV,
        patch(
            "app.services.build_info_service.current_db_revision",
            return_value="0020_step_063_kos_flags_default_on (head)",
        ),
    ):
        SR.return_value.get_or_create.return_value = monkey_settings
        MV.return_value.get.return_value = 1
        KV.return_value.get.return_value = 1
        data = svc.collect()

    rs = data["release_status"]
    assert data["release"] == "1.0"
    assert rs["accepted"] == "1.0"
    assert rs["in_progress"] is None
    assert rs["closed_0_6"] is True
    assert rs["closed_0_7"] is True
    assert rs["closed_0_8"] is True
    assert rs["closed_0_9"] is True
    assert rs["closed_1_0"] is True
    assert rs["engineering_ready"] is True
    assert rs["staging_validated"] is False
    assert rs["production_ready"] is False
    assert [s["step"] for s in rs["steps_063"]] == [
        "063",
        "064",
        "065",
        "066",
        "067",
    ]
    caps1 = rs["release_1_0_capabilities"]
    assert caps1["kos_defaults_on"]["code_present"] is True
    assert caps1["executive_only_api_routing"]["code_present"] is True
    assert caps1["canonical_flag_registry"]["code_present"] is True
    assert caps1["load_and_rollback_drill"]["code_present"] is True
    assert caps1["release_1_0_engineering_closure"]["code_present"] is True
    assert "Step 067" in rs["note"]
    assert "staging_validated/production_ready stay false" in rs["note"]


@pytest.mark.unit
def test_prior_release_steps_remain_present(tmp_path: Path):
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
        patch("app.services.build_info_service._project_root", lambda: tmp_path),
        patch("app.services.build_info_service.SettingsRepository") as SR,
        patch("app.services.build_info_service.MemoryVersionService") as MV,
        patch("app.services.build_info_service.KnowledgeVersionService") as KV,
        patch(
            "app.services.build_info_service.current_db_revision",
            return_value="0020_step_063_kos_flags_default_on (head)",
        ),
    ):
        SR.return_value.get_or_create.return_value = monkey_settings
        MV.return_value.get.return_value = 1
        KV.return_value.get.return_value = 1
        data = svc.collect()

    rs = data["release_status"]
    assert [s["step"] for s in rs["steps_058_062"]] == [
        "058",
        "059",
        "060",
        "061",
        "062",
    ]
    assert rs["release_0_9_capabilities"]["index_integrate_compose"]["code_present"]


@pytest.mark.unit
def test_required_closure_docs_exist():
    root = Path(__file__).resolve().parents[2]
    releases = root / "docs" / "releases"
    assert (releases / "1.0-step-067-engineering-package.md").is_file()
    assert (releases / "1.0-step-067-release-closure.md").is_file()
    assert (releases / "1.0-rollback.md").is_file()
    assert (releases / "1.0-step-067-closure-evidence.json").is_file()


@pytest.mark.unit
def test_runbook_surfaces_match_deploy_cli():
    root = Path(__file__).resolve().parents[2]
    text = (root / "docs" / "releases" / "1.0-rollback.md").read_text(encoding="utf-8")
    for surface in (
        "manage_deploy.sh status",
        "manage_deploy.sh build-info",
        "manage_deploy.sh health",
        "manage_deploy.sh deploy full",
        "verify-release",
        "smoke",
    ):
        assert surface in text
