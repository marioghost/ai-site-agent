"""Generic site origin inference from indexed corpus (no tenant hardcode)."""
from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.source import Source


class SiteOriginService:
    """Infer the dominant website origin from indexed sources."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def dominant_origin(self, *, limit_scan: int = 5000) -> str | None:
        """Return ``scheme://host`` for the most common indexed origin, or None."""
        rows = self.db.execute(
            select(Source.url)
            .where(Source.indexed_at.is_not(None))
            .where(Source.url.is_not(None))
            .limit(limit_scan)
        ).scalars().all()
        origins: Counter[str] = Counter()
        for url in rows:
            origin = self.origin_from_url(url or "")
            if origin:
                origins[origin] += 1
        if not origins:
            return None
        return origins.most_common(1)[0][0]

    @staticmethod
    def origin_from_url(url: str) -> str | None:
        parsed = urlparse((url or "").strip())
        if not parsed.scheme or not parsed.netloc:
            return None
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return f"{parsed.scheme.lower()}://{host}"
