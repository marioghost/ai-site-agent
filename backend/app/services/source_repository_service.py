"""High-level source operations combining SQLite metadata and Qdrant vectors."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.settings import Settings
from app.models.source import Source
from app.repositories.source_repository import SourceRepository
from app.services.indexing_service import IndexOutcome, IndexingService
from app.services.lexical_index_service import LexicalIndexService
from app.services.qdrant_service import QdrantService

logger = get_logger(__name__)


class SourceRepositoryService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repo = SourceRepository(db)

    def delete_source(self, source: Source) -> None:
        """Delete a source from SQLite (chunks cascade) and Qdrant."""
        try:
            qdrant = QdrantService(collection=self.settings.qdrant_collection)
            qdrant.delete_source_points(source.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to delete Qdrant points for %s: %s", source.id, exc)
        try:
            lex = LexicalIndexService(self.db)
            lex.delete_for_source(source.id)
            self.db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to delete lexical index for %s: %s", source.id, exc)
        # Chunk rows cascade-delete via the relationship.
        self.repo.delete(source)

    def reindex_source(self, source: Source) -> IndexOutcome:
        """Refetch and reindex a single source document."""
        indexer = IndexingService(self.db, self.settings)
        return indexer.index_source(source)
