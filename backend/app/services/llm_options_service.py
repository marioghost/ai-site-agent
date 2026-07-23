"""Dynamic Ollama generation options."""
from __future__ import annotations

from app.models.settings import Settings
from app.services.llm_mode_service import effective_generation_settings


def estimate_tokens(char_count: int) -> int:
    return max(1, char_count // 4)


def resolve_llm_options(settings: Settings, *, prompt_chars: int) -> dict:
    eff = effective_generation_settings(settings)
    num_predict = int(eff.get("llm_num_predict") or 160)

    mode = (eff.get("llm_num_ctx_mode") or "auto").lower()
    fixed = int(eff.get("llm_fixed_num_ctx") or 4096)
    est = estimate_tokens(prompt_chars)
    if mode == "fixed":
        num_ctx = fixed
    else:
        num_ctx = 4096 if est <= 3000 else 8192

    temperature = min(float(settings.temperature or 0.1), 0.1)
    keep_alive = (eff.get("llm_keep_alive") or "30m").strip()
    opts = {
        "temperature": temperature,
        "num_predict": num_predict,
        "num_ctx": num_ctx,
        "top_p": 0.9,
        "repeat_penalty": 1.05,
        "keep_alive": keep_alive,
        "llm_mode_profile": eff.get("llm_mode_profile", "fast"),
        "generation_timeout_seconds": eff.get("generation_timeout_seconds", 45),
        "llm_retry_max_attempts": eff.get("llm_retry_max_attempts", 0),
    }
    return opts
