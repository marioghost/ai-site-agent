"""Profile-driven query expansion for hybrid retrieval (semantic, bounded)."""
from __future__ import annotations

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.retrieval_engine.semantic_expansion import SemanticExpansionService
from app.services.retrieval_intent_service import RetrievalIntentResult


class RetrievalExpansionService:
    def __init__(self, profile: KnowledgeProfile | None = None, *, max_expansions: int = 5) -> None:
        self.profile = profile or KnowledgeProfileService.default_profile()
        self._semantic = SemanticExpansionService(self.profile, max_expansions=max_expansions)

    def expand_terms(
        self,
        normalized_query: str,
        *,
        intent_result: RetrievalIntentResult | None = None,
    ) -> list[str]:
        return self._semantic.expand(normalized_query, intent_result=intent_result).terms

    def variants(
        self,
        normalized_query: str,
        *,
        intent_result: RetrievalIntentResult | None = None,
    ) -> list[str]:
        return self._semantic.expand(normalized_query, intent_result=intent_result).variants
