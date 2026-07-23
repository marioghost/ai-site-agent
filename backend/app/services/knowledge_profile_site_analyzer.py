"""Analyze indexed website metadata for profile generation."""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.settings import Settings
from app.models.source import Source
from app.schemas.knowledge_profile_generation import WebsiteStructureSummary
from app.services.content_signals import is_homepage_url
from app.utils.url_utils import normalize_url


_SEGMENT_RE = re.compile(r"[a-zA-Zа-яА-ЯіІїЇєЄ0-9_-]+")


class KnowledgeProfileSiteAnalyzer:
    """Stage 1 — collect structure signals from indexed sources/chunks."""

    PAGE_TYPES = {"page", "html"}

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def analyze(self) -> WebsiteStructureSummary:
        pages = list(
            self.db.scalars(
                select(Source).where(
                    Source.status == "indexed",
                    Source.source_type.in_(sorted(self.PAGE_TYPES)),
                )
            ).all()
        )
        files = list(
            self.db.scalars(
                select(Source).where(
                    Source.status == "indexed",
                    Source.source_type.notin_(sorted(self.PAGE_TYPES)),
                )
            ).all()
        )
        chunk_count = self.db.scalar(select(func.count()).select_from(Chunk)) or 0

        segment_counter: Counter[str] = Counter()
        title_samples: list[str] = []
        heading_counter: Counter[str] = Counter()
        doc_type_counter: Counter[str] = Counter()
        hint_counter: Counter[str] = Counter()
        homepage_excerpt = ""

        for src in pages:
            if src.title:
                title_samples.append(src.title.strip())
            doc_type_counter[src.document_type or "generic_page"] += 1
            path = urlparse(src.url).path.strip("/")
            for part in path.split("/"):
                token = part.lower()
                if len(token) >= 3:
                    segment_counter[token] += 1

        headings = self.db.scalars(
            select(Chunk.heading)
            .where(Chunk.heading.isnot(None), Chunk.heading != "")
            .limit(500)
        ).all()
        for h in headings:
            h_clean = (h or "").strip()
            if h_clean:
                heading_counter[h_clean.lower()] += 1

        hints = self.db.execute(
            select(Chunk.content_type_hint, func.count())
            .group_by(Chunk.content_type_hint)
        ).all()
        for hint, count in hints:
            if hint:
                hint_counter[str(hint)] += int(count)

        homepage = next(
            (
                p
                for p in pages
                if is_homepage_url(p.url)
                or (
                    self.settings.site_url
                    and normalize_url(p.url) == normalize_url(self.settings.site_url)
                )
            ),
            pages[0] if pages else None,
        )
        if homepage:
            chunk = self.db.scalars(
                select(Chunk)
                .where(Chunk.source_id == homepage.id)
                .order_by(Chunk.chunk_index)
                .limit(1)
            ).first()
            if chunk and chunk.text:
                homepage_excerpt = chunk.text[:1200]

        return WebsiteStructureSummary(
            indexed_page_count=len(pages),
            indexed_file_count=len(files),
            total_chunks=int(chunk_count),
            site_url=self.settings.site_url or "",
            top_url_segments=[
                seg for seg, _ in segment_counter.most_common(30)
            ],
            sample_titles=title_samples[:40],
            sample_headings=[h for h, _ in heading_counter.most_common(40)],
            document_type_counts=dict(doc_type_counter),
            content_hint_counts=dict(hint_counter),
            homepage_excerpt=homepage_excerpt,
        )

    def prereq_errors(self) -> list[str]:
        errors: list[str] = []
        structure = self.analyze()
        if structure.indexed_page_count == 0:
            errors.append("No indexed pages found. Run indexing first.")
        return errors
