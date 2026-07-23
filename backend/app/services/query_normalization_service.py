"""Normalize user queries for caching and embedding.

Normalisation keeps the meaning intact while collapsing trivial differences
(whitespace, case, trailing punctuation) so that semantically identical queries
map to the same cache key.
"""
from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")
# Punctuation noise to strip from the ends only (keeps inner punctuation).
_EDGE_NOISE = " \t\n\r?!.,;:«»\"'()[]"


class QueryNormalizationService:
    @staticmethod
    def normalize(text: str) -> str:
        if not text:
            return ""
        normalized = _WS_RE.sub(" ", text.strip().lower())
        normalized = normalized.strip(_EDGE_NOISE)
        return normalized
