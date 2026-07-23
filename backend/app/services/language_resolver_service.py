"""Detect query language and prefer matching source languages."""
from __future__ import annotations

import re
from urllib.parse import urlparse

_CYRILLIC = re.compile(r"[\u0400-\u04FF]")
_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def detect_query_language(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return "unknown"
    cyr = len(_CYRILLIC.findall(raw))
    lat = len(_LATIN_WORD.findall(raw))
    if cyr >= 3 and cyr >= lat:
        return "uk"
    if lat >= 3 and lat > cyr:
        return "en"
    if cyr and lat:
        return "mixed"
    return "unknown"


def language_match_score(query_lang: str, source_lang: str) -> float:
    if query_lang == "unknown" or source_lang == "unknown":
        return 0.0
    if query_lang == source_lang:
        return 1.0
    if query_lang in {"uk", "en"} and source_lang == "mixed":
        return 0.5
    return 0.0


def normalize_url_for_lang_dedupe(url: str) -> str:
    """Strip language path segments for bilingual duplicate detection."""
    raw = (url or "").strip().lower().rstrip("/")
    if not raw:
        return ""
    parsed = urlparse(raw)
    path = parsed.path or "/"
    for seg in ("/en/", "/uk/", "/ua/", "/en-us/", "/uk-ua/"):
        path = path.replace(seg, "/")
    if path.endswith("/en") or path.endswith("/uk") or path.endswith("/ua"):
        path = path.rsplit("/", 1)[0] or "/"
    if path in {"", "/"}:
        return f"{parsed.netloc}/"
    return f"{parsed.netloc}{path.rstrip('/')}"
