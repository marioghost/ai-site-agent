"""Shared content signals: tokenization, content-type hints, homepage detection."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.knowledge_profile_service import KnowledgeProfileService

_TOKEN_RE = re.compile(r"\w{2,}", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def token_set(text: str) -> set[str]:
    return set(tokenize(text))


def normalize_content_hint(hint: str) -> str:
    if hint in ("", "general"):
        return "generic"
    return hint


def detect_content_type(*parts: str, profile: KnowledgeProfile | None = None) -> str:
    profile = profile or KnowledgeProfileService.default_profile()
    return KnowledgeProfileService.match_content_hint(profile, *parts)


def is_homepage_url(url: str) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    path = (parsed.path or "/").strip("/")
    if parsed.query:
        return False
    if path in ("", "index", "index.html", "home", "main"):
        return True
    if "/" not in path and len(path) <= 3:
        return True
    return False
