"""Deployment feature flags for Knowledge OS migration (RFC-100)."""
from __future__ import annotations

from app.core.config import get_config


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
