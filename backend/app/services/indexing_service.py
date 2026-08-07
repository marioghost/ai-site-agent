"""Index a single source document: fetch -> extract -> hash -> chunk -> embed -> upsert.

Shared by the full-site indexing worker and the single-source reindex endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.chunk import Chunk
from app.models.settings import Settings
from app.models.source import Source
from app.repositories.source_repository import SourceRepository
from app.services.boilerplate_detector_service import BoilerplateDetectorService
from app.services.chunking_service import ChunkingService
from app.services.content_extraction_constants import (
    CHUNKING_VERSION,
    CLASSIFICATION_VERSION,
    EXTRACTION_VERSION,
)
from app.services.docx_parser_service import DocxParserService
from app.services.embedding_service import EmbeddingInterrupted, EmbeddingService
from app.services.file_fetch_service import FileFetchService
from app.services.html_parser_service import HtmlParserService, ParsedPage
from app.services.indexing_planner_service import IndexingPlannerService
from app.services.ollama_service import OllamaService
from app.services.pdf_parser_service import PdfParserService
from app.services.qdrant_service import QdrantService
from app.services.text_cleaner_service import TextCleanerService
from app.services.content_category_service import detect_content_category
from app.services.content_signals import normalize_content_hint
from app.services.document_type_service import detect_document_type
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.source_intelligence_service import SourceIntelligenceService
from app.services.settings_flags import setting_bool
from app.utils.hashing import chunk_point_id, content_hash
from app.utils.time_utils import utcnow

logger = get_logger(__name__)


@dataclass
class IndexOutcome:
    status: str  # indexed / skipped / error
    detail: str = ""
    parsed_page: ParsedPage | None = None  # for crawl link discovery


class IndexingService:
    """Indexes one document (page or file) into SQLite + Qdrant."""

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repo = SourceRepository(db)
        self.fetcher = FileFetchService(timeout=settings.request_timeout_seconds)
        self.profile = KnowledgeProfileService.from_settings(settings)
        self.html_parser = HtmlParserService(profile=self.profile)
        self.pdf_parser = PdfParserService()
        self.docx_parser = DocxParserService()
        self.cleaner = TextCleanerService()
        self.chunker = ChunkingService(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            profile=self.profile,
        )
        self.ollama = OllamaService()
        self.embedding_service = EmbeddingService(
            model=settings.embedding_model, ollama=self.ollama
        )
        self.qdrant = QdrantService(collection=settings.qdrant_collection)
        self._planner = IndexingPlannerService(
            page_refresh_hours=settings.indexed_page_refresh_interval_hours,
            file_refresh_hours=settings.indexed_file_refresh_interval_hours,
        )
        self._boilerplate_detector: BoilerplateDetectorService | None = None

    def set_boilerplate_detector(self, detector: BoilerplateDetectorService | None) -> None:
        self._boilerplate_detector = detector

    def index_source(
        self,
        source: Source,
        *,
        force: bool = False,
        on_progress: Callable[[str, str], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> IndexOutcome:
        """Fetch, extract, dedup and (re)embed a single source."""

        def tick(stage: str, message: str) -> None:
            if on_progress:
                on_progress(stage, message)

        def stopped() -> bool:
            return bool(should_stop and should_stop())

        if stopped():
            return IndexOutcome(status="stopped", detail="stop requested")

        if force:
            planner = IndexingPlannerService(
                page_refresh_hours=self.settings.indexed_page_refresh_interval_hours,
                file_refresh_hours=self.settings.indexed_file_refresh_interval_hours,
                force_reindex=True,
            )
        else:
            planner = self._planner

        source.index_attempts = (source.index_attempts or 0) + 1
        now = utcnow()
        source.last_checked_at = now
        tick("fetching_page", f"Fetching: {source.url}")
        try:
            result = self.fetcher.fetch(source.url)
        except Exception as exc:  # noqa: BLE001
            return self._mark_error(source, f"Fetch failed: {exc}")

        if stopped():
            return IndexOutcome(status="stopped", detail="stop requested after fetch")

        parsed_page: ParsedPage | None = None
        tick("extracting_text", f"Extracting text: {source.url}")
        try:
            text, title, parsed_page = self._extract(source, result)
        except Exception as exc:  # noqa: BLE001
            return self._mark_error(source, f"Extraction failed: {exc}")
        # Release fetch buffers early (HTML keeps text only; files keep bytes).
        result.content = b""
        result.text = ""

        text = self.cleaner.clean(text)
        if parsed_page is not None:
            main_text = parsed_page.main_content_text or parsed_page.text or text
            if self._boilerplate_detector:
                main_text = self._boilerplate_detector.strip_boilerplate(main_text)
            text = main_text
            nav_chars = len(parsed_page.navigation_text or "")
            footer_chars = len(parsed_page.footer_text or "")
            header_chars = len(parsed_page.header_text or "")
            main_chars = len(main_text)
            source.extracted_text = parsed_page.text
            source.main_content_text = main_text
            source.navigation_text = parsed_page.navigation_text
            source.footer_text = parsed_page.footer_text
            source.header_text = parsed_page.header_text
            source.boilerplate_text = parsed_page.boilerplate_text
            source.main_content_chars = main_chars
            source.boilerplate_chars = nav_chars + footer_chars + header_chars
            source.boilerplate_ratio = BoilerplateDetectorService.boilerplate_ratio(
                main_chars=main_chars,
                navigation_chars=nav_chars,
                footer_chars=footer_chars,
                header_chars=header_chars,
            )
            source.extraction_version = EXTRACTION_VERSION
            source.chunking_version = CHUNKING_VERSION
            source.classification_version = CLASSIFICATION_VERSION
            source.needs_reprocess = False

        tick("extracting_text", f"Text extracted: {len(text)} chars")
        if not text.strip():
            source.status = "skipped"
            source.error_message = "No extractable text"
            source.title = title or source.title
            self.repo.save(source)
            return IndexOutcome(status="skipped", detail="empty content", parsed_page=parsed_page)

        new_hash = content_hash(text)

        # Dedup: unchanged content -> skip re-embedding.
        if source.content_hash == new_hash and source.status == "indexed" and not force:
            source.next_refresh_at = planner.compute_next_refresh(source, now=now)
            self.repo.save(source)
            return IndexOutcome(status="skipped", detail="unchanged", parsed_page=parsed_page)

        # Do not wipe vectors if the operator already asked to stop.
        if stopped():
            return IndexOutcome(status="stopped", detail="stop requested before embed")

        # Content changed (or new): remove old vectors/chunks then re-embed.
        self._reset_source_vectors(source)

        # Heading-aware chunking for HTML pages; plain chunking otherwise.
        is_homepage = parsed_page.is_homepage if parsed_page is not None else False
        headings_text = " ".join(
            b.heading for b in (parsed_page.blocks if parsed_page else []) if b.heading
        )
        document_type = detect_document_type(
            url=source.url,
            title=title or source.title or "",
            headings=headings_text,
            source_type=source.source_type,
            profile=self.profile,
        )
        source.document_type = document_type
        page_category = detect_content_category(
            url=source.url,
            title=title or source.title or "",
            document_type=document_type,
            is_homepage=is_homepage,
            profile=self.profile,
        )

        if parsed_page is not None and parsed_page.blocks:
            chunks = self.chunker.chunk_blocks(parsed_page.blocks, title)
        else:
            chunks = self.chunker.chunk_plain(text)
        tick("chunking", f"Created {len(chunks)} chunks")
        if not chunks:
            source.status = "skipped"
            source.error_message = "No chunks produced"
            self.repo.save(source)
            return IndexOutcome(status="skipped", detail="no chunks", parsed_page=parsed_page)

        try:
            tick("embedding", f"Creating embeddings for {len(chunks)} chunks")
            vectors = self.embedding_service.embed_texts(
                [c.text for c in chunks],
                should_stop=should_stop,
            )
        except EmbeddingInterrupted:
            # Vectors were already cleared — leave page waiting for a retry.
            source.status = "pending"
            source.error_message = "Interrupted by stop; queued for retry"
            source.next_refresh_at = utcnow()
            self.repo.save(source)
            return IndexOutcome(status="stopped", detail="stop during embedding")
        except Exception as exc:  # noqa: BLE001
            return self._mark_error(source, f"Embedding failed: {exc}")

        vector_size = len(vectors[0]) if vectors else 0
        if vector_size:
            self.qdrant.ensure_collection(vector_size)

        chunk_title = title or source.url
        point_ids: list[str] = []
        payloads: list[dict] = []
        chunk_rows: list[Chunk] = []
        for chunk in chunks:
            pid = chunk_point_id(source.id, chunk.index)
            point_ids.append(pid)
            chunk_category = detect_content_category(
                url=source.url,
                title=chunk_title,
                heading=chunk.heading or "",
                document_type=document_type,
                content_type_hint=chunk.content_type_hint,
                is_homepage=is_homepage,
                profile=self.profile,
            ) or page_category
            payloads.append(
                {
                    "source_id": source.id,
                    "chunk_index": chunk.index,
                    "title": chunk_title,
                    "url": source.url,
                    "source_type": source.source_type,
                    "text": chunk.text,
                    "heading": chunk.heading,
                    "is_homepage": is_homepage,
                    "is_structured_block": chunk.is_structured_block,
                    "content_type_hint": normalize_content_hint(chunk.content_type_hint),
                    "document_type": document_type,
                    "content_category": chunk_category,
                }
            )
            chunk_rows.append(
                Chunk(
                    source_id=source.id,
                    chunk_index=chunk.index,
                    title=chunk_title,
                    url=source.url,
                    text=chunk.text,
                    vector_id=pid,
                    source_type=source.source_type,
                    heading=chunk.heading,
                    is_homepage=is_homepage,
                    is_structured_block=chunk.is_structured_block,
                    content_type_hint=normalize_content_hint(chunk.content_type_hint),
                    document_type=document_type,
                    content_category=chunk_category,
                )
            )

        try:
            tick("saving", f"Saving to knowledge base: {source.url}")
            self.qdrant.upsert_chunks(point_ids, vectors, payloads)
        except Exception as exc:  # noqa: BLE001
            return self._mark_error(source, f"Qdrant upsert failed: {exc}")

        self.repo.add_chunks(chunk_rows)
        self._index_lexical(source, chunk_rows)

        source.title = title or source.title or source.url
        source.content_hash = new_hash
        source.content_length = len(text)
        source.status = "indexed"
        source.error_message = None
        source.indexed_at = now
        source.last_reprocessed_at = now if force else source.last_reprocessed_at
        source.needs_intelligence = True
        inline = setting_bool(
            self.settings, "run_source_intelligence_inline_during_indexing", default=False
        )
        if inline:
            try:
                sp = SourceIntelligenceService.build_profile(
                    source, self.profile, settings=self.settings, db=self.db
                )
                SourceIntelligenceService.apply_to_source(
                    source, sp, settings=self.settings, now=now
                )
                from app.services.epistemic_memory.memory_integration_service import (
                    EpistemicMemoryIntegrationService,
                )

                EpistemicMemoryIntegrationService(
                    self.db, self.settings
                ).shadow_write_after_si(source, sp)
                source.needs_intelligence = False
            except Exception as exc:  # noqa: BLE001
                logger.debug("Source intelligence skipped for %s: %s", source.url, exc)
        source.next_refresh_at = planner.compute_next_refresh(source, now=now)
        self.repo.save(source)

        return IndexOutcome(status="indexed", detail=f"{len(chunks)} chunks", parsed_page=parsed_page)

    def parse_page_only(self, url: str) -> ParsedPage | None:
        """Fetch and parse an HTML page for link/file discovery only.

        Used by files_only mode: the page is crawled to find file links but is
        never stored as a knowledge source.
        """
        try:
            result = self.fetcher.fetch(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Discovery fetch failed for %s: %s", url, exc)
            return None
        try:
            return self.html_parser.parse(result.text, url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Discovery parse failed for %s: %s", url, exc)
            return None

    def _extract(self, source: Source, result) -> tuple[str, str, ParsedPage | None]:
        """Dispatch extraction by source type. Returns (text, title, parsed_page)."""
        stype = source.source_type
        if stype == "pdf":
            return self.pdf_parser.extract(result.content), source.title or source.url, None
        if stype == "docx":
            return self.docx_parser.extract(result.content), source.title or source.url, None
        if stype == "txt":
            text = result.text or result.content.decode("utf-8", errors="ignore")
            return text, source.title or source.url, None
        # page or html file
        parsed = self.html_parser.parse(result.text, source.url)
        return parsed.text, parsed.title, parsed

    def _index_lexical(self, source: Source, chunk_rows: list[Chunk]) -> None:
        """No-op: the lexical index is a PostgreSQL generated ``tsvector`` column
        on ``chunks`` and is maintained automatically when chunk rows change."""
        return None

    def _reset_source_vectors(self, source: Source) -> None:
        try:
            self.qdrant.delete_source_points(source.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed deleting old vectors for source %s: %s", source.id, exc)
        # Deleting chunk rows also removes their generated full-text vectors.
        self.repo.delete_chunks_for_source(source.id)
        self.db.commit()

    def _mark_error(self, source: Source, message: str) -> IndexOutcome:
        logger.warning("Indexing error for %s: %s", source.url, message)
        has_chunks = self.repo.count_chunks_for_source(source.id) > 0
        if has_chunks:
            # Keep prior successful index in the knowledge base; flag for retry.
            source.status = "indexed"
            source.needs_reprocess = True
        else:
            source.status = "error"
        source.error_message = message[:1000]
        source.last_checked_at = utcnow()
        source.next_refresh_at = utcnow()
        self.repo.save(source)
        return IndexOutcome(status="error", detail=message)
