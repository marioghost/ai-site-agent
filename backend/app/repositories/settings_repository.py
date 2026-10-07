"""Repository for the single-row Settings table."""
from __future__ import annotations

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import get_config
from app.core.logging import get_logger
from app.models.settings import Settings
from app.services.system_prompt_defaults import DEFAULT_SYSTEM_PROMPT

DEFAULT_FALLBACK = "Вибачте, у мене немає такої інформації."
logger = get_logger(__name__)


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
            self._prune_extra_rows(keep_id=int(settings.id))
            return self.ensure_site_url(settings)
        # Serialize create against concurrent workers (Postgres advisory lock).
        try:
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:k)"), {"k": 0x53455431}
            )
        except Exception:  # noqa: BLE001
            logger.debug("settings create advisory lock unavailable", exc_info=True)
        settings = self.get()
        if settings is not None:
            return self.ensure_site_url(settings)
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
        return self.ensure_site_url(settings)

    def ensure_site_url(self, settings: Settings) -> Settings:
        """Persist dominant indexed origin when operator site_url is empty."""
        if (settings.site_url or "").strip():
            return settings
        from app.services.site_origin_service import SiteOriginService

        origin = SiteOriginService(self.db).dominant_origin()
        if not origin:
            return settings
        settings.site_url = origin
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        logger.info("settings_site_url_backfilled origin=%s settings_id=%s", origin, settings.id)
        return settings

    def _prune_extra_rows(self, *, keep_id: int) -> None:
        """Remove accidental extra Settings rows (singleton invariant)."""
        result = self.db.execute(
            delete(Settings).where(Settings.id != keep_id)
        )
        if result.rowcount:
            self.db.commit()
            logger.warning(
                "settings_singleton_pruned removed=%s keep_id=%s",
                result.rowcount,
                keep_id,
            )

    def save(self, settings: Settings) -> Settings:
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings
