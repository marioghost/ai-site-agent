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
_OVERVIEW_DEFINITION_EXCEPTIONS = re.compile(
    r"\b(what is|what are)\s+(this|the)\s+(site|organization|organisation|company|org|portal|bank|university|clinic)\b",
    re.I,
)
_BENEFITS_MARKERS = re.compile(
    r"\b(benefit|benefits|advantage|advantages|переваг\w*|переваги|why choose|"
    r"чому обрат\w*|strengths|value proposition)\b",
    re.I,
)
_PROCEDURE_MARKERS = re.compile(
    r"\b(how to|how do|how can|як\s+(відкрит|оформ|отримат|зроб|стати)|"
    r"steps?|procedure|інструкц\w*|покроков\w*)\b",
    re.I,
)
_LOCATOR_MARKERS = re.compile(
    r"\b(where|де\s+(знайт|є|розташ)|branch|branches|відділен\w*|atm|atms|"
    r"банкомат\w*|locator|map|nearest|office|offices|офіс\w*|"
    r"find.*(office|store|clinic|campus|branch|atm)|"
    r"знайти.*(відділен|офіс|магазин|клінік|кампус|банкомат)|"
    r"(відділен\w*|банкомат\w*|офіс\w*)\b)",
    re.I,
)
_CONTACT_MARKERS = re.compile(
    r"\b(contact|contacts|phone|email|support|зв.?язат|контакт\w*|телефон|"
    r"hotline|call us|working hours|графік\s*робот)\b",
    re.I,
)
_POLICY_MARKERS = re.compile(
    r"\b(privacy|конфіденц\w*|персональн\w*\s*даних|personal data|"
    r"terms of (use|service)|умови використання|cookie policy|"
    r"information security|інформаційн\w*\s*безпек)\b",
    re.I,
)
_NON_DEFINITION_SINGLES = frozenset(
    {
        "overview",
        "about",
        "company",
        "organization",
        "organisation",
        "services",
        "service",
        "help",
        "info",
        "information",
        "home",
        "contact",
        "contacts",
        "news",
        "bank",
        "site",
        "portal",
    }
)
_RATES_MARKERS = re.compile(
    r"\b(rate|rates|interest|price|pricing|fee|fees|тариф\w*|ставк\w*|"
    r"процентн\w*|вартість|ціна)\b",
    re.I,
)
_CONDITIONS_MARKERS = re.compile(
    r"\b(condition|conditions|terms|вимог\w*|умов\w*|eligibility|"
    r"requirements?|criteria)\b",
    re.I,
)
_ELIGIBILITY_MARKERS = re.compile(
    r"\b(eligible|eligibility|who can|requirements?|criteria|"
    r"хто може|вимог\w*)\b",
    re.I,
)


