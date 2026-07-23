"""LLM mode profiles: Fast / Balanced / High quality."""

from __future__ import annotations



from dataclasses import dataclass



from app.models.settings import Settings





@dataclass(frozen=True)

class LlmModeProfile:

    key: str

    label: str

    max_sources_in_prompt: int

    max_chars_per_source: int

    max_total_context_chars: int

    llm_max_prompt_chars: int

    llm_num_predict: int

    llm_num_ctx_mode: str

    llm_fixed_num_ctx: int

    max_answer_words_overview: int

    polish_mode: str

    generation_timeout_seconds: int

    llm_retry_max_attempts: int





PROFILES: dict[str, LlmModeProfile] = {

    "fast": LlmModeProfile(

        key="fast",

        label="Fast",

        max_sources_in_prompt=2,

        max_chars_per_source=900,

        max_total_context_chars=1800,

        llm_max_prompt_chars=3200,

        llm_num_predict=160,

        llm_num_ctx_mode="fixed",

        llm_fixed_num_ctx=4096,

        max_answer_words_overview=150,

        polish_mode="off",

        generation_timeout_seconds=45,

        llm_retry_max_attempts=0,

    ),

    "balanced": LlmModeProfile(

        key="balanced",

        label="Balanced",

        max_sources_in_prompt=3,

        max_chars_per_source=850,

        max_total_context_chars=2500,

        llm_max_prompt_chars=4500,

        llm_num_predict=240,

        llm_num_ctx_mode="auto",

        llm_fixed_num_ctx=4096,

        max_answer_words_overview=180,

        polish_mode="off",

        generation_timeout_seconds=60,

        llm_retry_max_attempts=1,

    ),

    "high_quality": LlmModeProfile(

        key="high_quality",

        label="High quality",

        max_sources_in_prompt=4,

        max_chars_per_source=1200,

        max_total_context_chars=5000,

        llm_max_prompt_chars=8000,

        llm_num_predict=512,

        llm_num_ctx_mode="auto",

        llm_fixed_num_ctx=4096,

        max_answer_words_overview=220,

        polish_mode="auto",

        generation_timeout_seconds=90,

        llm_retry_max_attempts=1,

    ),

}





def resolve_mode_key(settings: Settings) -> str:

    if bool(getattr(settings, "fast_mode_enabled", False)):

        return "fast"

    key = (getattr(settings, "llm_mode_profile", None) or "fast").lower().strip()

    if key not in PROFILES:

        return "fast"

    return key





def get_mode_profile(settings: Settings) -> LlmModeProfile:

    return PROFILES[resolve_mode_key(settings)]





def effective_generation_settings(settings: Settings) -> dict:

    """Merge dashboard settings with active mode profile (profile wins for caps)."""

    profile = get_mode_profile(settings)

    polish_mode = (getattr(settings, "polish_mode", None) or profile.polish_mode or "off").lower()

    if polish_mode not in {"off", "auto", "always"}:

        polish_mode = profile.polish_mode

    keep_alive = (getattr(settings, "llm_keep_alive", None) or "").strip()

    if not keep_alive:

        keep_alive = "30m"

    return {

        "llm_mode_profile": profile.key,

        "llm_mode_label": profile.label,

        "max_sources_in_prompt": profile.max_sources_in_prompt,

        "max_chars_per_source": profile.max_chars_per_source,

        "max_total_context_chars": profile.max_total_context_chars,

        "llm_max_prompt_chars": profile.llm_max_prompt_chars,

        "llm_num_predict": profile.llm_num_predict,

        "llm_num_ctx_mode": profile.llm_num_ctx_mode,

        "llm_fixed_num_ctx": profile.llm_fixed_num_ctx,

        "max_answer_words_overview": profile.max_answer_words_overview,

        "polish_mode": polish_mode,

        "llm_keep_alive": keep_alive,

        "generation_timeout_seconds": profile.generation_timeout_seconds,

        "llm_retry_max_attempts": profile.llm_retry_max_attempts,

    }





def profile_generation_timeout(settings: Settings) -> float:
    eff = effective_generation_settings(settings)
    return float(
        eff.get("generation_timeout_seconds") or settings.ollama_generation_timeout_seconds or 60
    )


