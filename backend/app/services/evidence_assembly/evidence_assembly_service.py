"""EvidenceAssemblyService — thin DFP facade (RFC-100 Step 040).

Stateless seam over DocumentFirstRetrievalPipeline. Establishes ownership of
evidence assembly without changing retrieval, ranking, context, or language.

Does not store knowledge, mutate Epistemic Memory, decide sufficiency, or
render prompts / answers.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.services.embedding_service import EmbeddingService
from app.services.evidence_assembly.types import (
    EVIDENCE_ASSEMBLY_PATH_SERVICE,
    EvidenceAssemblyRequest,
)
from app.services.qdrant_service import QdrantService
from app.services.retrieval_engine.pipeline import (
    DocumentFirstRetrievalPipeline,
    DocumentRetrievalResult,
)


class EvidenceAssemblyService:
    """Assemble observation evidence via legacy DFP — exactly once per call.

    Stateless: no caches of hits, documents, or answers across invocations.
    Ranking inside DFP remains operational legacy, not EA's cognitive mission.
    """

    def __init__(
        self,
        db: Session,
        settings: Settings,
        embedding: EmbeddingService,
        qdrant: QdrantService,
    ) -> None:
        self._db = db
        self._settings = settings
        self._pipeline = DocumentFirstRetrievalPipeline(db, settings, embedding, qdrant)

    def assemble(self, request: EvidenceAssemblyRequest) -> DocumentRetrievalResult:
        """Invoke DFP exactly once; return the same retrieval artifacts."""
        result = self._pipeline.run(
            query=request.query,
            normalized=request.normalized,
            intent_result=request.intent_result,
            profile=request.profile,
            query_vector=request.query_vector,
            expansion_terms=request.expansion_terms,
            query_language=request.query_language,
        )
        result.evidence_assembly_path = EVIDENCE_ASSEMBLY_PATH_SERVICE
        return result
