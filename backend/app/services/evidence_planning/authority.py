"""Intent-aware authority and fitness evaluation."""
from __future__ import annotations

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.evidence_planning.types import EvidenceCandidate
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.rag_planning.contracts import KnowledgePlan
from app.services.retrieval_engine.focus_compatibility import (
    evaluate_focus_compatibility,
    is_negative_compatibility,
    is_strong_compatibility,
)
from app.services.retrieval_engine.query_understanding import QueryUnderstanding
from app.services.rag_planning.intent_taxonomy import (
    INCIDENTAL_DOCUMENT_TYPES as LOW_OVERVIEW_DOCUMENT_TYPES,
    INCIDENTAL_PAGE_ROLES as LOW_OVERVIEW_PAGE_ROLES,
    OVERVIEW_INTENTS,
)

_ROLE_INTENT_FIT: dict[str, dict[str, float]] = {
    "entity_overview": {
        "organization_overview": 0.95,
        "service_overview": 0.75,
        "documentation": 0.55,
        "news": 0.15,
        "campaign": 0.10,
        "hr": 0.08,
        "recruitment": 0.08,
        "generic": 0.45,
    },
    "topic_overview": {
        "documentation": 0.90,
        "service_overview": 0.80,
        "organization_overview": 0.50,
        "news": 0.35,
        "generic": 0.55,
    },
    "news_query": {
        "news": 0.95,
        "campaign": 0.70,
        "organization_overview": 0.20,
    },
    "contacts_query": {
        "contact": 0.95,
        "organization_overview": 0.35,
    },
}


def evaluate_authority_fitness(
    candidate: EvidenceCandidate,
    *,
    intent: str,
    knowledge_plan: KnowledgePlan,
    understanding: QueryUnderstanding | None,
    profile: KnowledgeProfile | None = None,
) -> EvidenceCandidate:
    factors: dict[str, float] = {}
    score = 0.0

    rel = min(1.0, max(0.0, candidate.rerank_score))
    factors["retrieval_relevance"] = round(rel, 4)
    score += 0.22 * rel

    role_fit = _role_intent_fit(candidate.page_role, intent)
    factors["role_intent_fit"] = round(role_fit, 4)
    score += 0.22 * role_fit

    purpose_fit = _purpose_fit(candidate.source_purpose, understanding, intent)
    factors["purpose_fit"] = round(purpose_fit, 4)
    score += 0.18 * purpose_fit

    focus_fit, compatibility_label = _focus_consistency(candidate, understanding)
    candidate.focus_match_score = focus_fit
    candidate.compatibility_label = compatibility_label
    factors["focus_consistency"] = round(focus_fit, 4)
    score += 0.18 * focus_fit
    if is_negative_compatibility(compatibility_label):
        score -= 0.18
        factors["negative_compatibility"] = -0.18
    elif is_strong_compatibility(compatibility_label):
        score += 0.06
        factors["compatibility_bonus"] = 0.06
    elif compatibility_label in {"same_category", "category_support", "supporting_evidence"}:
        score += 0.02
        factors["category_bonus"] = 0.02

    # Prefer expected evidence type alignment from knowledge plan.
    expected = getattr(knowledge_plan, "expected_evidence_type", "") or ""
    semantic_focus = getattr(knowledge_plan, "semantic_focus", "") or ""
    if expected and is_strong_compatibility(compatibility_label):
        score += 0.04
        factors["expected_evidence_match"] = 0.04
    if semantic_focus == "organization_profile" and candidate.page_role in {
        "product_details",
        "pricing",
        "campaign",
    }:
        score -= 0.10
        factors["org_vs_product_penalty"] = -0.10

    if candidate.canonical:
        score += 0.08
        factors["canonical"] = 0.08
    if candidate.kp_preferred:
        score += 0.12
        factors["kp_preferred"] = 0.12
        if profile is not None:
            rule = KnowledgeProfileService.priority_rule_for_intent(profile, intent)
            if rule:
                try:
                    rank = list(rule.boost_document_types).index(candidate.document_type)
                    rank_boost = 0.10 * (1.0 - rank / max(len(rule.boost_document_types), 1))
                    score += rank_boost
                    factors["kp_preferred_rank"] = round(rank_boost, 4)
                except ValueError:
                    pass
    if candidate.kp_deprioritized:
        score -= 0.22
        factors["kp_deprioritized"] = -0.22

    if candidate.broad_injected:
        inject_penalty = -0.18
        if role_fit >= 0.7 and candidate.kp_preferred:
            inject_penalty = -0.06
        score += inject_penalty
        factors["broad_inject"] = inject_penalty

    if understanding and understanding.language not in {"unknown", ""}:
        if candidate.language == understanding.language:
            score += 0.05
            factors["language_match"] = 0.05
        elif candidate.language not in {understanding.language, "mixed", "unknown"}:
            score -= 0.06
            factors["language_fallback"] = -0.06

    aspect_overlap = len(candidate.available_aspects & set(knowledge_plan.required_slots))
    if knowledge_plan.required_slots:
        aspect_score = aspect_overlap / len(knowledge_plan.required_slots)
        score += 0.15 * aspect_score
        factors["required_aspect_overlap"] = round(aspect_score, 4)

    forbidden_overlap = len(candidate.available_aspects & set(knowledge_plan.forbidden_slots))
    if forbidden_overlap:
        penalty = min(0.35, 0.12 * forbidden_overlap)
        score -= penalty
        factors["forbidden_aspect_overlap"] = -round(penalty, 4)

    if intent in OVERVIEW_INTENTS:
        if candidate.page_role in LOW_OVERVIEW_PAGE_ROLES:
            score -= 0.25
            factors["incidental_role"] = -0.25
        if candidate.document_type in LOW_OVERVIEW_DOCUMENT_TYPES:
            score -= 0.20
            factors["incidental_doc_type"] = -0.20

    score += 0.10 * candidate.quality_score
    factors["quality"] = round(0.10 * candidate.quality_score, 4)

    fitness = max(0.0, min(1.0, score))
    candidate.authority_fitness = fitness
    candidate.fitness_factors = factors
    candidate.fitness_band = _fitness_band(fitness)
    candidate.forbidden_for_query = forbidden_overlap > 0 and fitness < 0.35
    candidate.intent_compatibility = max(purpose_fit, focus_fit)
    return candidate


