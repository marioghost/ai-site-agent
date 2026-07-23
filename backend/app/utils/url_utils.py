"""URL helpers: normalisation, domain checks, file-type detection."""
from __future__ import annotations

import fnmatch
import re
from urllib.parse import urljoin, urldefrag, urlparse, urlunparse

_FILE_EXTENSIONS = {
    "pdf": "pdf",
    "docx": "docx",
    "doc": "docx",
    "txt": "txt",
    "text": "txt",
    "htm": "html",
    "html": "html",
}


def normalize_url(url: str) -> str:
    """Normalise a URL: strip fragments, trailing slashes (except root)."""
    url, _ = urldefrag(url.strip())
    parsed = urlparse(url)
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    normalized = urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            parsed.query,
            "",
        )
    )
    return normalized


def get_domain(url: str) -> str:
    """Return the lowercase host (without port) for a URL."""
    netloc = urlparse(url).netloc.lower()
    return netloc.split(":")[0]


def is_allowed_domain(url: str, allowed_domains: list[str]) -> bool:
    """Return True if the URL's domain is in the allowed list.

    Subdomains of an allowed domain are also allowed. An empty list means
    "allow everything".
    """
    if not allowed_domains:
        return True
    domain = get_domain(url)
    for allowed in allowed_domains:
        allowed = allowed.lower().strip()
        if not allowed:
            continue
        if domain == allowed or domain.endswith("." + allowed):
            return True
    return False


def is_denied(url: str, deny_patterns: list[str]) -> bool:
    """Return True if URL matches any deny glob/regex-ish pattern."""
    for pattern in deny_patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        if fnmatch.fnmatch(url, pattern) or re.search(pattern, url):
            return True
    return False


def detect_file_type(url: str) -> str | None:
    """Return a normalised file type from a URL extension, or None for a page."""
    path = urlparse(url).path.lower()
    match = re.search(r"\.([a-z0-9]+)(?:$)", path)
    if not match:
        return None
    ext = match.group(1)
    return _FILE_EXTENSIONS.get(ext)


def resolve_url(base: str, link: str) -> str | None:
    """Resolve a possibly-relative link against a base URL."""
    if not link:
        return None
    link = link.strip()
    if link.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    try:
        return normalize_url(urljoin(base, link))
    except Exception:
        return None
