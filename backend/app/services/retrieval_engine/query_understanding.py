"""Dynamic query understanding — domain-agnostic, no hardcoded business rules."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.rag_planning.purpose_catalog import purpose_expectations_for_answer_type
from app.services.rag_planning.intent_taxonomy import (
    CONTACT_INTENTS,
    FAQ_INTENTS,
    LISTING_INTENTS,
    OVERVIEW_INTENTS,
)
from app.services.retrieval_intent_service import RetrievalIntentResult

_LISTING_MARKERS = re.compile(
    r"\b(які|which|what|list|available|перелік|види|типи|опції|options|"
    r"assortment|catalog|catalogue|offerings|products|services|"
    r"є\s*\?|are there|do you have)\b",
    re.I,
)
_COMPARISON_MARKERS = re.compile(r"\b(vs|versus|compare|порівня|difference|краще|better)\b", re.I)
_DEFINITION_MARKERS = re.compile(r"\b(what is|what are|що таке|що це|define|визнач)\b", re.I)


@dataclass
class QueryUnderstanding:
    query: str
    intent: str
    legacy_intent: str
    topic: str | None = None
    expected_answer_type: str = "general"
    scope_type: str = "general"
    preferred_purposes: list[str] = field(default_factory=list)
    unsuitable_purposes: list[str] = field(default_factory=list)
    preferred_evidence: list[str] = field(default_factory=list)
    unsuitable_evidence: list[str] = field(default_factory=list)
    focus_terms: list[str] = field(default_factory=list)
    language: str = "unknown"
    specificity: float = 0.5
    ambiguity: float = 0.5
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "legacy_intent": self.legacy_intent,
            "topic": self.topic,
            "expected_answer_type": self.expected_answer_type,
            "scope_type": self.scope_type,
            "preferred_purposes": self.preferred_purposes,
            "unsuitable_purposes": self.unsuitable_purposes,
            "preferred_evidence": self.preferred_evidence,
            "unsuitable_evidence": self.unsuitable_evidence,
            "focus_terms": self.focus_terms,
            "specificity": round(self.specificity, 3),
            "ambiguity": round(self.ambiguity, 3),
            "confidence": round(self.confidence, 3),
        }


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[\w\u0400-\u04FF]{3,}", (text or "").lower())}


class QueryUnderstandingService:
    """Infer what kind of evidence the query needs — without domain-specific rules."""

    @classmethod
    def analyze(
        cls,
        query: str,
        *,
        intent_result: RetrievalIntentResult,
        query_language: str = "unknown",
    ) -> QueryUnderstanding:
        q = (query or "").strip()
        legacy = intent_result.legacy_intent or "unknown"
        topic = intent_result.matched_topic.label if intent_result.matched_topic else None
        topic_key = intent_result.matched_topic.key if intent_result.matched_topic else None

        answer_type = cls._infer_answer_type(q, legacy, intent_result)
        scope_type = cls._scope_type(answer_type, intent_result)
        preferred_purposes, unsuitable_purposes = purpose_expectations_for_answer_type(answer_type)
        preferred_evidence, unsuitable_evidence = cls._evidence_expectations(
            q, answer_type, topic, topic_key, intent_result
        )
        focus_terms = cls._focus_terms(q, topic, topic_key, intent_result)

        tokens = _tokens(q)
        specificity = min(1.0, len(tokens) / 8.0) if tokens else 0.3
        if topic:
            specificity = min(1.0, specificity + 0.15)
        ambiguity = 1.0 - specificity if intent_result.is_broad else max(0.0, 0.5 - specificity * 0.3)

        return QueryUnderstanding(
            query=q,
            intent=intent_result.intent,
            legacy_intent=legacy,
            topic=topic or topic_key,
            expected_answer_type=answer_type,
            scope_type=scope_type,
            preferred_purposes=preferred_purposes,
            unsuitable_purposes=unsuitable_purposes,
            preferred_evidence=preferred_evidence,
            unsuitable_evidence=unsuitable_evidence,
            focus_terms=focus_terms,
            language=query_language,
            specificity=specificity,
            ambiguity=ambiguity,
            confidence=intent_result.confidence,
        )

    @staticmethod
    def _infer_answer_type(
        query: str, legacy_intent: str, intent_result: RetrievalIntentResult
    ) -> str:
        if legacy_intent in CONTACT_INTENTS or intent_result.answer_strategy == "contacts":
            return "contact"
        if _DEFINITION_MARKERS.search(query):
            return "definition"
        if _COMPARISON_MARKERS.search(query):
            return "comparison"
        if _LISTING_MARKERS.search(query) or legacy_intent in LISTING_INTENTS:
            return "listing"
        if intent_result.is_broad or legacy_intent in OVERVIEW_INTENTS:
            return "overview"
        if legacy_intent in FAQ_INTENTS:
            return "faq"
        if legacy_intent in {"legal", "documentation"}:
            return "documentation"
        if intent_result.answer_strategy in {"specific_fact", "fact"}:
            return "fact"
        return "general"

    @staticmethod
    def _scope_type(answer_type: str, intent_result: RetrievalIntentResult) -> str:
        if answer_type == "overview":
            return "organization_overview" if intent_result.is_broad else "topic_overview"
        if answer_type in {"listing", "comparison"} or intent_result.legacy_intent == "product_query":
            return "product_family"
        if answer_type in {"definition", "fact"}:
            return "exact_subject"
        if answer_type == "contact":
            return "navigation"
        if answer_type == "faq":
            return "procedure"
        return "general"

    @staticmethod
    def _evidence_expectations(
        query: str,
        answer_type: str,
        topic: str | None,
        topic_key: str | None,
        intent_result: RetrievalIntentResult,
    ) -> tuple[list[str], list[str]]:
        preferred: list[str] = []
        unsuitable: list[str] = []

        if topic:
            preferred.append(topic.lower())
        if topic_key:
            preferred.append(topic_key.replace("_", " "))
        for alias in intent_result.matched_aliases or []:
            preferred.append(alias.lower())

        if answer_type == "listing":
            preferred.extend(
                [
                    "available options",
                    "product list",
                    "service list",
                    "catalog",
                    "offers",
                ]
            )
            unsuitable.extend(
                [
                    "conceptual explanation",
                    "blog article",
                    "news story",
                    "career page",
                    "generic commentary",
                ]
            )
        elif answer_type == "overview":
            unsuitable.extend(["product listing only", "news archive", "job openings"])

        # Add query noun tokens as topic hints
        stop = {"які", "what", "which", "how", "the", "and", "for", "про", "що", "як"}
        for tok in _tokens(query):
            if tok not in stop and len(tok) >= 4:
                preferred.append(tok)

        return list(dict.fromkeys(preferred))[:16], list(dict.fromkeys(unsuitable))[:12]

    @staticmethod
    def _focus_terms(
        query: str,
        topic: str | None,
        topic_key: str | None,
        intent_result: RetrievalIntentResult,
    ) -> list[str]:
        stop = {"які", "what", "which", "how", "the", "and", "for", "про", "що", "як", "де", "does"}
        focus: list[str] = []
        for blob in [topic or "", (topic_key or "").replace("_", " "), *(intent_result.matched_aliases or [])]:
            for tok in _tokens(blob):
                if tok not in stop and len(tok) >= 3:
                    focus.append(tok)
        for tok in _tokens(query):
            if tok not in stop and len(tok) >= 3:
                focus.append(tok)
        return list(dict.fromkeys(focus))[:12]
