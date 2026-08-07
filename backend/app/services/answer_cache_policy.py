"""When semantic answer cache may be used on a chat turn.

Keeps lookup/store gating in one place so RagService and streaming stay aligned.
See ADR-0003 (Memory assist bypasses answer cache).
"""
from __future__ import annotations

from app.models.settings import Settings
from app.services.reasoning.memory_assist_policy import memory_assist_effective


def answer_cache_permitted(
    settings: Settings,
    *,
    bypass_cache: bool,
    apply_memory_assist: bool,
) -> bool:
    """True when answer cache lookup/store may run for this turn."""
    if bypass_cache or not settings.enable_semantic_answer_cache:
        return False
    if apply_memory_assist and memory_assist_effective(settings):
        return False
    return True


def answer_cache_skip_reason(
    settings: Settings,
    *,
    bypass_cache: bool,
    apply_memory_assist: bool,
) -> str:
    """Trace skip reason when answer_cache_permitted is False."""
    if not settings.enable_semantic_answer_cache:
        return "disabled"
    if bypass_cache:
        return "bypassed"
    if apply_memory_assist and memory_assist_effective(settings):
        return "memory_assist_active"
    return "bypassed"
