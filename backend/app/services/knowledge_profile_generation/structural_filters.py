"""Structural filters for KP generation — no industry / locale word lists.

Locale-like path segments are detected by shape (2–3 letter alpha codes),
not by a hardcoded language catalog.
"""
from __future__ import annotations

import re

_LOCALE_SEGMENT = re.compile(r"^[a-z]{2,3}(?:-[a-z]{2,3})?$")
_SENTENCE_END = re.compile(r"[.!?…]")

# Universal URL/section stems that must not be treated as organization names.
# No vertical product vocabulary (rates/cards/loans/etc.).
SECTION_NOISE_LABELS = frozenset(
    {
        "branch",
        "branches",
        "atm",
        "atms",
        "office",
        "offices",
        "location",
        "locations",
        "contact",
        "contacts",
        "news",
        "blog",
        "faq",
        "support",
        "help",
        "home",
        "index",
        "about",
        "products",
        "services",
        "documents",
        "privacy",
        "terms",
    }
)


def is_locale_like_path_segment(segment: str) -> bool:
    """True when a URL path segment looks like a locale code (e.g. en, uk, en-us)."""
    s = (segment or "").strip().lower().replace("_", "-")
    if not s:
        return False
    return bool(_LOCALE_SEGMENT.fullmatch(s))


def first_meaningful_path_segment(segments: list[str]) -> str | None:
    """Skip locale-shaped prefixes; return the first structural section segment."""
    for seg in segments:
        if seg and not is_locale_like_path_segment(seg):
            return seg
    return None


def is_section_noise_label(name: str) -> bool:
    """True when a candidate name is only structural section vocabulary."""
    tokens = re.findall(r"[a-zA-Zа-яА-ЯіїєґІЇЄҐ]+", (name or "").lower())
    if not tokens:
        return True
    return all(t in SECTION_NOISE_LABELS or t in {"and", "the", "or"} for t in tokens)


def derive_site_subject(
    *,
    organization_name: str,
    homepage_texts: list[str],
    max_len: int = 160,
) -> str:
    """Short subject phrase from homepage text, or empty if the extract looks polluted.

    Rejects banner mashups (pipes), oversized blobs, and excerpts that do not
    relate to the organization when long.
    """
    if not homepage_texts:
        return ""
    raw = " ".join((homepage_texts[0] or "").split())
    if not raw:
        return ""
    match = _SENTENCE_END.search(raw)
    if match:
        raw = raw[: match.start()].strip()
    if "|" in raw or len(raw) > max_len:
        return ""
    org = (organization_name or "").strip()
    if org and org.lower() not in raw.lower() and len(raw) > 80:
        return ""
    return raw[:max_len]
