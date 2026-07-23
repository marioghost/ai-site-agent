"""Optional second-pass Ukrainian polishing of generated answers.

Rewrites the answer into clean, grammatically correct Ukrainian WITHOUT changing
facts, numbers, links or meaning. Used only when the response language is
Ukrainian and the answer is a real (non-fallback) grounded answer.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.services.ollama_service import OllamaError, OllamaService

logger = get_logger(__name__)

_POLISH_SYSTEM_PROMPT = (
    "Ти — редактор української мови. Перепиши наданий текст чистою, "
    "грамотною, природною українською мовою. СУВОРІ ПРАВИЛА: не змінюй факти, "
    "числа, дати, посилання (URL), назви та згадки джерел; не додавай нову "
    "інформацію; не прибирай наявну інформацію; не перекладай і не змінюй URL. "
    "Поверни лише відредагований текст без коментарів."
)

# Answers shorter than this are typically already clean; skipping them in fast
# mode avoids an extra LLM round-trip.
_SHORT_ANSWER_CHARS = 160


class AnswerPolishService:
    def __init__(self, ollama: OllamaService, model: str) -> None:
        self.ollama = ollama
        self.model = model

    @staticmethod
    def should_skip_short(answer: str, fast_mode: bool) -> bool:
        return fast_mode and len(answer.strip()) <= _SHORT_ANSWER_CHARS

    def polish(
        self,
        answer: str,
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
        timeout: float = 20.0,
    ) -> str:
        """Return a polished version of the answer, or the original on failure."""
        text = answer.strip()
        if not text:
            return answer
        use_model = model or self.model
        try:
            result = self.ollama.chat(
                model=use_model,
                system_prompt=_POLISH_SYSTEM_PROMPT,
                user_prompt=text,
                temperature=min(temperature, 0.2),
                max_tokens=max_tokens,
                timeout=timeout,
            )
        except OllamaError as exc:
            logger.warning("Ukrainian polish pass failed: %s", exc)
            return answer
        polished = result.content.strip()
        return polished or answer
