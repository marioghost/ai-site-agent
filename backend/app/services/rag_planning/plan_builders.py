"""Build KnowledgePlan and AnswerPlan from existing understanding signals."""
from __future__ import annotations

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.rag_planning.contracts import AnswerPlan, KnowledgePlan
from app.services.rag_planning.intent_taxonomy import (
    CONTACT_INTENTS,
    FAQ_INTENTS,
    INCIDENTAL_DOCUMENT_TYPES,
    NEWS_INTENTS,
    OVERVIEW_DOCUMENT_TYPES,
    POLICY_INTENTS,
    is_overview_intent,
)
from app.services.rag_planning.purpose_catalog import (
    filter_valid_purposes,
    purposes_to_forbidden_slots,
)
from app.services.retrieval_engine.query_understanding import QueryUnderstanding

_OVERVIEW_REQUIRED = ("identity", "activity")
_OVERVIEW_OPTIONAL = ("audience", "capabilities", "distinguisher")
_LISTING_REQUIRED = ("options",)
_LISTING_OPTIONAL = ("categories",)
_CONTACT_REQUIRED = ("contact_info",)
_COMPARISON_REQUIRED = ("attributes",)
_COMPARISON_OPTIONAL = ("alternatives",)
_NEWS_REQUIRED = ("current_item",)
_PROMOTION_REQUIRED = ("offer",)
_FACT_REQUIRED = ("fact",)
_DOC_REQUIRED = ("documentation",)
_FAQ_REQUIRED = ("answer",)
_GENERAL_REQUIRED = ("general",)

_FORBIDDEN_OVERVIEW = frozenset({"offer", "vacancy", "news_item", "campaign"})

OVERVIEW_SCOPE_INSTRUCTION = (
    "Answer the overview or identity question first; include only the most "
    "relevant dimensions; omit unrelated topics; stop once the question is answered."
)


def build_knowledge_plan(
    *,
    information_need: str,
    understanding: QueryUnderstanding | None,
    profile: KnowledgeProfile | None,
) -> KnowledgePlan:
    answer_type = understanding.expected_answer_type if understanding else "general"
    intent_l = (information_need or "").lower()
    reasons: list[str] = [f"answer_type={answer_type}"]

    if is_overview_intent(intent_l) or answer_type == "overview":
        required, optional = _OVERVIEW_REQUIRED, _OVERVIEW_OPTIONAL
        forbidden = tuple(_FORBIDDEN_OVERVIEW)
        reasons.append("overview_knowledge_slots")
    elif answer_type == "listing" or "list" in intent_l:
        required, optional = _LISTING_REQUIRED, _LISTING_OPTIONAL
        forbidden = ("news_item", "vacancy")
    elif answer_type == "contact" or intent_l in CONTACT_INTENTS:
        required, optional = _CONTACT_REQUIRED, ()
        forbidden = ("offer", "news_item", "product_listing")
    elif answer_type == "documentation" or intent_l in POLICY_INTENTS:
        required, optional = _DOC_REQUIRED, ("conditions", "exceptions")
        forbidden = ("offer", "news_item")
    elif answer_type == "comparison":
        required, optional = _COMPARISON_REQUIRED, _COMPARISON_OPTIONAL
        forbidden = ("news_item",)
    elif answer_type == "fact" or intent_l == "specific_fact":
        required, optional = _FACT_REQUIRED, ()
        forbidden = tuple(_FORBIDDEN_OVERVIEW)
    elif intent_l in NEWS_INTENTS:
        required, optional = _NEWS_REQUIRED, ("context",)
        forbidden = ("identity", "offer")
    elif "promotion" in intent_l or "offer" in intent_l or "campaign" in intent_l:
        required, optional = _PROMOTION_REQUIRED, ("terms", "validity")
        forbidden = ("identity", "history")
    elif answer_type == "faq" or intent_l in FAQ_INTENTS:
        required, optional = _FAQ_REQUIRED, ("related_topics",)
        forbidden = ("offer", "news_item")
    else:
        required, optional = _GENERAL_REQUIRED, ("supporting_detail",)
        forbidden = ()

    preferred_purposes: tuple[str, ...] = ()
    unsuitable_purposes: tuple[str, ...] = ()
    preferred_doc_types: frozenset[str] = frozenset()
    deprioritized_doc_types: frozenset[str] = frozenset()

    if understanding:
        preferred_purposes = filter_valid_purposes(list(understanding.preferred_purposes))
        unsuitable_purposes = filter_valid_purposes(list(understanding.unsuitable_purposes))
        extra_forbidden = purposes_to_forbidden_slots(list(unsuitable_purposes))
        forbidden = tuple(dict.fromkeys((*forbidden, *extra_forbidden)))

    if profile is not None:
        rule = KnowledgeProfileService.priority_rule_for_intent(profile, information_need)
        if rule:
            preferred_doc_types = frozenset(rule.boost_document_types)
            deprioritized_doc_types = frozenset(rule.deprioritize_document_types)
            reasons.append("knowledge_profile_priority_rule")
        elif is_overview_intent(intent_l):
            preferred_doc_types = OVERVIEW_DOCUMENT_TYPES
            deprioritized_doc_types = INCIDENTAL_DOCUMENT_TYPES

    return KnowledgePlan(
        information_need=information_need,
        answer_type=answer_type,
        required_slots=required,
        optional_slots=optional,
        forbidden_slots=forbidden,
        preferred_purposes=preferred_purposes,
        unsuitable_purposes=unsuitable_purposes,
        preferred_document_types=preferred_doc_types,
        deprioritized_document_types=deprioritized_doc_types,
        plan_reasons=tuple(reasons),
    )


def build_answer_plan(*, knowledge_plan: KnowledgePlan) -> AnswerPlan:
    scope = ""
    reasons: list[str] = ["derived_from_knowledge_plan"]

    if is_overview_intent(knowledge_plan.information_need) or knowledge_plan.answer_type == "overview":
        scope = OVERVIEW_SCOPE_INSTRUCTION
        reasons.append("overview_scope")
    elif knowledge_plan.answer_type == "contact":
        scope = "Provide contact information clearly and concisely."
    elif knowledge_plan.answer_type == "faq":
        scope = "Answer the specific question directly using the evidence."
    elif knowledge_plan.answer_type == "listing":
        scope = "List the relevant options found in the evidence; do not claim completeness unless stated."
    elif knowledge_plan.answer_type == "comparison":
        scope = "Compare the relevant alternatives using aligned attributes from the evidence."

    return AnswerPlan(
        answer_type=knowledge_plan.answer_type,
        scope_instruction=scope,
        plan_reasons=tuple(reasons),
    )
