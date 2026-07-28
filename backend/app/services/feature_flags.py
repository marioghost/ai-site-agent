"""Deployment feature flags for Knowledge OS migration (RFC-100)."""
from __future__ import annotations

from app.core.config import get_config


def knowledge_os_executive_enabled() -> bool:
    """Route non-streaming chat via ExecutiveService when True (default False)."""
    return bool(get_config().knowledge_os_executive_enabled)


def reasoning_service_enabled() -> bool:
    """Route chat through ReasoningService passthrough when True (default False, RFC-100 Step 039)."""
    return bool(get_config().reasoning_service_enabled)


def evidence_assembly_enabled() -> bool:
    """Route DFP stage through EvidenceAssemblyService when True (default False, RFC-100 Step 040)."""
    return bool(get_config().evidence_assembly_enabled)


def reasoning_speech_acts_enabled() -> bool:
    """Activate Language consumption of speech acts (default False, RFC-100 Step 045).

    Has no effect unless ReasoningService is on the chat path
    (``REASONING_SERVICE_ENABLED``). Independently rollbackable.
    """
    return bool(get_config().reasoning_speech_acts_enabled)


def semantic_diagnostics_v2_enabled(settings) -> bool:
    """Include semantic diagnostics v2 stubs when True (default False, RFC-100 Step 014)."""
    return bool(getattr(settings, "enable_semantic_diagnostics_v2", False))


def cache_namespace_v2_enabled(settings) -> bool:
    """Include memory_version in cache namespace when True (default False, RFC-100 Step 023)."""
    return bool(getattr(settings, "cache_namespace_v2_enabled", False))


def memory_shadow_write_enabled(settings) -> bool:
    """Persist SI claim proposals to epistemic tables when True (default False, RFC-100 Step 030)."""
    return bool(getattr(settings, "memory_shadow_write_enabled", False))


def memory_evidence_assist_enabled(settings) -> bool:
    """Advisory Memory region read before Evidence Assembly when True (default False, Step 047).

    Effective only when ``REASONING_SERVICE_ENABLED`` and ``cache_namespace_v2_enabled``.
  """
    return bool(getattr(settings, "memory_evidence_assist_enabled", False))


def memory_canonical_shadow_enabled(settings) -> bool:
    """Diagnostic Memory vs retrieval shadow when True (default False, Step 048).

    Effective only when Reasoning, assist, and cache namespace v2 are also ON.
    """
    return bool(getattr(settings, "memory_canonical_shadow_enabled", False))


def allow_legacy_kp_presets(settings) -> bool:
    """Allow Knowledge Profile industry preset list/load APIs (default False, Step 054).

    Settings-backed only — not an environment flag. Does not affect stored
    ``knowledge_profile_json`` runtime, generation/wizard, or in-process PRESETS.
    """
    return bool(getattr(settings, "allow_legacy_kp_presets", False))


def legacy_doc_type_canonical_enabled(settings) -> bool:
    """Allow legacy CanonicalSourceService doc-type reorder (default False, Step 055).

    Settings-backed only. When False, RPS finalize skips KP document-type
    canonical reorder and keeps post-DFP/broad-inject order. Does not implement
    Memory authority selection and does not change shadow/assist semantics.
    """
    return bool(getattr(settings, "legacy_doc_type_canonical_enabled", False))


def memory_canonical_shadow_effective(settings) -> bool:
    """True when shadow comparison is configured to run (all prerequisites ON)."""
    return (
        reasoning_service_enabled()
        and memory_evidence_assist_enabled(settings)
        and cache_namespace_v2_enabled(settings)
        and memory_canonical_shadow_enabled(settings)
    )
