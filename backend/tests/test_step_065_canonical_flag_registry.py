"""RFC-100 Step 065 — canonical flag registry ownership."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import build_info_service
from app.services.feature_flags import (
    FLAG_DEFINITIONS,
    FlagDefinition,
    env_bool_flag_definitions,
    flag_definition_by_key,
    flag_keys,
    maintenance_observation,
    settings_flag_definitions,
)

EXPECTED_ENV_BOOL = {
    "KNOWLEDGE_OS_EXECUTIVE_ENABLED",
    "REASONING_SERVICE_ENABLED",
    "EVIDENCE_ASSEMBLY_ENABLED",
    "REASONING_SPEECH_ACTS_ENABLED",
    "MAINTENANCE_EXECUTION_ENABLED",
}
EXPECTED_SETTINGS = {
    "enable_semantic_diagnostics_v2",
    "cache_namespace_v2_enabled",
    "memory_shadow_write_enabled",
    "memory_evidence_assist_enabled",
    "memory_canonical_shadow_enabled",
    "allow_legacy_kp_presets",
    "legacy_doc_type_canonical_enabled",
}
EXPECTED_INT = {"MAINTENANCE_INVESTIGATIONS_PER_CYCLE"}


pytestmark = pytest.mark.unit


def test_registry_exists_and_unique_keys():
    assert FLAG_DEFINITIONS
    keys = flag_keys()
    assert len(keys) == len(set(keys))
    assert set(keys) == EXPECTED_ENV_BOOL | EXPECTED_SETTINGS | EXPECTED_INT


def test_source_defaults_classification_and_visibility():
    by_key = flag_definition_by_key()
    for key in EXPECTED_ENV_BOOL | EXPECTED_INT:
        d = by_key[key]
        assert d.source == "env"
        assert d.product_visibility is False
        assert d.engineering_visibility is True
        assert d.runtime_owner
    for key in EXPECTED_SETTINGS:
        d = by_key[key]
        assert d.source == "settings"
        assert d.product_visibility is False

    assert by_key["KNOWLEDGE_OS_EXECUTIVE_ENABLED"].default is True
    assert by_key["KNOWLEDGE_OS_EXECUTIVE_ENABLED"].classification == "permanent_kill_switch"
    assert "direct Rag" not in by_key["KNOWLEDGE_OS_EXECUTIVE_ENABLED"].effect
    assert "controlled unavailable" in by_key["KNOWLEDGE_OS_EXECUTIVE_ENABLED"].effect.lower()

    assert by_key["MAINTENANCE_EXECUTION_ENABLED"].default is True
    assert by_key["MAINTENANCE_EXECUTION_ENABLED"].classification == "permanent_operational"
    assert by_key["MAINTENANCE_INVESTIGATIONS_PER_CYCLE"].value_kind == "int"
    assert by_key["MAINTENANCE_INVESTIGATIONS_PER_CYCLE"].int_default == 0

    assert by_key["enable_semantic_diagnostics_v2"].default is True
    assert by_key["allow_legacy_kp_presets"].default is False
    assert by_key["legacy_doc_type_canonical_enabled"].classification == "legacy_compatibility"


def test_build_info_imports_canonical_helpers_not_independent_tuples():
    src = Path(build_info_service.__file__).read_text(encoding="utf-8")
    assert "_ENV_CAPABILITIES" not in src
    assert "_SETTINGS_CAPABILITIES" not in src
    assert "env_bool_flag_definitions" in src
    assert "settings_flag_definitions" in src
    assert "maintenance_observation" in src
    assert "instead of direct RagService" not in src


def test_env_bool_and_settings_partitions():
    assert {d.key for d in env_bool_flag_definitions()} == EXPECTED_ENV_BOOL
    assert {d.key for d in settings_flag_definitions()} == EXPECTED_SETTINGS
    assert all(isinstance(d, FlagDefinition) for d in FLAG_DEFINITIONS)


def test_maintenance_observation_parity_with_owner(monkeypatch):
    monkeypatch.delenv("MAINTENANCE_EXECUTION_ENABLED", raising=False)
    monkeypatch.delenv("MAINTENANCE_INVESTIGATIONS_PER_CYCLE", raising=False)
    from app.services.executive.maintenance_orchestration import (
        operational_budget,
        rollout_flag_enabled,
    )

    obs = maintenance_observation(environ={})
    assert obs["execution_enabled"] is True
    assert obs["investigations_per_cycle"] == 0
    assert obs["execution_enabled"] is rollout_flag_enabled({})
    assert obs["investigations_per_cycle"] == operational_budget({})

    monkeypatch.setenv("MAINTENANCE_EXECUTION_ENABLED", "false")
    monkeypatch.setenv("MAINTENANCE_INVESTIGATIONS_PER_CYCLE", "3")
    obs2 = maintenance_observation()
    assert obs2["execution_enabled"] is False
    assert obs2["investigations_per_cycle"] == 3