@dataclass
class QueryUnderstanding:
    query: str
    intent: str
    legacy_intent: str
    topic: str | None = None
    expected_answer_type: str = "general"
    scope_type: str = "general"
    semantic_focus: str = "general"
    expected_evidence_type: str = "general"
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
            "semantic_focus": self.semantic_focus,
            "expected_evidence_type": self.expected_evidence_type,
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

        semantic_focus = cls._semantic_focus(q, legacy, intent_result)
        answer_type = cls._infer_answer_type(q, legacy, intent_result, semantic_focus)
        expected_evidence_type = cls._expected_evidence_type(semantic_focus, answer_type, legacy)
        if _POLICY_MARKERS.search(q):
            expected_evidence_type = "policy"
            if answer_type in {"faq", "general", "overview"}:
                answer_type = "documentation"
        scope_type = cls._scope_type(answer_type, semantic_focus, intent_result)
        preferred_purposes, unsuitable_purposes = purpose_expectations_for_answer_type(answer_type)
        preferred_evidence, unsuitable_evidence = cls._evidence_expectations(
            q, answer_type, semantic_focus, topic, topic_key, intent_result
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
            semantic_focus=semantic_focus,
            expected_evidence_type=expected_evidence_type,
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
    def _semantic_focus(
        query: str, legacy_intent: str, intent_result: RetrievalIntentResult
    ) -> str:
        # Locator before generic contact/overview so branch/ATM asks are not org-scoped.
        if _LOCATOR_MARKERS.search(query):
            return "locator"
        if legacy_intent in CONTACT_INTENTS or intent_result.answer_strategy == "contacts":
            return "contact"
        if _CONTACT_MARKERS.search(query):
            return "contact"
        if _POLICY_MARKERS.search(query) or legacy_intent in {"legal", "documentation"}:
            return "faq"
        if _BENEFITS_MARKERS.search(query):
            # Product-scoped benefit asks should not force organization overview.
            if legacy_intent in {"product_query", "topic_overview"} or (
                intent_result.matched_topic
                and legacy_intent not in OVERVIEW_INTENTS
            ):
                return "product_specification"
            return "organization_profile"
        if _PROCEDURE_MARKERS.search(query):
            return "procedure"
        # Rates/conditions/eligibility beat bare "what is/are" (e.g. "what are the conditions").
        if _ELIGIBILITY_MARKERS.search(query):
            return "eligibility"
        if _RATES_MARKERS.search(query):
            return "rates"
        if _CONDITIONS_MARKERS.search(query):
            return "product_specification"
        if _COMPARISON_MARKERS.search(query):
            return "comparison"
        if _OVERVIEW_DEFINITION_EXCEPTIONS.search(query):
            return "overview"
        # "What is <OrgName>?" when the subject matches known org aliases.
        if _DEFINITION_MARKERS.search(query) and legacy_intent in OVERVIEW_INTENTS:
            subject_m = re.search(
                r"(?:what is|what are|що таке|що це)\s+(.+?)\s*\??$",
                query.strip(),
                re.I,
            )
            aliases = {
                str(a).lower()
                for a in (getattr(intent_result, "matched_aliases", None) or [])
                if a
            }
            if subject_m and aliases:
                subject = subject_m.group(1).strip().lower()
                if any(a == subject or a in subject or subject in a for a in aliases if len(a) >= 3):
                    return "overview"
        if _DEFINITION_MARKERS.search(query):
            return "definition"
        # Single-token term asks (e.g. acronyms) prefer definition over broad overview.
        token = query.strip().strip("?!.")
        if (
            len(token.split()) == 1
            and 2 <= len(token) <= 12
            and token.lower() not in _NON_DEFINITION_SINGLES
            and legacy_intent in OVERVIEW_INTENTS
            and not _LOCATOR_MARKERS.search(token)
        ):
            return "definition"
        listing_hit = bool(_LISTING_MARKERS.search(query) or legacy_intent in LISTING_INTENTS)
        if listing_hit:
            # Bare "what … organization/company do?" is overview, not a product listing.
            org_activity = re.search(
                r"\b(organization|organisation|company|bank|site|portal|you|your|"
                r"організац\w*|компані\w*|банк\w*|ви\b|ваш\w*)\b",
                query,
                re.I,
            )
            product_list = re.search(
                r"\b(products?|services?|послуг\w*|перелік|опці\w*|options|"
                r"assortment|catalog|catalogue|offerings|види|типи)\b",
                query,
                re.I,
            )
            if org_activity and not product_list:
                return "overview"
            return "listing"
        if intent_result.is_broad or legacy_intent in OVERVIEW_INTENTS:
            return "overview"
        if legacy_intent in FAQ_INTENTS:
            return "faq"
        if intent_result.answer_strategy in {"specific_fact", "fact"}:
            return "product_specification"
        return "general"

    @staticmethod
    def _expected_evidence_type(semantic_focus: str, answer_type: str, legacy_intent: str) -> str:
        mapping = {
            "organization_profile": "organization_profile",
            "overview": "organization_profile",
            "definition": "definition",
            "procedure": "procedure",
            "locator": "locator",
            "contact": "contact",
            "rates": "rates",
            "product_specification": "product_specification",
            "eligibility": "eligibility",
            "comparison": "comparison",
            "listing": "product_overview",
            "faq": "faq",
        }
        if semantic_focus in mapping:
            if semantic_focus == "faq" and legacy_intent in {"legal", "documentation"}:
                return "policy"
            if semantic_focus == "faq" and answer_type == "documentation":
                return "policy"
            return mapping[semantic_focus]
        if legacy_intent in {"news_query"}:
            return "news"
        if "promotion" in legacy_intent or "offer" in legacy_intent:
            return "promotion"
        if answer_type == "documentation":
            return "documentation"
        if answer_type == "overview":
            return "organization_profile"
        return "general"

    @staticmethod
    def _infer_answer_type(
        query: str,
        legacy_intent: str,
        intent_result: RetrievalIntentResult,
        semantic_focus: str,
    ) -> str:
        # Semantic focus wins over coarse listing markers (e.g. "які переваги").
        if semantic_focus == "contact":
            return "contact"
        if semantic_focus == "locator":
            return "contact"
        if semantic_focus == "organization_profile":
            return "overview"
        if semantic_focus == "procedure":
            return "faq"
        if semantic_focus == "definition":
            return "definition"
        if semantic_focus == "comparison":
            return "comparison"
        if semantic_focus == "listing":
            return "listing"
        if semantic_focus in {"rates", "product_specification", "eligibility"}:
            return "fact"
        if semantic_focus == "faq":
            return "faq"
        if semantic_focus == "overview":
            return "overview"

        if legacy_intent in CONTACT_INTENTS or intent_result.answer_strategy == "contacts":
            return "contact"
        if _DEFINITION_MARKERS.search(query) and not _OVERVIEW_DEFINITION_EXCEPTIONS.search(
            query
        ):
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
    def _scope_type(
        answer_type: str,
        semantic_focus: str,
        intent_result: RetrievalIntentResult,
    ) -> str:
        if semantic_focus in {"locator", "contact"}:
            return "navigation"
        if semantic_focus == "organization_profile":
            return "organization_overview"
        if semantic_focus == "procedure":
            return "procedure"
        if semantic_focus in {"product_specification", "rates", "eligibility", "definition"}:
            return "exact_subject" if semantic_focus != "listing" else "product_family"
        if semantic_focus == "listing":
            return "product_family"
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
        semantic_focus: str,
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

        if semantic_focus == "organization_profile":
            preferred.extend(["organization profile", "about the organization", "company overview"])
            unsuitable.extend(
                [
                    "product listing only",
                    "individual product page",
                    "news archive",
                    "job openings",
                    "promotion campaign",
                ]
            )
        elif semantic_focus == "locator":
            preferred.extend(["branch locator", "location finder", "map", "office locator"])
            unsuitable.extend(["product listing", "news story", "marketing campaign"])
        elif semantic_focus == "definition":
            preferred.extend(["product overview", "service description", "definition"])
            unsuitable.extend(["homepage marketing", "news story", "promotion"])
        elif semantic_focus in {"product_specification", "rates", "eligibility"}:
            preferred.extend(["product terms", "conditions", "pricing", "eligibility"])
            unsuitable.extend(["adjacent product", "news story", "career page"])
        elif answer_type == "listing":
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
