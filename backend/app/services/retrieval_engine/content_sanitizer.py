"""Strip UI chrome and boilerplate from context text sent to the LLM."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

_UI_JUNK_PATTERNS = re.compile(
    r"(?:^|\s)(?:×|✕|☰|≡|\||›|»|←|→)(?:\s|$)|"
    r"\b(?:детальніше|читати далі|read more|learn more|click here|"
    r"sign up|log in|subscribe|menu|navigation|breadcrumb)\b",
    re.I | re.M,
)
_TITLE_PIPE = re.compile(r"^[^|\n]{0,80}\|\s*[^|\n]{0,80}\s*(?:—|–|-)\s*[^|\n]{0,80}$", re.M)
_EMPTY_HEADING = re.compile(r"^#{1,6}\s*$", re.M)
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_BLANK_LINES = re.compile(r"\n{3,}")
_DEBUG_MARKERS = re.compile(r"(?:@TODO|TODO:|FIXME|lorem ipsum)", re.I)
_INCIDENTAL_SECTION = re.compile(
    r"\b(compliance|privacy|cookie|charity|donation|career|vacancy|recruitment|"
    r"sustainability|esg|environmental|boilerplate|terms of use|gdpr|"
    r"equal opportunity|accessibility statement)\b",
    re.I,
)
_OVERVIEW_SECTION = re.compile(
    r"\b(about|overview|mission|identity|who we are|our story|history|"
    r"services|activity|purpose|introduction|profile|who are we|"
    r"what we do|company profile|organization)\b",
    re.I,
)
_HEADING_SPLIT = re.compile(r"^(#{1,6}\s+.+)$", re.M)


def strip_ui_junk(text: str) -> str:
    if not text:
        return ""
    out = text
    out = _UI_JUNK_PATTERNS.sub(" ", out)
    out = _TITLE_PIPE.sub("", out)
    out = _EMPTY_HEADING.sub("", out)
    out = _MULTI_SPACE.sub(" ", out)
    out = _BLANK_LINES.sub("\n\n", out)
    return out.strip()


def extract_lead_paragraphs(text: str, max_chars: int) -> str:
    """Prefer informative opening paragraphs over chunk/title fragments."""
    cleaned = strip_ui_junk(text)
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned
    paragraphs: list[str] = []
    total = 0
    for block in re.split(r"\n\s*\n", cleaned):
        p = block.strip()
        if len(p) < 40:
            continue
        if _looks_like_nav_line(p):
            continue
        if total + len(p) + 2 > max_chars:
            remaining = max_chars - total - 2
            if remaining > 80:
                paragraphs.append(p[:remaining].rstrip() + "…")
            break
        paragraphs.append(p)
        total += len(p) + 2
    if paragraphs:
        return "\n\n".join(paragraphs)[:max_chars]
    return cleaned[:max_chars]


def _looks_like_nav_line(line: str) -> bool:
    lower = line.lower()
    if len(line) < 60 and line.count("|") >= 2:
        return True
    nav_markers = ("головна", "home", "контакти", "contact", "меню", "footer", "cookie")
    hits = sum(1 for m in nav_markers if m in lower)
    return hits >= 2 and len(line) < 120


def clean_context_text(text: str, *, max_chars: int) -> str:
    cleaned = strip_ui_junk(text)
    cleaned = _DEBUG_MARKERS.sub("", cleaned)
    if len(cleaned) < 200:
        lead = extract_lead_paragraphs(cleaned, max_chars)
        if len(lead) > len(cleaned):
            cleaned = lead
    return cleaned[:max_chars]


def extract_overview_excerpt(
    text: str,
    *,
    max_chars: int,
    chunk_hint: str = "",
    prefer_identity: bool = True,
) -> str:
    """Prefer introductory identity sections for overview-style sources."""
    cleaned = strip_ui_junk(text)
    cleaned = _DEBUG_MARKERS.sub("", cleaned)
    if not cleaned:
        return ""
    sections = _split_sections(cleaned)
    if len(sections) <= 1:
        if len(cleaned) <= max_chars:
            return cleaned
        lead = extract_lead_paragraphs(cleaned, max_chars)
        if chunk_hint:
            hinted = _window_by_hint(cleaned, chunk_hint, max_chars)
            if _section_score(hinted, prefer_identity) >= _section_score(lead, prefer_identity):
                return hinted
        return lead

    if prefer_identity and len(cleaned) <= max_chars:
        best = max(sections, key=lambda s: _section_score(s, prefer_identity, chunk_hint=chunk_hint))
        return best[:max_chars]

    if len(cleaned) <= max_chars:
        return cleaned

    scored = sorted(
        sections,
        key=lambda s: _section_score(s, prefer_identity, chunk_hint=chunk_hint),
        reverse=True,
    )
    parts: list[str] = []
    total = 0
    for section in scored:
        if total + len(section) + 2 > max_chars:
            remaining = max_chars - total - 2
            if remaining > 120:
                parts.append(section[:remaining].rstrip() + "…")
            break
        parts.append(section)
        total += len(section) + 2
    if parts:
        return "\n\n".join(parts)[:max_chars]
    return extract_lead_paragraphs(cleaned, max_chars)


def dedupe_near_duplicate_text(existing: str, candidate: str, *, threshold: float = 0.82) -> bool:
    """Return True when candidate is a near-duplicate of existing text."""
    if not existing or not candidate:
        return False
    a = existing[:1200].lower()
    b = candidate[:1200].lower()
    if a == b or b in a or a in b:
        return True
    return SequenceMatcher(None, a, b).ratio() >= threshold


def _split_sections(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if _HEADING_SPLIT.match(line.strip()):
            if current:
                block = "\n".join(current).strip()
                if block:
                    parts.append(block)
                current = []
            current.append(line.strip())
        else:
            current.append(line)
    if current:
        block = "\n".join(current).strip()
        if block:
            parts.append(block)
    if not parts:
        return [text.strip()]
    return parts


def _section_score(section: str, prefer_identity: bool, *, chunk_hint: str = "") -> float:
    score = 0.0
    heading = section.splitlines()[0] if section else ""
    body = section
    if prefer_identity:
        if _OVERVIEW_SECTION.search(heading):
            score += 3.0
        elif _OVERVIEW_SECTION.search(body[:400]):
            score += 1.5
        if _INCIDENTAL_SECTION.search(heading):
            score -= 4.0
        elif _INCIDENTAL_SECTION.search(body[:500]):
            score -= 2.0
    if chunk_hint:
        hint_words = {w.lower() for w in chunk_hint.split() if len(w) > 3}
        window = section.lower()
        score += sum(0.15 for w in hint_words if w in window)
    if _looks_like_nav_line(section[:160]):
        score -= 2.0
    if len(section) < 60:
        score -= 1.0
    # Prefer earlier identity lead when scores tie.
    score += min(0.5, len(body) / 4000.0)
    return score


def _window_by_hint(main_content: str, chunk_hint: str, max_chars: int) -> str:
    hint_words = {w.lower() for w in chunk_hint.split() if len(w) > 3}
    if not hint_words:
        return main_content[:max_chars]
    best_start = 0
    best_score = -1.0
    step = max(200, max_chars // 4)
    for start in range(0, max(1, len(main_content) - max_chars), step):
        window = main_content[start : start + max_chars]
        score = sum(1 for w in hint_words if w in window.lower())
        score += _section_score(window, True)
        if score > best_score:
            best_score = score
            best_start = start
    return main_content[best_start : best_start + max_chars]
