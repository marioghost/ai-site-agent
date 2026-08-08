"""Infer site identity (subject + entity type) from indexed evidence.

Historical intent (pre–zero-hardcode): Knowledge Profile generation filled
`organization_name`, `site_subject`, and `entity_type` so retrieval knew
*who* the site is and *what it is about*. That used to come from industry
PRESET seed tables — removed by charter.

This module restores the same fields via a flexible cascade that only reads
signals from the site itself (pages, metadata, URL structure, detected name).
No industry vocabularies, no vertical keyword maps.

Algorithm
---------
1. Collect evidence texts: about pages → homepage → metadata descriptions.
2. site_subject: first clean sentence that mentions the organization;
   else "{org} — {top site sections}" using the site's own path labels.
3. entity_type: schema.org/@type from the site if present; else a short
   phrase after a structural copula near the org name in about/homepage
   text (grammar shape, not industry lists); else dominant URL section
   label from the site; else empty.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.knowledge_profile_generation.models import (
    MetadataDataset,
    PageRecord,
    WebsiteHierarchy,
)
from app.services.knowledge_profile_generation.structural_filters import (
    SECTION_NOISE_LABELS,
    is_locale_like_path_segment,
    is_section_noise_label,
)

_SENTENCE_END = re.compile(r"[.!?…]")
# Structural copulas (grammar), not industry terms — Latin + Cyrillic scripts.
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

# Labels that are ungrounded English templates (not site vocabulary).
_PLACEHOLDER_LABEL_TOKENS = frozenset(
    {
        "about",
        "the",
        "organization",
        "organisation",
        "company",
        "website",
        "site",
        "entity",
        "business",
        "profile",
        "overview",
        "general",
        "information",
        "info",
    }
)


@dataclass(frozen=True)
class SiteIdentity:
    site_subject: str
    entity_type: str
    subject_source: str
    entity_type_source: str


def infer_site_identity(
    *,
    organization_name: str,
    pages: list[PageRecord],
    metadata: MetadataDataset | None,
    hierarchy: WebsiteHierarchy | None,
    top_url_segments: list[str] | None = None,
    max_subject_len: int = 160,
) -> SiteIdentity:
    org = (organization_name or "").strip()
    evidence = _evidence_texts(pages, hierarchy, metadata)

    subject, subject_src = _infer_subject(org, evidence, top_url_segments or [], max_subject_len)
    entity_type, type_src = _infer_entity_type(org, evidence, metadata, top_url_segments or [])

    return SiteIdentity(
        site_subject=subject,
        entity_type=entity_type,
        subject_source=subject_src,
        entity_type_source=type_src,
    )


def ground_topic_label(label: str, *, evidence_text: str, fallback: str) -> str:
    """Keep labels that appear in site evidence; replace ungrounded templates."""
    cleaned = (label or "").strip()
    if not cleaned:
        return (fallback or "").strip() or "topic"
    if not _is_ungrounded_placeholder(cleaned, evidence_text):
        return cleaned[:80]
    fb = (fallback or "").strip()
    if fb and not _is_ungrounded_placeholder(fb, evidence_text):
        return fb[:80]
    return cleaned[:80]


def _evidence_texts(
    pages: list[PageRecord],
    hierarchy: WebsiteHierarchy | None,
    metadata: MetadataDataset | None,
) -> list[tuple[str, str]]:
    """Ordered (source, text) pairs — about first, then homepage, then other.

    Prefer page body texts over title/heading mashups so subject/type are clean.
    """
    about_urls: set[str] = set()
    home_urls: set[str] = set()
    if hierarchy:
        about_urls = {c.url for c in hierarchy.categories if c.category == "about"}
        home_urls = {c.url for c in hierarchy.categories if c.category == "homepage"}

    about: list[tuple[str, str]] = []
    home: list[tuple[str, str]] = []
    other: list[tuple[str, str]] = []

    for page in pages:
        body = " ".join(" ".join(t.split()) for t in page.texts[:4] if t and t.strip())
        heading_blob = " ".join(
            " ".join(h.split()) for h in ([page.title] + list(page.headings[:3])) if h
        )
        # Body first (identity-quality); headings only as schema/JSON-LD carriers.
        chunks: list[str] = []
        if body:
            chunks.append(body)
        if heading_blob and heading_blob.lower() not in (body or "").lower():
            chunks.append(heading_blob)
        if not chunks:
            continue

        bucket = other
        if page.is_homepage or page.url in home_urls:
            bucket = home
        elif page.url in about_urls or (
            page.path_segments[:1]
            and page.path_segments[0].lower() in {"about", "about-us", "about_us"}
        ):
            bucket = about

        for i, chunk in enumerate(chunks):
            bucket.append((f"{page.url}#{i}", chunk))

    if metadata:
        for meta in metadata.pages:
            if meta.meta_description:
                about.insert(0, (f"meta:{meta.url}", meta.meta_description))

    return about + home + other[:16]


def _infer_subject(
    org: str,
    evidence: list[tuple[str, str]],
    top_segments: list[str],
    max_len: int,
) -> tuple[str, str]:
    for source, text in evidence:
        sentence = _first_clean_sentence(text, org=org, max_len=max_len)
        if sentence:
            return sentence, source.split("#", 1)[0]

    if org:
        sections = _site_section_labels(top_segments, limit=3)
        if sections:
            return f"{org} — {', '.join(sections)}"[:max_len], "url_structure"
        return org[:max_len], "organization_name"
    return "", "empty"


_SCHEMA_TYPE_RE = re.compile(r'"@type"\s*:\s*"([^"]+)"', re.IGNORECASE)
_SCHEMA_UTILITY_TYPES = frozenset(
    {
        "thing",
        "webpage",
        "website",
        "breadcrumblist",
        "listitem",
        "imageobject",
        "searchaction",
        "wpheader",
        "wpfooter",
        "sitenavigationelement",
    }
)
_AFTER_ORG_COPULA = re.compile(
    r"^[\s,\-–—]*"
    r"(?:[\w.'’-]{1,40}\s+){0,4}"
    r"(?:"
    r"(?:is|are|was|were)\s+(?:a|an|the)\s+"
    r"|(?:є|це)\s+"
    r"|является\s+"
    r")"
    r"(?P<body>[^|.!?;\n]{3,80})",
    re.IGNORECASE,
)


def _schema_type_from_text(text: str) -> str:
    for match in _SCHEMA_TYPE_RE.finditer(text or ""):
        raw = match.group(1).strip()
        if not raw:
            continue
        # Take last path segment of schema.org URLs / multi-types
        name = raw.split("/")[-1].split(",")[0].strip()
        if name.lower() in _SCHEMA_UTILITY_TYPES:
            continue
        if len(name) < 3 or len(name) > 40:
            continue
        return name
    return ""


def _infer_entity_type(
    org: str,
    evidence: list[tuple[str, str]],
    metadata: MetadataDataset | None,
    top_segments: list[str],
) -> tuple[str, str]:
    for source, text in evidence[:12]:
        schema = _schema_type_from_text(text)
        if schema:
            return schema, f"schema:{source.split('#', 1)[0]}"

    del metadata  # reserved; names alone are not types

    if org:
        for source, text in evidence[:10]:
            extracted = _definitional_type(org, text)
            if extracted:
                return extracted, source.split("#", 1)[0]

    dominant = _dominant_section_type(top_segments)
    if dominant:
        return dominant, "url_structure"

    return "", "empty"


def _definitional_type(org: str, text: str) -> str:
    """Extract 'Org is a Y' type phrase anchored on the organization name."""
    if not org or not text:
        return ""
    lower = text.lower()
    candidates = [org]
    token = org.split()[0] if org.split() else org
    if token.lower() != org.lower():
        candidates.append(token)

    for cand in candidates:
        cand_l = cand.lower()
        start = 0
        while True:
            idx = lower.find(cand_l, start)
            if idx < 0:
                break
            after = text[idx + len(cand) :]
            match = _AFTER_ORG_COPULA.match(after)
            if match:
                phrase = _clean_type_phrase(match.group("body"))
                if phrase:
                    return phrase
            start = idx + max(len(cand), 1)
    return ""


def _clean_type_phrase(body: str) -> str:
    raw = " ".join((body or "").split())
    if not raw or "|" in raw:
        return ""
    # Cut trailing clauses
    for sep in (",", " - ", " – ", " — ", " that ", " which ", " який", " яка", " що "):
        if sep in raw:
            raw = raw.split(sep, 1)[0].strip()
    words = _WORD.findall(raw)
    if not words:
        return ""
    # Keep a short noun phrase (1–5 tokens); drop pure section-noise phrases.
    kept = words[:5]
    phrase = " ".join(kept)
    if is_section_noise_label(phrase):
        return ""
    if len(phrase) < 3 or len(phrase) > 60:
        return ""
    return phrase


def _dominant_section_type(top_segments: list[str]) -> str:
    """Use the site's own dominant URL section as a soft type hint."""
    counts: dict[str, int] = {}
    for seg in top_segments:
        if not seg or is_locale_like_path_segment(seg):
            continue
        key = seg.lower().replace("_", "-")
        if key in SECTION_NOISE_LABELS or key in {"homepage", "general"}:
            continue
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return ""
    best, n = max(counts.items(), key=lambda x: x[1])
    total = sum(counts.values())
    if n < 2 or n / max(total, 1) < 0.35:
        return ""
    return best.replace("-", " ")


