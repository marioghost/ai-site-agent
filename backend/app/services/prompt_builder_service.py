"""Compact prompt builder — delegates to retrieval_engine implementation."""
from __future__ import annotations

from app.services.context_builder_service import BuiltContext
from app.services.qdrant_service import SearchHit
from app.services.retrieval_engine.prompt_builder import OVERVIEW_INTENTS, CompactPromptBuilder
from app.services.source_intelligence_constants import PROMPT_TEMPLATE_VERSION

OVERVIEW_INTENTS = OVERVIEW_INTENTS  # re-export from retrieval_engine


class PromptBuilderService:
    VERSION = PROMPT_TEMPLATE_VERSION

    @classmethod
    def build(
        cls,
        *,
        message: str,
        hits: list[SearchHit],
        built_context: BuiltContext | None,
        intent: str,
        settings,
        org_name: str = "the organization",
    ) -> tuple[str, str]:
        return CompactPromptBuilder.build(
            message=message,
            hits=hits,
            built_context=built_context,
            intent=intent,
            settings=settings,
            org_name=org_name,
        )

    @staticmethod
    def contains_debug_trace(text: str) -> bool:
        return CompactPromptBuilder.contains_debug_trace(text)
