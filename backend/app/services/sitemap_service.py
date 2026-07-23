"""Sitemap parsing. Handles sitemap index and urlset, with nested sitemaps."""
from __future__ import annotations

from lxml import etree

from app.core.logging import get_logger
from app.services.file_fetch_service import FileFetchService
from app.utils.url_utils import normalize_url

logger = get_logger(__name__)

_SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class SitemapService:
    def __init__(self, fetcher: FileFetchService | None = None) -> None:
        self.fetcher = fetcher or FileFetchService()

    def collect_urls(self, sitemap_url: str, max_depth: int = 3) -> list[str]:
        """Recursively collect page URLs from a sitemap or sitemap index."""
        seen_sitemaps: set[str] = set()
        urls: list[str] = []
        self._collect(sitemap_url, urls, seen_sitemaps, max_depth)
        # Deduplicate while preserving order.
        deduped = list(dict.fromkeys(normalize_url(u) for u in urls))
        return deduped

    def _collect(
        self,
        sitemap_url: str,
        urls: list[str],
        seen: set[str],
        depth: int,
    ) -> None:
        if depth < 0 or sitemap_url in seen:
            return
        seen.add(sitemap_url)
        try:
            result = self.fetcher.fetch(sitemap_url)
            root = etree.fromstring(result.content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch/parse sitemap %s: %s", sitemap_url, exc)
            return

        tag = etree.QName(root).localname
        if tag == "sitemapindex":
            for sm in root.findall(f"{_SM_NS}sitemap"):
                loc = sm.find(f"{_SM_NS}loc")
                if loc is not None and loc.text:
                    self._collect(loc.text.strip(), urls, seen, depth - 1)
        elif tag == "urlset":
            for url_el in root.findall(f"{_SM_NS}url"):
                loc = url_el.find(f"{_SM_NS}loc")
                if loc is not None and loc.text:
                    urls.append(loc.text.strip())
        else:
            logger.warning("Unknown sitemap root tag '%s' at %s", tag, sitemap_url)
