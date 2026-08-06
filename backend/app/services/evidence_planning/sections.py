"""Section-level relevance selection."""
from __future__ import annotations

from app.services.evidence_planning.types import EvidenceCandidate
from app.services.rag_planning.contracts import KnowledgePlan
from app.services.rag_planning.intent_taxonomy import OVERVIEW_INTENTS, is_overview_intent
from app.services.retrieval_engine.content_sanitizer import extract_overview_excerpt


def apply_section_selection(
    candidate: EvidenceCandidate,
    *,
    intent: str,
    knowledge_plan: KnowledgePlan,
    main_content: str = "",
    max_chars: int = 1200,
) -> EvidenceCandidate:
    chunk_hint = candidate.text
    prefer_identity = is_overview_intent(intent) and "identity" in knowledge_plan.required_slots

    if main_content.strip():
        excerpt = extract_overview_excerpt(
            main_content,
            max_chars=max_chars,
            chunk_hint=chunk_hint,
            prefer_identity=prefer_identity,
        )
        if excerpt.strip():
            candidate.section_text = excerpt
            candidate.section_heading = candidate.heading or candidate.title
            candidate.section_relevance = _section_relevance(excerpt, knowledge_plan, chunk_hint)
            candidate.token_estimate = max(1, len(excerpt) // 4)
            return candidate

    text = candidate.text.strip()
    heading = candidate.heading.strip()
    candidate.section_text = text
    candidate.section_heading = heading or candidate.title
    candidate.section_relevance = _section_relevance(text, knowledge_plan, chunk_hint)
    return candidate


def _section_relevance(text: str, knowledge_plan: KnowledgePlan, hint: str) -> float:
    lower = text.lower()
    score = 0.35
    for aspect in knowledge_plan.required_slots:
        if aspect.replace("_", " ") in lower or aspect in lower:
            score += 0.12
    for aspect in knowledge_plan.forbidden_slots:
        if aspect.replace("_", " ") in lower:
            score -= 0.15
    hint_words = {w.lower() for w in hint.split() if len(w) > 3}
    if hint_words:
        score += min(0.25, sum(0.04 for w in hint_words if w in lower))
    return max(0.0, min(1.0, score))
