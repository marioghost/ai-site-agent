"""Domain-agnostic lexical grounding shared by profile generation stages."""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def word_tokens(text: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(text or "")}


def tokens_share_stem(left: str, right: str) -> bool:
    """Conservative morphology check without language or domain dictionaries."""
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 4 and longer.startswith(shorter)


def labels_overlap(left: str, right: str, *, threshold: float = 0.8) -> bool:
    """Detect near-duplicate labels by token containment and shared stems."""
    left_tokens = word_tokens(left)
    right_tokens = word_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    matches = sum(
        1
        for token in left_tokens
        if any(tokens_share_stem(token, other) for other in right_tokens)
    )
    return matches / min(len(left_tokens), len(right_tokens)) >= threshold