def _role_intent_fit(page_role: str, intent: str) -> float:
    intent_map = _ROLE_INTENT_FIT.get(intent, {})
    if page_role in intent_map:
        return intent_map[page_role]
    if intent in OVERVIEW_INTENTS:
        return intent_map.get(page_role, _ROLE_INTENT_FIT["entity_overview"].get(page_role, 0.45))
    return intent_map.get(page_role, 0.45)


def _purpose_fit(
    purpose: str,
    understanding: QueryUnderstanding | None,
    intent: str,
) -> float:
    p = (purpose or "").lower().strip()
    if not p:
        return 0.45
    if understanding:
        if p in understanding.preferred_purposes:
            return 0.9
        if p in understanding.unsuitable_purposes:
            return 0.15
    if intent == "news_query" and p == "news":
        return 0.95
    if intent in OVERVIEW_INTENTS and p in {"about company", "landing page", "service description"}:
        return 0.85
    if p == "general information":
        return 0.40
    return 0.50


def _focus_consistency(
    candidate: EvidenceCandidate,
    understanding: QueryUnderstanding | None,
) -> tuple[float, str]:
    # Prefer DFP-seeded label when already computed on the candidate.
    seeded = (candidate.compatibility_label or "").strip()
    seeded_score = float(candidate.focus_match_score or 0.0)
    if seeded and seeded != "ambiguous" and seeded_score > 0:
        return seeded_score, seeded

    result = evaluate_focus_compatibility(
        understanding,
        title=candidate.title,
        purpose=candidate.source_purpose,
        page_role=candidate.page_role,
        document_type=candidate.document_type,
        text=candidate.text,
        url=candidate.url or "",
        semantic_phrases=[
            candidate.heading,
            candidate.section_heading,
            candidate.source_purpose,
        ],
    )
    return result.score, result.label


def _fitness_band(fitness: float) -> str:
    if fitness >= 0.72:
        return "high"
    if fitness >= 0.48:
        return "moderate"
    if fitness >= 0.28:
        return "low"
    return "poor"
