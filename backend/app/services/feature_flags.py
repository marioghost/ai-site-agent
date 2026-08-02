"""Deployment feature flags for Knowledge OS migration (RFC-100).

RFC-100 Step 065 — canonical flag definitions + effective-value helpers.
Storage remains Environment / Settings; this module owns definitions and
effective bool resolution for flags that already have helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.config import get_config

FlagSource = Literal["env", "settings"]
FlagClassification = Literal[
    "permanent_kill_switch",
    "permanent_settings",
    "legacy_compatibility",
    "permanent_operational",
]


@dataclass(frozen=True)
class FlagDefinition:
    """Lightweight registry entry (Step 065). Not a remote/dynamic platform."""

    key: str
    source: FlagSource
    default: bool
    classification: FlagClassification
    friendly_name: str
    effect: str
    rollout: str
    runtime_owner: str
    config_attr: str | None = None
    settings_attr: str | None = None
    product_visibility: bool = False
    engineering_visibility: bool = True
    value_kind: Literal["bool", "int"] = "bool"
    int_default: int | None = None


FLAG_DEFINITIONS: tuple[FlagDefinition, ...] = (
    FlagDefinition(
        key="KNOWLEDGE_OS_EXECUTIVE_ENABLED",
        source="env",
        default=True,
        classification="permanent_kill_switch",
        friendly_name="Executive seam",
        effect=(
            "Sole API chat entry via ExecutiveService; "
            "explicit false = controlled unavailable (HTTP 503 / SSE executive_disabled)"
        ),
        rollout="Step 063 default ON; Step 064 hard kill-switch = env false + restart",
        runtime_owner="feature_flags.knowledge_os_executive_enabled",
        config_attr="knowledge_os_executive_enabled",
    ),
    FlagDefinition(
        key="REASONING_SERVICE_ENABLED",
        source="env",
        default=True,
        classification="permanent_kill_switch",
        friendly_name="Reasoning seam",
        effect="Route chat through ReasoningService (diagnostics + optional Language)",
        rollout="Step 063 — default ON; kill-switch = env false + restart",
        runtime_owner="feature_flags.reasoning_service_enabled",
        config_attr="reasoning_service_enabled",
    ),
    FlagDefinition(
        key="EVIDENCE_ASSEMBLY_ENABLED",
        source="env",
        default=True,
        classification="permanent_kill_switch",
        friendly_name="Evidence Assembly seam",
        effect="Route RPS assemble stage through EvidenceAssemblyService",
        rollout="Step 063 — default ON; kill-switch = env false + restart",
        runtime_owner="feature_flags.evidence_assembly_enabled",
        config_attr="evidence_assembly_enabled",
    ),
    FlagDefinition(
        key="REASONING_SPEECH_ACTS_ENABLED",
        source="env",
        default=True,
        classification="permanent_kill_switch",
        friendly_name="Speech-act Language rendering",
        effect="Language applies clarify/refuse/qualify when Reasoning is ON",
        rollout="Step 063 — default ON; requires Reasoning ON; kill-switch = env false",
        runtime_owner="feature_flags.reasoning_speech_acts_enabled",
        config_attr="reasoning_speech_acts_enabled",
    ),
    FlagDefinition(
        key="MAINTENANCE_EXECUTION_ENABLED",
        source="env",
        default=True,
        classification="permanent_operational",
        friendly_name="Maintenance execution",
        effect="Gate maintenance investigation execution (budget still defaults to 0)",
        rollout="Step 063 — default ON when unset; invalid non-empty fails closed",
        runtime_owner="maintenance_orchestration.rollout_flag_enabled",
    ),
    FlagDefinition(
        key="MAINTENANCE_INVESTIGATIONS_PER_CYCLE",
        source="env",
        default=False,  # unused for int flags; see int_default
        classification="permanent_operational",
        friendly_name="Maintenance investigations per cycle",
        effect="Max investigations selected per maintenance cycle (0 = no work)",
        rollout="Default 0; missing/invalid/negative fail closed to 0",
        runtime_owner="maintenance_orchestration.operational_budget",
        value_kind="int",
        int_default=0,
        product_visibility=False,
    ),
    FlagDefinition(
        key="enable_semantic_diagnostics_v2",
        source="settings",
        default=True,
        classification="permanent_settings",
        friendly_name="Semantic diagnostics v2 stub",
        effect="Empty understanding_trace on chat when debug enabled",
        rollout="Step 063 — default ON",
        runtime_owner="feature_flags.semantic_diagnostics_v2_enabled",
        settings_attr="enable_semantic_diagnostics_v2",
    ),
    FlagDefinition(
        key="cache_namespace_v2_enabled",
        source="settings",
        default=True,
        classification="permanent_settings",
        friendly_name="Cache namespace v2",
        effect="Include memory_version in retrieval/answer cache namespace",
        rollout="Step 063 — default ON",
        runtime_owner="feature_flags.cache_namespace_v2_enabled",
        settings_attr="cache_namespace_v2_enabled",
    ),
    FlagDefinition(
        key="memory_shadow_write_enabled",
        source="settings",
        default=True,
        classification="permanent_settings",
        friendly_name="Memory shadow write",
        effect="Persist SI claim proposals to Epistemic Memory (shadow; not used by chat)",
        rollout="Step 063 — default ON",
        runtime_owner="feature_flags.memory_shadow_write_enabled",
        settings_attr="memory_shadow_write_enabled",
    ),
    FlagDefinition(
        key="memory_evidence_assist_enabled",
        source="settings",
        default=True,
        classification="permanent_settings",
        friendly_name="Memory evidence assist",
        effect="Advisory Memory region read in Reasoning before Evidence Assembly",
        rollout="Step 063 — default ON; effective when Reasoning + cache_namespace_v2 ON",
        runtime_owner="feature_flags.memory_evidence_assist_enabled",
        settings_attr="memory_evidence_assist_enabled",
    ),
    FlagDefinition(
        key="memory_canonical_shadow_enabled",
        source="settings",
        default=True,
        classification="permanent_settings",
        friendly_name="Memory canonical shadow",
        effect="Diagnostic Memory vs retrieval source-set comparison (shadow only)",
        rollout="Step 063 — default ON; effective when Reasoning + assist + cache v2 ON",
        runtime_owner="feature_flags.memory_canonical_shadow_enabled",
        settings_attr="memory_canonical_shadow_enabled",
    ),
    FlagDefinition(
        key="allow_legacy_kp_presets",
        source="settings",
        default=False,
        classification="legacy_compatibility",
        friendly_name="Legacy KP presets",
        effect="Allow GET/POST Knowledge Profile industry preset APIs (410 when false)",
        rollout="Default OFF at Step 054; rollback = Settings true",
        runtime_owner="feature_flags.allow_legacy_kp_presets",
        settings_attr="allow_legacy_kp_presets",
    ),
    FlagDefinition(
        key="legacy_doc_type_canonical_enabled",
        source="settings",
        default=False,
        classification="legacy_compatibility",
        friendly_name="Legacy document-type canonical selection",
        effect=(
            "When true, RPS finalize runs KP doc-type CanonicalSourceService reorder; "
            "when false, skip (DFP/score order)"
        ),
        rollout="Default OFF at Step 055; rollback = Settings true; not Memory authority",
        runtime_owner="feature_flags.legacy_doc_type_canonical_enabled",
        settings_attr="legacy_doc_type_canonical_enabled",
    ),
)


def flag_definition_by_key() -> dict[str, FlagDefinition]:
    return {d.key: d for d in FLAG_DEFINITIONS}


def flag_keys() -> tuple[str, ...]:
    return tuple(d.key for d in FLAG_DEFINITIONS)


def env_bool_flag_definitions() -> tuple[FlagDefinition, ...]:
    """Env flags that belong in boolean env_flags / deployed_capabilities maps."""
    return tuple(
        d for d in FLAG_DEFINITIONS if d.source == "env" and d.value_kind == "bool"
    )


def settings_flag_definitions() -> tuple[FlagDefinition, ...]:
    return tuple(d for d in FLAG_DEFINITIONS if d.source == "settings")


def maintenance_observation(*, environ: dict[str, str] | None = None) -> dict:
    """Read-only observation from the canonical maintenance owner (no behavior change).

    Budget is an int and must not be stuffed into env_flags (dict[str, bool]).
    """
    from app.services.executive.maintenance_orchestration import (
        operational_budget,
        rollout_flag_enabled,
    )

    return {
        "execution_enabled": bool(rollout_flag_enabled(environ)),
        "investigations_per_cycle": int(operational_budget(environ)),
        "surface": "env",
        "runtime_owner": "maintenance_orchestration",
    }


def _settings_bool(settings, name: str, *, default: bool) -> bool:
    """Read a Settings-backed flag.

    Missing attribute → *default* (plain objects / incomplete stubs).
    ORM unset (``None``) → False so in-memory ``Settings()`` fixtures stay
    explicit; production defaults come from Alembic ``server_default`` +
    migration ``UPDATE`` (Step 063) and Pydantic schema defaults.
    """
    if not hasattr(settings, name):
        return default
    value = getattr(settings, name)
    if value is None:
        return False
    return bool(value)


def knowledge_os_executive_enabled() -> bool:
    """Route chat via ExecutiveService when True (default True, RFC-100 Step 063)."""
    return bool(get_config().knowledge_os_executive_enabled)


def reasoning_service_enabled() -> bool:
    """Route chat through ReasoningService when True (default True, RFC-100 Step 063)."""
    return bool(get_config().reasoning_service_enabled)


def evidence_assembly_enabled() -> bool:
    """Route assemble stage through EvidenceAssemblyService when True (default True, Step 063)."""
    return bool(get_config().evidence_assembly_enabled)


def reasoning_speech_acts_enabled() -> bool:
    """Activate Language consumption of speech acts (default True, RFC-100 Step 063).

    Has no effect unless ReasoningService is on the chat path
    (``REASONING_SERVICE_ENABLED``). Independently rollbackable.
    """
    return bool(get_config().reasoning_speech_acts_enabled)


def semantic_diagnostics_v2_enabled(settings) -> bool:
    """Include semantic diagnostics v2 stubs when True (default True, RFC-100 Step 063)."""
    return _settings_bool(settings, "enable_semantic_diagnostics_v2", default=True)


def cache_namespace_v2_enabled(settings) -> bool:
    """Include memory_version in cache namespace when True (default True, RFC-100 Step 063)."""
    return _settings_bool(settings, "cache_namespace_v2_enabled", default=True)


def memory_shadow_write_enabled(settings) -> bool:
    """Persist SI claim proposals to epistemic tables when True (default True, Step 063)."""
    return _settings_bool(settings, "memory_shadow_write_enabled", default=True)


def memory_evidence_assist_enabled(settings) -> bool:
    """Advisory Memory region read before Evidence Assembly (default True, Step 063).

    Effective only when ``REASONING_SERVICE_ENABLED`` and ``cache_namespace_v2_enabled``.
    """
    return _settings_bool(settings, "memory_evidence_assist_enabled", default=True)


def memory_canonical_shadow_enabled(settings) -> bool:
    """Diagnostic Memory vs retrieval shadow (default True, RFC-100 Step 063).

    Effective only when Reasoning, assist, and cache namespace v2 are also ON.
    """
    return _settings_bool(settings, "memory_canonical_shadow_enabled", default=True)


def allow_legacy_kp_presets(settings) -> bool:
    """Allow Knowledge Profile industry preset list/load APIs (default False, Step 054).

    Settings-backed only — not an environment flag. Does not affect stored
    ``knowledge_profile_json`` runtime, generation/wizard, or in-process PRESETS.
    """
    return _settings_bool(settings, "allow_legacy_kp_presets", default=False)


def legacy_doc_type_canonical_enabled(settings) -> bool:
    """Allow legacy CanonicalSourceService doc-type reorder (default False, Step 055).

    Settings-backed only. When False, RPS finalize skips KP document-type
    canonical reorder and keeps post-DFP/broad-inject order. Does not implement
    Memory authority selection and does not change shadow/assist semantics.
    """
    return _settings_bool(settings, "legacy_doc_type_canonical_enabled", default=False)


def memory_canonical_shadow_effective(settings) -> bool:
    """True when shadow comparison is configured to run (all prerequisites ON)."""
    return (
        reasoning_service_enabled()
        and memory_evidence_assist_enabled(settings)
        and cache_namespace_v2_enabled(settings)
        and memory_canonical_shadow_enabled(settings)
    )