def _site_section_labels(top_segments: list[str], *, limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for seg in top_segments:
        if not seg or is_locale_like_path_segment(seg):
            continue
        label = seg.replace("-", " ").replace("_", " ").strip()
        key = label.lower()
        if not label or key in seen or key in SECTION_NOISE_LABELS:
            continue
        if is_section_noise_label(label):
            continue
        seen.add(key)
        out.append(label)
        if len(out) >= limit:
            break
    return out


def _first_clean_sentence(text: str, *, org: str, max_len: int) -> str:
    raw = " ".join((text or "").split())
    if not raw:
        return ""
    # Prefer a sentence that mentions the organization.
    parts: list[str] = []
    start = 0
    for match in _SENTENCE_END.finditer(raw):
        parts.append(raw[start : match.start()].strip())
        start = match.end()
    if start < len(raw):
        parts.append(raw[start:].strip())
    if not parts:
        parts = [raw]

    org_l = (org or "").lower()
    ordered = parts
    if org_l:
        with_org = [p for p in parts if org_l in p.lower()]
        if with_org:
            ordered = with_org + [p for p in parts if p not in with_org]

    for part in ordered:
        candidate = part.strip(" .,;|")
        if not candidate or "|" in candidate:
            continue
        if len(candidate) > max_len:
            continue
        if org_l:
            # Subject must mention the organization when we know the name.
            if org_l not in candidate.lower():
                # Allow first token of multi-word org names
                token = org_l.split()[0]
                if len(token) < 3 or token not in candidate.lower():
                    continue
        # Skip pure nav noise
        if is_section_noise_label(candidate):
            continue
        return candidate[:max_len]
    return ""


def _is_ungrounded_placeholder(label: str, evidence_text: str) -> bool:
    tokens = [t.lower() for t in _WORD.findall(label)]
    if not tokens:
        return True
    if not all(t in _PLACEHOLDER_LABEL_TOKENS for t in tokens):
        return False
    # Placeholder-only label: require it literally appear in evidence to keep.
    ev = (evidence_text or "").lower()
    return label.lower() not in ev
