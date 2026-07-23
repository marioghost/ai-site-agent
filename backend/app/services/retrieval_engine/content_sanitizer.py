"""Strip UI chrome and boilerplate from context text sent to the LLM."""
from __future__ import annotations

import re

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
    if len(cleaned) < 200:
        lead = extract_lead_paragraphs(cleaned, max_chars)
        if len(lead) > len(cleaned):
            cleaned = lead
    return cleaned[:max_chars]
