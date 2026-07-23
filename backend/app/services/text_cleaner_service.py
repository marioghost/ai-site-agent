"""Text cleanup helpers used after extraction."""
from __future__ import annotations

import re


class TextCleanerService:
    """Normalise whitespace and strip noise from extracted text."""

    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""
        # Normalise newlines.
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Collapse 3+ newlines into 2 (paragraph break).
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Strip trailing spaces per line.
        lines = [line.strip() for line in text.split("\n")]
        # Drop empty leading/trailing lines and collapse runs of spaces.
        cleaned_lines = []
        for line in lines:
            line = re.sub(r"[ \t]{2,}", " ", line)
            cleaned_lines.append(line)
        text = "\n".join(cleaned_lines).strip()
        return text

    @staticmethod
    def normalize_for_hash(text: str) -> str:
        return " ".join((text or "").split())
