"""Lightweight language helpers (no heavy dependencies)."""
from __future__ import annotations

import re

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def guess_language(text: str) -> str:
    """Very rough language guess: 'uk'/'ru' for Cyrillic, else 'en'.

    This is intentionally simple; the LLM is instructed to answer in the
    user's language anyway. Used only for optional metadata/logging.
    """
    sample = text[:2000]
    if _CYRILLIC_RE.search(sample):
        return "uk"
    return "en"
