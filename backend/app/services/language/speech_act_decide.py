"""Post-retrieval speech-act decision helper (RFC-100 Step 045).

Used by Language activation after retrieval and before LLM.
Decision logic stays in Reasoning; this only packages retrieval into DTOs.
"""
from __future__ import annotations

from app.services.qdrant_service import SearchHit
from app.services.rag_service import RagResult, RagSource
from app.services.reasoning.evidence_sufficiency import (
    EvidenceSufficiencyAssessment,
    assess_evidence_sufficiency,
)
from app.services.reasoning.speech_act import SpeechActDecision, select_speech_act


def decision_from_retrieval(
    *,
    hits: list[SearchHit],
    query_intent: str,
    applied_knowledge_config: dict | None,
    used_context: bool,
) -> tuple[EvidenceSufficiencyAssessment, SpeechActDecision]:
    """Select speech act from retrieval outputs only (no answer text / no LLM)."""
    sources = [
        RagSource(
            title=h.title or "",
            url=h.url or "",
            source_type=h.source_type or "page",
            score=float(h.score or 0.0),
        )
        for h in (hits or [])
    ]
    stub = RagResult(
        answer="",
        sources=sources,
        used_context=bool(used_context and sources),
        request_id="",
        query_intent=query_intent or "unknown",
        applied_knowledge_config=applied_knowledge_config,
    )
    assessment = assess_evidence_sufficiency(stub)
    strategy = ""
    if isinstance(applied_knowledge_config, dict):
        strategy = str(applied_knowledge_config.get("answer_strategy") or "")
    need = query_intent or strategy or None
    return assessment, select_speech_act(assessment, information_need=need)
