"""Format retrieved chunks into a clean, deduplicated source list for answers."""
from __future__ import annotations

from dataclasses import dataclass

from app.services.qdrant_service import SearchHit

_MAX_SOURCES = 5


@dataclass
class FormattedSource:
    title: str
    url: str
    source_type: str
    score: float


class SourceFormattingService:
    @staticmethod
    def format(hits: list[SearchHit], limit: int = _MAX_SOURCES) -> list[FormattedSource]:
        """Deduplicate by URL, drop empty URLs, sort by score desc, cap to limit."""
        best: dict[str, FormattedSource] = {}
        for hit in hits:
            url = (hit.url or "").strip()
            if not url:
                continue
            existing = best.get(url)
            if existing is None or hit.score > existing.score:
                best[url] = FormattedSource(
                    title=(hit.title or url).strip(),
                    url=url,
                    source_type=hit.source_type or "page",
                    score=round(float(hit.score), 4),
                )
        ranked = sorted(best.values(), key=lambda s: s.score, reverse=True)
        return ranked[: max(0, limit)]
