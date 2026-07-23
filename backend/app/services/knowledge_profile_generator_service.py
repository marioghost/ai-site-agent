"""Knowledge Profile generator — delegates to deterministic multi-stage pipeline."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.settings_repository import SettingsRepository
from app.schemas.knowledge_profile_generation import GenerationPreview
from app.services.knowledge_profile_generation.pipeline import KnowledgeProfilePipeline


class KnowledgeProfileGeneratorService:
    """Thin wrapper around KnowledgeProfilePipeline for backward compatibility."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = SettingsRepository(db).get_or_create()

    def generate(
        self,
        *,
        use_llm: bool = True,
        merge_identity: bool = False,
        on_stage=None,
    ) -> tuple[GenerationPreview, dict]:
        pipeline = KnowledgeProfilePipeline(self.db)
        return pipeline.run(
            use_llm=use_llm,
            merge_identity=merge_identity,
            on_stage=on_stage,
        )
