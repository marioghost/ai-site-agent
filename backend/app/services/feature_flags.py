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
