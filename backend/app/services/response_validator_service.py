"""Lightweight deterministic answer validation (no LLM)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.language_resolver_service import detect_query_language

# Configurable malformed phrase blacklist (generic Ukrainian quality issues).
DEFAULT_MALFORMED_PHRASES: tuple[str, ...] = (
    "середньомалим",
    "досвід від років",
    "багато ресурсів та технологій",
)

_UNSUPPORTED_YEARS_PATTERN = re.compile(
    r"(?:досвід|experience)\s+(?:від|over|for)\s+(?:багато|many|\d+\+?\s*(?:рок|year))",
    re.IGNORECASE,
)


@dataclass
class ValidationResult:
    valid: bool = True
    warnings: list[str] = field(default_factory=list)
    cleaned_answer: str = ""
    applied_fixes: list[str] = field(default_factory=list)


class ResponseValidatorService:
    def __init__(
        self,
        *,
        malformed_phrases: tuple[str, ...] | None = None,
        max_words: int = 220,
    ) -> None:
        self.malformed_phrases = malformed_phrases or DEFAULT_MALFORMED_PHRASES
        self.max_words = max_words

    def validate(
        self,
        answer: str,
        *,
        query: str,
        context_text: str = "",
        is_overview: bool = False,
    ) -> ValidationResult:
        text = (answer or "").strip()
        result = ValidationResult(cleaned_answer=text)
        if not text:
            result.valid = False
            result.warnings.append("empty_answer")
            return result

        query_lang = detect_query_language(query)
        if query_lang == "uk" and not self._looks_ukrainian(text):
            result.warnings.append("language_mismatch_expected_uk")

        for phrase in self.malformed_phrases:
            if phrase.lower() in text.lower():
                result.warnings.append(f"malformed_phrase:{phrase}")
                fixed = self._apply_simple_fix(text, phrase)
                if fixed != text:
                    result.applied_fixes.append(f"replaced:{phrase}")
                    text = fixed

        if _UNSUPPORTED_YEARS_PATTERN.search(text) and not self._years_in_context(text, context_text):
            result.warnings.append("unsupported_years_claim")
            text = _UNSUPPORTED_YEARS_PATTERN.sub("", text).strip()
            result.applied_fixes.append("removed_unsupported_years")

        word_count = len(text.split())
        limit = self.max_words if is_overview else self.max_words + 80
        if word_count > limit:
            result.warnings.append(f"answer_too_long:{word_count}>{limit}")

        result.cleaned_answer = re.sub(r"\s{2,}", " ", text).strip()
        if result.warnings:
            result.valid = not any(
                w.startswith("empty") or w.startswith("malformed_phrase")
                for w in result.warnings
            )
        return result

    @staticmethod
    def _looks_ukrainian(text: str) -> bool:
        cyr = len(re.findall(r"[\u0400-\u04FF]", text))
        lat = len(re.findall(r"[A-Za-z]{2,}", text))
        return cyr >= 3 and cyr >= lat

    @staticmethod
    def _years_in_context(answer: str, context: str) -> bool:
        nums = re.findall(r"\d{1,3}", answer)
        if not nums:
            return False
        ctx = context or ""
        return any(n in ctx for n in nums)

    @staticmethod
    def _apply_simple_fix(text: str, phrase: str) -> str:
        replacements = {
            "середньомалим": "малим і середнім",
        }
        repl = replacements.get(phrase.lower())
        if not repl:
            return text
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        return pattern.sub(repl, text)
