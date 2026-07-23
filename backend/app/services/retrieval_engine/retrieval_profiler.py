"""Retrieval profile resolution."""
from __future__ import annotations

from app.models.settings import Settings
from app.services.retrieval_engine.config import RetrievalProfileConfig, load_retrieval_profile


class RetrievalProfiler:
    """Resolve active retrieval profile from settings."""

    @staticmethod
    def active(settings: Settings) -> RetrievalProfileConfig:
        return load_retrieval_profile(settings)
