"""Structural filters for KP generation — no industry / locale word lists.

Locale-like path segments are detected by shape (2–3 letter alpha codes),
not by a hardcoded language catalog.
"""
from __future__ import annotations

import re

_LOCALE_SEGMENT = re.compile(r"^[a-z]{2,3}(?:-[a-z]{2,3})?$")

# Universal URL/section stems that must not be treated as organization names.
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
    """Backward-compatible wrapper — prefer infer_site_identity in new code."""
    from app.services.knowledge_profile_generation.site_identity import infer_site_identity

    pages = []
    if homepage_texts:
        from app.services.knowledge_profile_generation.models import PageRecord

        pages = [
            PageRecord(
                source_id=0,
                url="/",
                title="",
                document_type="generic_page",
                path_segments=[],
                headings=[],
                texts=list(homepage_texts),
                content_hints=[],
                is_homepage=True,
            )
        ]
    identity = infer_site_identity(
        organization_name=organization_name,
        pages=pages,
        metadata=None,
        hierarchy=None,
        top_url_segments=[],
        max_subject_len=max_len,
    )
    # Wrapper API: only return an extracted sentence from homepage text.
    # Org-name / URL fallbacks belong to infer_site_identity (assembler path).
    if identity.subject_source in {"organization_name", "empty", "url_structure"}:
        return ""
    return identity.site_subject
