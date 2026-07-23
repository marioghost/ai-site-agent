"""Shared retrieval scoring helpers (main vs boilerplate token matches)."""
from __future__ import annotations

from app.services.content_signals import token_set

_MAIN_PREVIEW_CHARS = 800
_MAIN_HEAD_CHARS = 120
_NAV_ONLY_PENALTY = 0.28
_HIGH_BOILERPLATE_PENALTY = 0.18
_BOILERPLATE_RATIO_THRESHOLD = 0.55


def score_content_match(
    *,
    query_tokens: set[str],
    title: str,
    heading: str,
    text: str,
    url: str,
    title_boost: float,
    heading_boost: float,
    boilerplate_ratio: float = 0.0,
) -> tuple[float, float, float, float, float, str]:
    """Return title, main, url, boilerplate penalty, nav-only penalty, reason."""
    if not query_tokens:
        return 0.0, 0.0, 0.0, 0.0, 0.0, ""

    title_tokens = token_set(title)
    heading_tokens = token_set(heading)
    body = text or ""
    main_preview = body[: min(_MAIN_HEAD_CHARS, len(body))]
    tail_preview = body[len(main_preview) :]
    main_tokens = token_set(main_preview)
    tail_tokens = token_set(tail_preview)
    url_tokens = token_set(url.replace("/", " ").replace("-", " "))

    title_hits = query_tokens & title_tokens
    heading_hits = query_tokens & heading_tokens
    main_hits = query_tokens & main_tokens
    tail_hits = query_tokens & tail_tokens
    url_hits = query_tokens & url_tokens
    full_hits = query_tokens & token_set(f"{title} {heading} {body}")

    title_score = title_boost if title_hits else 0.0
    if heading_hits:
        title_score += heading_boost

    main_score = 0.0
    if main_hits:
        main_score = min(title_boost, 0.12) * (len(main_hits) / max(1, len(query_tokens)))
    if title_hits or heading_hits:
        main_score += min(0.08, 0.04 * len(title_hits | heading_hits))

    url_score = 0.06 if url_hits else 0.0

    nav_penalty = 0.0
    reason = ""
    if full_hits and not (title_hits or heading_hits or main_hits or url_hits):
        nav_penalty = _NAV_ONLY_PENALTY
        reason = "query_terms_nav_only"
    elif tail_hits and not (title_hits or heading_hits or main_hits or url_hits):
        nav_penalty = _NAV_ONLY_PENALTY * 0.85
        reason = "query_terms_tail_only"

    boilerplate_penalty = 0.0
    if boilerplate_ratio >= _BOILERPLATE_RATIO_THRESHOLD:
        boilerplate_penalty = _HIGH_BOILERPLATE_PENALTY * boilerplate_ratio
        reason = reason or "high_boilerplate_ratio"

    return title_score, main_score, url_score, boilerplate_penalty, nav_penalty, reason
