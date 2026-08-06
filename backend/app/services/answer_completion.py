"""Deterministic answer finishing helpers (no LLM)."""
from __future__ import annotations

import re

_SENTENCE_END = re.compile(r"[.!?…][\"'»”’)\]]*")


def finish_if_truncated(text: str, *, truncated: bool) -> str:
    """If generation hit a hard token ceiling mid-thought, keep the last complete sentence.

    This is recovery from an incomplete stream — not a length policy. Complete
    answers (done_reason=stop) are returned unchanged.
    """
    raw = (text or "").rstrip()
    if not truncated or not raw:
        return raw
    if _SENTENCE_END.search(raw[-12:] if len(raw) >= 12 else raw):
        return raw
    ends = list(_SENTENCE_END.finditer(raw))
    if not ends:
        return raw
    return raw[: ends[-1].end()].rstrip()


def preview_prompt(text: str, limit: int = 2000) -> str:
    """Diagnostics preview that keeps both Sources head and Task/Question tail."""
    raw = text or ""
    if len(raw) <= limit:
        return raw
    head = max(400, limit // 2)
    tail = max(400, limit - head - 5)
    return f"{raw[:head]}\n...\n{raw[-tail:]}"
