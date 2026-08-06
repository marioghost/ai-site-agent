"""Repository for the single-row Settings table."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_config
from app.models.settings import Settings
from app.services.system_prompt_defaults import DEFAULT_SYSTEM_PROMPT

DEFAULT_FALLBACK = "Я не знайшов цієї інформації на сайті."


class SettingsRepository:
    """CRUD-ish access for the singleton settings row."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> Settings | None:
        return self.db.execute(
            select(Settings).order_by(Settings.id).limit(1)
        ).scalar_one_or_none()

    def get_or_create(self) -> Settings:
        settings = self.get()
        if settings is not None:
            return settings
        config = get_config()
        settings = Settings(
            llm_model=config.default_llm_model,
            embedding_model=config.default_embedding_model,
            qdrant_collection=config.default_qdrant_collection,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            fallback_answer=DEFAULT_FALLBACK,
        )
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def save(self, settings: Settings) -> Settings:
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings
