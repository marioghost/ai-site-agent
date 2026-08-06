"""Token budget allocation for context building."""
from __future__ import annotations

from app.models.settings import Settings
from app.services.llm_mode_service import effective_generation_settings
from app.services.llm_options_service import estimate_tokens
from app.services.retrieval_engine.types import ContextBudget


class ContextBudgetService:
    CHARS_PER_TOKEN = 4

    @classmethod
    def compute(
        cls,
        settings: Settings,
        *,
        system_prompt: str = "",
        user_message: str = "",
        num_ctx: int | None = None,
    ) -> ContextBudget:
        eff = effective_generation_settings(settings)
        ctx = num_ctx or int(eff.get("llm_fixed_num_ctx") or getattr(settings, "llm_fixed_num_ctx", 4096) or 4096)
        max_context_tokens = int(getattr(settings, "max_context_tokens", 0) or 0)
        answer_reserve = int(eff.get("llm_num_predict") or getattr(settings, "llm_num_predict", 320) or 320) + 64
        system_tokens = estimate_tokens(len(system_prompt)) if system_prompt else 120
        query_tokens = estimate_tokens(len(user_message)) if user_message else 40
        overhead = 48
        available = ctx - system_tokens - query_tokens - answer_reserve - overhead
        if max_context_tokens > 0:
            available = min(available, max_context_tokens)
        # Respect mode profile total context char budget without expanding beyond settings cap.
        profile_chars = int(eff.get("max_total_context_chars") or 0)
        if profile_chars > 0:
            available = min(available, max(256, profile_chars // cls.CHARS_PER_TOKEN))
        available = max(256, available)
        return ContextBudget(
            num_ctx=ctx,
            system_tokens=system_tokens,
            user_query_tokens=query_tokens,
            answer_reserve_tokens=answer_reserve,
            available_context_tokens=available,
        )

    @classmethod
    def tokens_to_chars(cls, tokens: int) -> int:
        return max(128, tokens * cls.CHARS_PER_TOKEN)

    @classmethod
    def chars_to_tokens(cls, chars: int) -> int:
        return max(1, chars // cls.CHARS_PER_TOKEN)
