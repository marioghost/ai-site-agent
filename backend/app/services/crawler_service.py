"""Crawl frontier management: visited tracking, depth, domain/deny filtering.

The actual fetching/parsing happens in the indexing worker (so each page is
fetched only once). This service just decides what is allowed and tracks state.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from app.utils.url_utils import is_allowed_domain, is_denied, normalize_url


@dataclass
class CrawlItem:
    url: str
    depth: int


class CrawlFrontier:
    def __init__(
        self,
        allowed_domains: list[str],
        deny_patterns: list[str],
        max_depth: int,
    ) -> None:
        self.allowed_domains = allowed_domains
        self.deny_patterns = deny_patterns
        self.max_depth = max_depth
        self._queue: deque[CrawlItem] = deque()
        self._visited: set[str] = set()

    def seen(self, url: str) -> bool:
        return normalize_url(url) in self._visited

    def mark_visited(self, url: str) -> None:
        self._visited.add(normalize_url(url))

    def can_visit(self, url: str) -> bool:
        url = normalize_url(url)
        if url in self._visited:
            return False
        if not url.startswith(("http://", "https://")):
            return False
        if not is_allowed_domain(url, self.allowed_domains):
            return False
        if is_denied(url, self.deny_patterns):
            return False
        return True

    def add(self, url: str, depth: int) -> None:
        url = normalize_url(url)
        if depth > self.max_depth:
            return
        if self.can_visit(url) and not self._is_queued(url):
            self._queue.append(CrawlItem(url=url, depth=depth))

    def _is_queued(self, url: str) -> bool:
        return any(item.url == url for item in self._queue)

    def pop(self) -> CrawlItem | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    def has_next(self) -> bool:
        return bool(self._queue)

    @property
    def visited_count(self) -> int:
        return len(self._visited)

    @property
    def visited_urls(self) -> set[str]:
        return set(self._visited)
