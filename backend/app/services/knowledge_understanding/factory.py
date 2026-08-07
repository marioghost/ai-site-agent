"""Factory for Knowledge Understanding Layer (concept-index MVP)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.services.feature_flags import knowledge_understanding_enabled
from app.services.knowledge_understanding.adapters.concept_index import (
    ConceptIndexUnderstandingLayer,
)
from app.services.knowledge_understanding.interface import KnowledgeUnderstandingLayer


def get_understanding_layer(
    db: Session,
    settings: Settings,
) -> KnowledgeUnderstandingLayer:
    """Return the active Understanding Layer implementation."""
    return ConceptIndexUnderstandingLayer(
        db,
        enabled=knowledge_understanding_enabled(settings),
    )
