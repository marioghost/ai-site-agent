"""Detect and strip site-wide boilerplate / navigation text."""
from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.source import Source

_TOKEN_RE = re.compile(r"\w{2,}", re.UNICODE)
_MIN_PHRASE_TOKENS = 4
_MIN_SOURCE_FRACTION = 0.25
_MAX_PHRASES = 200


def _normalize_phrase(text: str) -> str:
    tokens = _TOKEN_RE.findall((text or "").lower())
    if len(tokens) < _MIN_PHRASE_TOKENS:
        return ""
    return " ".join(tokens)


class BoilerplateDetectorService:
    """Corpus-level boilerplate phrase detection and per-page cleanup."""

    def __init__(self, db: Session | None = None) -> None:
        self.db = db
        self._phrases: set[str] = set()

    def build_from_sources(self, *, limit: int = 5000) -> list[str]:
        if self.db is None:
            return []
        rows = list(
            self.db.scalars(
                select(Source)
                .where(Source.status == "indexed")
                .where(Source.navigation_text.isnot(None))
                .limit(limit)
            ).all()
        )
        if len(rows) < 3:
            return []

        counter: Counter[str] = Counter()
        for row in rows:
            for field in (
                row.navigation_text,
                row.footer_text,
                row.header_text,
                row.boilerplate_text,
            ):
                phrase = _normalize_phrase(field or "")
                if phrase:
                    counter[phrase] += 1

        threshold = max(2, int(len(rows) * _MIN_SOURCE_FRACTION))
        phrases = [p for p, c in counter.most_common(_MAX_PHRASES) if c >= threshold]
        self._phrases = set(phrases)
        return phrases

    @property
    def phrases(self) -> set[str]:
        return self._phrases

    def load_phrases(self, phrases: list[str]) -> None:
        self._phrases = {p for p in phrases if p}

    def strip_boilerplate(self, text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned or not self._phrases:
            return cleaned
        lower = cleaned.lower()
        for phrase in sorted(self._phrases, key=len, reverse=True):
            if phrase and phrase in lower:
                cleaned = re.sub(re.escape(phrase), " ", cleaned, flags=re.I)
                lower = cleaned.lower()
        return re.sub(r"\s{2,}", " ", cleaned).strip()

    @staticmethod
    def boilerplate_ratio(
        *,
        main_chars: int,
        navigation_chars: int,
        footer_chars: int,
        header_chars: int,
    ) -> float:
        total = main_chars + navigation_chars + footer_chars + header_chars
        if total <= 0:
            return 0.0
        boilerplate = navigation_chars + footer_chars + header_chars
        return min(1.0, boilerplate / total)
