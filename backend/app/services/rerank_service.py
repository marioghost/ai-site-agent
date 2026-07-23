"""Lightweight MVP reranker.

Combines the vector similarity score with cheap lexical signals (keyword overlap
in the chunk text and title) to push the most on-topic chunks to the top. No
external/heavy reranker model is required.
"""
from __future__ import annotations

import re

from app.services.qdrant_service import SearchHit

# Unicode-aware word tokens (handles Cyrillic), at least 2 chars long.
_TOKEN_RE = re.compile(r"\w{2,}", re.UNICODE)

_TEXT_WEIGHT = 0.15
_TITLE_WEIGHT = 0.10


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


class RerankService:
    @staticmethod
    def rerank(query: str, hits: list[SearchHit]) -> list[SearchHit]:
        """Return hits sorted by a combined vector + lexical score.

        The original ``hit.score`` (vector similarity) is preserved on each hit;
        only the ordering changes.
        """
        q_tokens = _tokens(query)
        if not q_tokens or not hits:
            return hits

        def combined(hit: SearchHit) -> float:
            text_tokens = _tokens(hit.text)
            title_tokens = _tokens(hit.title)
            text_overlap = len(q_tokens & text_tokens) / len(q_tokens)
            title_overlap = len(q_tokens & title_tokens) / len(q_tokens)
            return hit.score + _TEXT_WEIGHT * text_overlap + _TITLE_WEIGHT * title_overlap

        return sorted(hits, key=combined, reverse=True)
