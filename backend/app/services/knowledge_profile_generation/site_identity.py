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
from app.services.knowledge_profile_generation.lexical_grounding import (
    tokens_share_stem,
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
    evidence_snippets: tuple[str, ...] = ()


def infer_site_identity(
    *,
    organization_name: str,
    pages: list[PageRecord],
    metadata: MetadataDataset | None,
    hierarchy: WebsiteHierarchy | None,
    top_url_segments: list[str] | None = None,
    max_subject_len: int = 160,
    topic_labels: list[str] | None = None,
) -> SiteIdentity:
    org = (organization_name or "").strip()
    evidence = _rank_identity_evidence(
        org,
        _evidence_texts(pages, hierarchy, metadata),
    )

    subject, subject_src = _infer_subject(
        org,
        evidence,
        top_url_segments or [],
        topic_labels or [],
        max_subject_len,
    )
    entity_type, type_src = _infer_entity_type(
        org,
        evidence,
        pages,
        metadata,
        top_url_segments or [],
    )

    return SiteIdentity(
        site_subject=subject,
        entity_type=entity_type,
        subject_source=subject_src,
        entity_type_source=type_src,
        evidence_snippets=_identity_snippets(evidence, org=org),
    )


def _rank_identity_evidence(
    org: str,
    evidence: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    indexed = list(enumerate(evidence))

    def quality(item: tuple[int, tuple[str, str]]) -> tuple[int, int]:
        index, (_, text) = item
        if _definitional_type(org, text):
            return 3, -index
        if _mentions_name(text, org):
            return 2, -index
        return 1, -index

    indexed.sort(key=quality, reverse=True)
    return [item for _, item in indexed]


def _identity_snippets(
    evidence: list[tuple[str, str]],
    *,
    org: str,
) -> tuple[str, ...]:
    seen: set[str] = set()
    snippets: list[str] = []
    for _, text in evidence:
        cleaned = " ".join((text or "").split())[:500]
        key = cleaned.casefold()
        if not cleaned or key in seen or (org and not _mentions_name(cleaned, org)):
            continue
        seen.add(key)
        snippets.append(cleaned)
        if len(snippets) >= 12:
            break
    return tuple(snippets)


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


def is_grounded_in_evidence(
    value: str,
    evidence: list[str],
    *,
    minimum_token_coverage: float = 0.3,
) -> bool:
    """Validate generated identity text against corpus vocabulary."""
    tokens = {
        token.casefold()
        for token in _WORD.findall(value or "")
        if len(token) >= 4
    }
    if not tokens:
        return False
    evidence_tokens = {
        token.casefold()
        for text in evidence
        for token in _WORD.findall(text or "")
        if len(token) >= 4
    }
    if not evidence_tokens:
        return False
    grounded = {
        token
        for token in tokens
        if any(tokens_share_stem(token, candidate) for candidate in evidence_tokens)
    }
    coverage = len(grounded) / len(tokens)
    return coverage >= minimum_token_coverage


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

    # PageMetadata.meta_description is extracted from page text in this
    # pipeline, not a distinct authoritative signal. Re-adding every value
    # here would duplicate evidence and promote arbitrary pages to About.
    del metadata

    return about + home + other


def _infer_subject(
    org: str,
    evidence: list[tuple[str, str]],
    top_segments: list[str],
    topic_labels: list[str],
    max_len: int,
) -> tuple[str, str]:
    # Site-wide concepts outrank any single page: they represent recurring,
    # corpus-level understanding rather than one campaign or local page role.
    if org:
        topics = _site_topic_labels(topic_labels, org=org, limit=3)
        if topics:
            return f"{org} — {', '.join(topics)}"[:max_len], "site_understanding"

    # A self-definition is stronger identity evidence than banners, alerts,
    # promotions, or other transient sentences that merely mention the name.
    for source, text in evidence:
        sentence = _definitional_sentence(text, org=org, max_len=max_len)
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
    pages: list[PageRecord],
    metadata: MetadataDataset | None,
    top_segments: list[str],
) -> tuple[str, str]:
    for source, text in evidence[:12]:
        schema = _schema_type_from_text(text)
        if schema:
            return schema, f"schema:{source.split('#', 1)[0]}"

    del metadata  # reserved; names alone are not types

    semantic_type = _dominant_semantic_entity_type(pages)
    if semantic_type:
        return semantic_type, "source_intelligence"

    if org:
        for source, text in evidence[:10]:
            extracted = _definitional_type(org, text)
            if extracted:
                return extracted, source.split("#", 1)[0]

    dominant = _dominant_section_type(top_segments)
    if dominant:
        return dominant, "url_structure"

    return "", "empty"


def _dominant_semantic_entity_type(pages: list[PageRecord]) -> str:
    identity_pages = [page for page in pages if page.is_homepage]
    if not identity_pages:
        identity_pages = [page for page in pages if page.canonical]
    if not identity_pages:
        identity_pages = pages

    scores: dict[str, float] = {}
    labels: dict[str, str] = {}
    support: dict[str, set[int]] = {}
    for page in identity_pages:
        semantic = page.semantic_profile
        if semantic is None:
            continue
        label = (semantic.entity_type or "").strip()
        confidence = float(semantic.entity_type_confidence or 0.0)
        if not label or confidence <= 0.0:
            continue
        key = label.casefold()
        labels.setdefault(key, label)
        scores[key] = scores.get(key, 0.0) + confidence
        support.setdefault(key, set()).add(page.source_id)
    if not scores:
        return ""
    best = max(scores, key=lambda key: (scores[key], len(support[key])))
    count = len(support[best])
    mean_confidence = scores[best] / max(count, 1)
    minimum_support = 1 if len(identity_pages) == 1 else 2
    if count < minimum_support or mean_confidence < 0.5:
        return ""
    return labels[best][:60]


def _definitional_type(org: str, text: str) -> str:
    """Extract 'Org is a Y' type phrase anchored on the organization name."""
    if not org or not text:
        return ""
    lower = text.lower()
    for cand in [org]:
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


def _site_topic_labels(
    topic_labels: list[str],
    *,
    org: str,
    limit: int,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in topic_labels:
        label = " ".join((raw or "").split()).strip(" .,;|")
        key = label.casefold()
        if not label or key in seen or key == org.casefold():
            continue
        if len(label) > 60 or is_section_noise_label(label):
            continue
        seen.add(key)
        out.append(label)
        if len(out) >= limit:
            break
    return out


def _definitional_sentence(text: str, *, org: str, max_len: int) -> str:
    raw = " ".join((text or "").split())
    if not raw or not org:
        return ""
    start = 0
    parts: list[str] = []
    for match in _SENTENCE_END.finditer(raw):
        parts.append(raw[start : match.start()].strip())
        start = match.end()
    if start < len(raw):
        parts.append(raw[start:].strip())
    for part in parts:
        candidate = part.strip(" .,;|")
        if (
            candidate
            and "|" not in candidate
            and len(candidate) <= max_len
            and _mentions_name(candidate, org)
            and _definitional_type(org, candidate)
        ):
            return candidate
    return ""


def _mentions_name(text: str, name: str) -> bool:
    """Match a complete identity phrase, never an arbitrary first token."""
    text_tokens = [t.casefold() for t in _WORD.findall(text)]
    name_tokens = [t.casefold() for t in _WORD.findall(name)]
    if not text_tokens or not name_tokens:
        return False
    width = len(name_tokens)
    if any(
        text_tokens[i : i + width] == name_tokens
        for i in range(len(text_tokens) - width + 1)
    ):
        return True
    # Permit punctuation/spacing differences for a substantial compact name,
    # but never degrade a multi-word identity to one common word.
    compact_name = "".join(name_tokens)
    compact_text = "".join(text_tokens)
    return len(compact_name) >= 6 and compact_name in compact_text


def _is_ungrounded_placeholder(label: str, evidence_text: str) -> bool:
    tokens = [t.lower() for t in _WORD.findall(label)]
    if not tokens:
        return True
    if not all(t in _PLACEHOLDER_LABEL_TOKENS for t in tokens):
        return False
    # Placeholder-only label: require it literally appear in evidence to keep.
    ev = (evidence_text or "").lower()
    return label.lower() not in ev
