"""Evidence Assembly path markers (RFC-100 Step 040).

Result artifacts reuse ``DocumentRetrievalResult`` from DFP — no duplicate
result DTO. Request packing is the thin typed boundary for the assemble call.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.retrieval_intent_service import RetrievalIntentResult

EVIDENCE_ASSEMBLY_PATH_LEGACY = "legacy"
EVIDENCE_ASSEMBLY_PATH_SERVICE = "evidence_assembly"


@dataclass(frozen=True)
class EvidenceAssemblyRequest:
    """Inputs for one evidence-assembly invocation (stateless).

    Mirrors ``DocumentFirstRetrievalPipeline.run`` kwargs so callers do not
    invent a second parallel contract. Does not include HTTP/ORM objects.
    """

    query: str
    normalized: str
    intent_result: RetrievalIntentResult
    profile: KnowledgeProfile
    query_vector: list[float] | None = None
    expansion_terms: list[str] | None = None
    query_language: str = "unknown"
