"""Polish pass policy (off by default for production latency)."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.settings import Settings
from app.services.llm_mode_service import effective_generation_settings
from app.services.query_intent_service import BROAD_INTENTS


@dataclass(frozen=True)
class PolishDecision:
    enabled: bool
    reason: str


def _resolve_polish_mode(settings: Settings) -> str:
    eff = effective_generation_settings(settings)
    mode = (eff.get("polish_mode") or "off").lower().strip()
    if mode not in {"off", "auto", "always"}:
        return "off"
    return mode


def evaluate_polish(
    settings: Settings,
    *,
    answer: str,
    language: str,
    fast_mode: bool,
    generation_ms: int,
    is_overview: bool = False,
    error_type: str | None = None,
    is_fallback: bool = False,
) -> PolishDecision:
    if error_type:
        return PolishDecision(False, f"error:{error_type}")
    if is_fallback:
        return PolishDecision(False, "fallback_response")
    text = (answer or "").strip()
    if not text:
        return PolishDecision(False, "empty_answer")

    mode = _resolve_polish_mode(settings)
    if mode == "off":
        return PolishDecision(False, "mode_off")
    if language != "uk":
        return PolishDecision(False, f"language:{language}")

    min_chars = int(getattr(settings, "polish_min_answer_chars", 2000) or 2000)
    gen_limit = int(getattr(settings, "polish_skip_if_generation_ms_over", 15000) or 15000)

    if mode == "always":
        if generation_ms > gen_limit:
            return PolishDecision(False, f"generation_slow:{generation_ms}ms")
        return PolishDecision(True, "mode_always")

    # auto
    if is_overview:
        return PolishDecision(False, "overview_query")
    if fast_mode and len(text) <= 160:
        return PolishDecision(False, "fast_short_answer")
    if len(text) < min_chars:
        return PolishDecision(False, f"answer_short:{len(text)}<{min_chars}")
    if generation_ms > gen_limit:
        return PolishDecision(False, f"generation_slow:{generation_ms}ms")
    return PolishDecision(True, "auto_eligible")


def should_polish(
    settings: Settings,
    *,
    answer: str,
    language: str,
    fast_mode: bool,
    generation_ms: int,
    is_overview: bool = False,
    error_type: str | None = None,
    is_fallback: bool = False,
) -> bool:
    return evaluate_polish(
        settings,
        answer=answer,
        language=language,
        fast_mode=fast_mode,
        generation_ms=generation_ms,
        is_overview=is_overview,
        error_type=error_type,
        is_fallback=is_fallback,
    ).enabled


def is_overview_intent(intent: str) -> bool:
    return intent in BROAD_INTENTS
