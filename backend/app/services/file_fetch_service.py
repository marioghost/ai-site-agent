"""HTTP fetching of pages and files via httpx."""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

_USER_AGENT = "AI-Site-Agent/1.0 (+local knowledge indexer)"


@dataclass
class FetchResult:
    url: str
    status_code: int
    content: bytes
    text: str
    content_type: str


class FileFetchService:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def fetch(self, url: str) -> FetchResult:
        """Fetch a URL. Raises httpx errors on failure."""
        headers = {"User-Agent": _USER_AGENT}
        with httpx.Client(
            timeout=self.timeout, follow_redirects=True, headers=headers
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "").lower()
            text = ""
            # Only decode as text for textual content types.
            if any(
                t in content_type
                for t in ("text", "html", "xml", "json", "javascript")
            ) or not content_type:
                text = resp.text
            return FetchResult(
                url=str(resp.url),
                status_code=resp.status_code,
                content=resp.content,
                text=text,
                content_type=content_type,
            )
