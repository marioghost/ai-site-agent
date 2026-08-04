"""RFC-100 Step 063 — Knowledge OS flags default ON (Release 1.0)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_config
from app.models.settings import Settings
from app.services import feature_flags as flags
from app.services.build_info_service import APP_RELEASE, RELEASE_1_0_STEPS
from app.services.executive.maintenance_orchestration import rollout_flag_enabled

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations" / "versions"


@pytest.mark.unit
def test_app_release_is_1_0_after_step_067_closure():
    assert APP_RELEASE == "1.0"
    assert RELEASE_1_0_STEPS[0]["step"] == "063"


@pytest.mark.unit
def test_migration_0020_chain():
    path = MIGRATIONS / "0020_step_063_kos_flags_default_on.py"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert 'revision = "0020_step_063_kos_flags_default_on"' in text
    assert 'down_revision = "0019_legacy_doc_type_canonical_enabled"' in text
    for col in (
        "enable_semantic_diagnostics_v2",
        "cache_namespace_v2_enabled",
        "memory_shadow_write_enabled",
        "memory_evidence_assist_enabled",
        "memory_canonical_shadow_enabled",
    ):
        assert col in text
    assert "allow_legacy_kp_presets" not in text.split("upgrade")[1]
    assert "legacy_doc_type_canonical_enabled" not in text.split("upgrade")[1]


@pytest.mark.unit
def test_env_kos_flags_default_on(monkeypatch):
    for key in (
        "KNOWLEDGE_OS_EXECUTIVE_ENABLED",
        "REASONING_SERVICE_ENABLED",
        "EVIDENCE_ASSEMBLY_ENABLED",
        "REASONING_SPEECH_ACTS_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    get_config.cache_clear()
    assert flags.knowledge_os_executive_enabled() is True
    assert flags.reasoning_service_enabled() is True
    assert flags.evidence_assembly_enabled() is True
    assert flags.reasoning_speech_acts_enabled() is True
    get_config.cache_clear()


@pytest.mark.unit
def test_settings_kos_flags_default_on():
    from app.schemas.settings import SettingsBase

    # Pydantic API/schema defaults (ORM Python unset stays None until DB materialize).
    schema = SettingsBase()
    assert schema.enable_semantic_diagnostics_v2 is True
    assert schema.cache_namespace_v2_enabled is True
    assert schema.memory_shadow_write_enabled is True
    assert schema.memory_evidence_assist_enabled is True
    assert schema.memory_canonical_shadow_enabled is True
    assert schema.allow_legacy_kp_presets is False
    assert schema.legacy_doc_type_canonical_enabled is False

    s = Settings(
        enable_semantic_diagnostics_v2=True,
        cache_namespace_v2_enabled=True,
        memory_shadow_write_enabled=True,
        memory_evidence_assist_enabled=True,
        memory_canonical_shadow_enabled=True,
        allow_legacy_kp_presets=False,
        legacy_doc_type_canonical_enabled=False,
    )
    assert flags.semantic_diagnostics_v2_enabled(s) is True
    assert flags.cache_namespace_v2_enabled(s) is True
    assert flags.memory_shadow_write_enabled(s) is True
    assert flags.memory_evidence_assist_enabled(s) is True
    assert flags.memory_canonical_shadow_enabled(s) is True
    assert flags.allow_legacy_kp_presets(s) is False
    assert flags.legacy_doc_type_canonical_enabled(s) is False


@pytest.mark.unit
def test_maintenance_rollout_defaults_on_when_unset():
    assert rollout_flag_enabled({}) is True
