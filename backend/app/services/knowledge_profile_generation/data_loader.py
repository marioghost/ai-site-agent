"""Load indexed pages from SQLite for profile generation."""
from __future__ import annotations

import json
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.settings import Settings
from app.models.source import Source
from app.schemas.source_intelligence import SourceSemanticProfile
from app.services.content_signals import is_homepage_url
from app.services.knowledge_profile_generation.models import PageRecord
from app.utils.url_utils import normalize_url


class IndexedPageLoader:
    PAGE_TYPES = {"page", "html"}

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def load(self) -> list[PageRecord]:
        pages = list(
            self.db.scalars(
                select(Source).where(
                    Source.status == "indexed",
                    Source.source_type.in_(sorted(self.PAGE_TYPES)),
                )
            ).all()
        )
        site_norm = normalize_url(self.settings.site_url) if self.settings.site_url else ""
        site_host = ""
        if self.settings.site_url:
            site_host = urlparse(self.settings.site_url).netloc.replace("www.", "").lower()

        records: list[PageRecord] = []
        for src in pages:
            if site_host:
                src_host = urlparse(src.url).netloc.replace("www.", "").lower()
                if src_host != site_host:
                    continue
            chunks = list(
                self.db.scalars(
                    select(Chunk)
                    .where(Chunk.source_id == src.id)
                    .order_by(Chunk.chunk_index)
                ).all()
            )
            path = urlparse(src.url).path.strip("/")
            segments = [p.lower() for p in path.split("/") if len(p) >= 2]
            is_home = is_homepage_url(src.url) or (
                bool(site_norm) and normalize_url(src.url) == site_norm
            )
            semantic = self._semantic_profile(src.intelligence_json)
            chunk_texts = [c.text for c in chunks if c.text]
            main_text = (src.main_content_text or "").strip()
            texts = list(chunk_texts)
            if main_text and all(main_text != text.strip() for text in chunk_texts):
                texts.insert(0, main_text)
            records.append(
                PageRecord(
                    source_id=src.id,
                    url=src.url,
                    title=(src.title or "").strip(),
                    document_type=src.document_type or "generic_page",
                    path_segments=segments,
                    headings=[c.heading.strip() for c in chunks if c.heading],
                    texts=texts,
                    content_hints=[c.content_type_hint for c in chunks if c.content_type_hint],
                    is_homepage=is_home,
                    main_text=main_text,
                    footer_text=(src.footer_text or "").strip(),
                    semantic_profile=semantic,
                    canonical=bool(src.canonical),
                    importance=int(src.importance or 0),
                )
            )
        return records

    @staticmethod
    def _semantic_profile(raw: str | None) -> SourceSemanticProfile | None:
        try:
            data = json.loads(raw or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return SourceSemanticProfile.from_storage(data)

    def prereq_errors(self, pages: list[PageRecord] | None = None) -> list[str]:
        if pages is None:
            pages = self.load()
        if not pages:
            return ["No indexed pages found. Run indexing first."]
        return []
