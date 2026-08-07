"""Knowledge profile defaults, presets, validation and boost table builders."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.models.settings import Settings
from app.schemas.knowledge_profile import (
    AppliedKnowledgeConfig,
    ContentHintRule,
    DocumentTypeRule,
    ImportantTopic,
    IntentRule,
    KnowledgeProfile,
    QueryExpansionRule,
    SourcePriorityRule,
)

_PLACEHOLDER_RE = re.compile(r"\{\{([\w.]+)\}\}")

GENERIC_OVERVIEW_PATTERNS = [
    "розкажи про",
    "що таке",
    "хто такі",
    "хто такий",
    "інформація про",
    "все що знаєш про",
    "про компанію",
    "про організацію",
    "про нас",
    "about",
    "tell me about",
    "what is",
    "who is",
    "company info",
    "organization info",
    "about us",
    "about the company",
]

GENERIC_NEWS_MARKERS = ("новини", "новина", "news", "прес", "press", "blog")
GENERIC_CONTACT_MARKERS = (
    "контакт",
    "contact",
    "телефон",
    "phone",
    "адреса",
    "address",
    "зв'язатися",
    "звʼязатися",
)
GENERIC_FAQ_MARKERS = (
    "faq",
    "поширені запитання",
    "часті запитання",
    "питання та відповіді",
)


def _generic_document_type_rules() -> list[DocumentTypeRule]:
    return [
        DocumentTypeRule(
            document_type="promotion_page",
            url_patterns=[
                "/actions/", "/action/", "/promo", "/promotion", "/campaign",
                "/offer", "/discount", "/special",
            ],
            title_patterns=["promo", "promotion", "акція", "cashback", "bonus", "знижк"],
            priority=92,
        ),
        DocumentTypeRule(
            document_type="action_page",
            url_patterns=["/actions/", "/action/"],
            priority=91,
        ),
        DocumentTypeRule(
            document_type="offer_page",
            url_patterns=["/offer", "/offers/"],
            title_patterns=["offer", "пропозиц"],
            priority=90,
        ),
        DocumentTypeRule(
            document_type="news_page",
            url_patterns=["/news", "news/", "novyny", "новини", "press", "/press"],
            title_patterns=["News", "Новини", "Press"],
            priority=88,
        ),
        DocumentTypeRule(
            document_type="blog_page",
            url_patterns=["/blog", "blog/"],
            title_patterns=["Blog", "Блог"],
            priority=55,
        ),
        DocumentTypeRule(
            document_type="about_page",
            url_patterns=[
                "about-us", "about_us", "/about", "about/",
                "pro-kompaniyu", "pro-nas", "про-нас", "who-we-are",
                "/corporate/", "corporate-info",
                # Path-bounded company/history — avoid matching news slugs containing those words.
                "/company", "company/", "company-info", "our-company",
                "/history", "history/", "our-history", "istoriya", "історія",
            ],
            title_patterns=[
                "About", "Про компанію", "Про нас", "About us", "History", "Історія",
            ],
            heading_patterns=["About us", "Про нас", "History", "Історія"],
            priority=90,
        ),
        DocumentTypeRule(
            document_type="contact_page",
            url_patterns=["/contact", "contacts/", "contact-us", "kontakty"],
            title_patterns=["Contact", "Contacts", "Контакти"],
            priority=85,
        ),
        DocumentTypeRule(
            document_type="faq_page",
            url_patterns=["faq", "questions", "q-and-a"],
            title_patterns=["FAQ", "Поширені запитання"],
            priority=80,
        ),
        DocumentTypeRule(
            document_type="pricing_page",
            url_patterns=["pricing", "price", "tarify", "ціни", "tariffs"],
            title_patterns=["Pricing", "Prices", "Тарифи", "Ціни"],
            priority=75,
        ),
        DocumentTypeRule(
            document_type="product_page",
            url_patterns=["/product", "/products/", "/item/"],
            title_patterns=["Product"],
            priority=70,
        ),
        DocumentTypeRule(
            document_type="category_page",
            url_patterns=["/category", "/categories", "/catalog", "/services", "/products"],
            title_patterns=["Catalog", "Services", "Products", "Каталог", "Послуги"],
            priority=65,
        ),
        DocumentTypeRule(
            document_type="documentation_page",
            url_patterns=["docs", "documentation", "help/", "/api/"],
            title_patterns=["Documentation", "Docs", "Документація"],
            priority=72,
        ),
        DocumentTypeRule(
            document_type="support_page",
            url_patterns=["support", "help-center", "customer-service"],
            title_patterns=["Support", "Help", "Підтримка"],
            priority=68,
        ),
        DocumentTypeRule(
            document_type="legal_page",
            url_patterns=["privacy", "terms", "legal", "cookie", "gdpr", "політика", "умови"],
            title_patterns=["Privacy", "Terms", "Legal"],
            priority=40,
        ),
    ]


def _generic_content_hint_rules() -> list[ContentHintRule]:
    return [
        ContentHintRule(content_type_hint="about", patterns=["about us", "про нас", "про компані", "history of", "історія"], priority=90),
        ContentHintRule(content_type_hint="contacts", patterns=["контакт", "contact", "телефон", "phone", "email", "адреса"], priority=85),
        ContentHintRule(content_type_hint="faq", patterns=["faq", "поширені запитання", "часті запитання"], priority=80),
        ContentHintRule(content_type_hint="pricing", patterns=["pricing", "price list", "тариф", "ціни", "вартість"], priority=75),
        ContentHintRule(content_type_hint="products", patterns=["product", "catalog", "каталог", "товар", "послуг"], priority=70),
        ContentHintRule(content_type_hint="docs", patterns=["documentation", "docs", "api reference", "документація"], priority=68),
        ContentHintRule(content_type_hint="support", patterns=["support", "help center", "підтримка"], priority=65),
        ContentHintRule(content_type_hint="news", patterns=["новин", "news", "press release"], priority=50),
        ContentHintRule(content_type_hint="schedule", patterns=["working hours", "графік роботи", "години роботи", "schedule"], priority=60),
        ContentHintRule(content_type_hint="delivery", patterns=["delivery", "shipping", "доставка"], priority=55),
        ContentHintRule(content_type_hint="returns", patterns=["returns", "refund", "повернення"], priority=55),
    ]


def _generic_source_priority_rules() -> list[SourcePriorityRule]:
    return [
        SourcePriorityRule(
            query_intent="entity_overview",
            boost_document_types=["about_page", "homepage", "company_page"],
            deprioritize_document_types=[
                "news_page", "blog_page", "promotion_page", "action_page", "offer_page",
                "media_page", "contact_page", "documentation_page",
            ],
            boost_content_hints=["about", "overview"],
            deprioritize_content_hints=["news", "career", "employee_stories", "jobs", "recruitment"],
        ),
        SourcePriorityRule(
            query_intent="topic_overview",
            boost_document_types=["category_page", "product_page", "faq_page", "documentation_page"],
            deprioritize_document_types=[
                "news_page", "blog_page", "promotion_page", "action_page", "offer_page",
            ],
            boost_content_hints=["products", "support", "docs"],
        ),
        SourcePriorityRule(
            query_intent="contacts_query",
            boost_document_types=["contact_page", "homepage", "faq_page"],
            boost_content_hints=["contacts"],
        ),
        SourcePriorityRule(
            query_intent="faq_like",
            boost_document_types=["faq_page", "product_page", "support_page"],
            boost_content_hints=["faq", "support"],
        ),
        SourcePriorityRule(
            query_intent="news_query",
            boost_document_types=["news_page", "blog_page"],
            boost_content_hints=["news"],
        ),
    ]


def _generic_intent_rules() -> list[IntentRule]:
    return [
        IntentRule(
            key="news_query",
            label="News / press",
            patterns=list(GENERIC_NEWS_MARKERS),
            routing_intent="news_query",
            default_answer_strategy="overview",
            priority=90,
        ),
        IntentRule(
            key="contacts_query",
            label="Contact information",
            patterns=list(GENERIC_CONTACT_MARKERS),
            routing_intent="contacts_query",
            default_answer_strategy="contact",
            priority=88,
        ),
        IntentRule(
            key="faq_like",
            label="FAQ / how-to",
            patterns=list(GENERIC_FAQ_MARKERS),
            routing_intent="faq_like",
            default_answer_strategy="faq",
            priority=86,
        ),
        IntentRule(
            key="entity_overview",
            label="Entity overview",
            patterns=[
                *GENERIC_OVERVIEW_PATTERNS,
                "{{organization_name}}",
                "{{site_display_name}}",
                "{{entity_type}}",
            ],
            routing_intent="entity_overview",
            default_answer_strategy="overview",
            priority=100,
        ),
    ]


def _topic_intent_rules(topics: list[ImportantTopic]) -> list[IntentRule]:
    rules: list[IntentRule] = []
    for topic in topics:
        rules.append(
            IntentRule(
                key=f"topic_{topic.key}",
                label=topic.label or topic.key,
                patterns=["{{topic.aliases}}", "{{topic.label}}", topic.key],
                topic_key=topic.key,
                topic_required=True,
                routing_intent="topic_overview",
                default_answer_strategy=topic.answer_strategy,
                priority=75,
            )
        )
    return rules


def _generic_query_expansion_rules() -> list[QueryExpansionRule]:
    return [
        QueryExpansionRule(
            trigger_patterns=["розкажи про", "tell me about", "все що знаєш", "about"],
            add_terms=[
                "{{organization_name}}",
                "{{site_display_name}}",
                "{{organization_aliases}}",
                "{{site_subject}}",
                "{{entity_type}}",
                "about",
                "overview",
            ],
            trigger_intent="entity_overview",
        ),
        QueryExpansionRule(
            trigger_intent="topic_overview",
            add_terms=[
                "{{matched_topic.label}}",
                "{{matched_topic.aliases}}",
                "{{matched_topic.preferred_document_types}}",
                "{{matched_topic.preferred_content_hints}}",
            ],
        ),
        QueryExpansionRule(
            trigger_intent="entity_overview",
            add_terms=[
                "{{organization_name}}",
                "{{organization_aliases}}",
                "{{site_subject}}",
                "{{entity_type}}",
            ],
        ),
    ]


def generic_corporate_profile() -> KnowledgeProfile:
    return KnowledgeProfile(
        overview_query_patterns=list(GENERIC_OVERVIEW_PATTERNS),
        intents=_generic_intent_rules(),
        document_type_rules=_generic_document_type_rules(),
        content_hint_rules=_generic_content_hint_rules(),
        source_priority_rules=_generic_source_priority_rules(),
        query_expansion_rules=_generic_query_expansion_rules(),
    )


def bank_financial_profile() -> KnowledgeProfile:
    p = generic_corporate_profile()
    p.entity_type = "bank"
    p.site_subject = "banking services and financial information"
    p.important_topics = [
        ImportantTopic(
            key="rates",
            label="Exchange rates",
            aliases=["курси валют", "курс валют", "курс долара", "обмін валют", "exchange rates", "currency rates"],
            preferred_document_types=["rates_page", "homepage"],
            preferred_content_hints=["rates"],
            answer_strategy="table",
        ),
        ImportantTopic(
            key="credits",
            label="Loans / credits",
            aliases=["кредити", "кредит", "позика", "loans", "loan"],
            preferred_document_types=["product_page", "category_page", "faq_page"],
            preferred_content_hints=["products"],
            answer_strategy="overview",
        ),
        ImportantTopic(
            key="deposits",
            label="Deposits",
            aliases=["депозити", "депозит", "deposit", "deposits", "вклад"],
            preferred_document_types=["product_page", "category_page"],
            preferred_content_hints=["products"],
            answer_strategy="overview",
        ),
    ]
    extra_rules = [
        DocumentTypeRule(
            document_type="rates_page",
            url_patterns=["exchange-rate", "exchange-rates", "rates/", "/rates", "курс-валют", "курси-валют"],
            title_patterns=["Exchange rates", "Курси валют", "Курс валют"],
            priority=88,
        ),
        DocumentTypeRule(
            document_type="product_page",
            url_patterns=["/credit", "/loan", "/deposit", "/card", "кредит-", "депозит-"],
            priority=72,
        ),
        DocumentTypeRule(
            document_type="category_page",
            url_patterns=["/credits", "/deposits", "/cards", "кредити", "депозити"],
            priority=68,
        ),
    ]
    p.document_type_rules = extra_rules + p.document_type_rules
    p.content_hint_rules = [
        ContentHintRule(content_type_hint="rates", patterns=["курс валют", "exchange rate", "usd", "eur", "обмін валют"], priority=92),
        ContentHintRule(content_type_hint="products", patterns=["кредит", "депозит", "credit", "deposit", "card"], priority=78),
    ] + p.content_hint_rules
    p.source_priority_rules.append(
        SourcePriorityRule(
            query_intent="topic_overview",
            boost_document_types=["rates_page", "product_page", "category_page"],
            deprioritize_document_types=["news_page"],
            boost_content_hints=["rates", "products"],
        )
    )
    p.intents = _generic_intent_rules() + _topic_intent_rules(p.important_topics)
    return p


def ecommerce_profile() -> KnowledgeProfile:
    p = generic_corporate_profile()
    p.entity_type = "online_store"
    p.site_subject = "online store and product catalog"
    p.important_topics = [
        ImportantTopic(
            key="delivery",
            label="Delivery",
            aliases=["delivery", "shipping", "доставка", "відправлення"],
            preferred_document_types=["shipping_page", "faq_page", "support_page"],
            preferred_content_hints=["delivery"],
            answer_strategy="fact",
        ),
        ImportantTopic(
            key="returns",
            label="Returns",
            aliases=["returns", "refund", "повернення", "обмін"],
            preferred_document_types=["returns_page", "faq_page", "legal_page"],
            preferred_content_hints=["returns"],
            answer_strategy="fact",
        ),
    ]
    p.intents = _generic_intent_rules() + _topic_intent_rules(p.important_topics)
    return p


def saas_profile() -> KnowledgeProfile:
    p = generic_corporate_profile()
    p.entity_type = "saas"
    p.site_subject = "software platform documentation and pricing"
    p.important_topics = [
        ImportantTopic(
            key="pricing",
            label="Pricing",
            aliases=["pricing", "plans", "tariffs", "ціна", "тарифи", "підписка"],
            preferred_document_types=["pricing_page", "product_page"],
            preferred_content_hints=["pricing"],
            answer_strategy="pricing",
        ),
        ImportantTopic(
            key="docs",
            label="Documentation",
            aliases=["docs", "documentation", "api", "документація"],
            preferred_document_types=["documentation_page", "support_page"],
            preferred_content_hints=["docs"],
            answer_strategy="generic",
        ),
    ]
    p.intents = _generic_intent_rules() + _topic_intent_rules(p.important_topics)
    return p


def documentation_portal_profile() -> KnowledgeProfile:
    p = generic_corporate_profile()
    p.entity_type = "documentation"
    p.site_subject = "technical documentation and guides"
    p.source_priority_rules = [
        SourcePriorityRule(
            query_intent="entity_overview",
            boost_document_types=["documentation_page", "about_page", "homepage"],
            deprioritize_document_types=[
                "news_page", "blog_page", "promotion_page", "action_page", "offer_page",
            ],
            boost_content_hints=["docs", "about"],
        ),
        SourcePriorityRule(
            query_intent="topic_overview",
            boost_document_types=["documentation_page", "support_page", "faq_page"],
            boost_content_hints=["docs", "support"],
        ),
    ] + [r for r in p.source_priority_rules if r.query_intent not in {"entity_overview", "topic_overview"}]
    return p


def government_profile() -> KnowledgeProfile:
    p = generic_corporate_profile()
    p.entity_type = "government"
    p.site_subject = "public services and official information"
    return p


def university_profile() -> KnowledgeProfile:
    p = generic_corporate_profile()
    p.entity_type = "university"
    p.site_subject = "education programs and university information"
    p.document_type_rules.append(
        DocumentTypeRule(
            document_type="category_page",
            url_patterns=["programs", "faculty", "admission", "навчання", "факультет"],
            priority=70,
        )
    )
    return p


PRESETS: dict[str, KnowledgeProfile] = {
    "generic_corporate": generic_corporate_profile(),
    "bank_financial": bank_financial_profile(),
    "ecommerce": ecommerce_profile(),
    "saas": saas_profile(),
    "documentation_portal": documentation_portal_profile(),
    "government": government_profile(),
    "university": university_profile(),
}

KNOWN_PLACEHOLDERS = frozenset(
    {
        "organization_name",
        "site_display_name",
        "site_subject",
        "entity_type",
        "organization_aliases",
        "matched_topic.label",
        "matched_topic.aliases",
        "matched_topic.key",
        "matched_topic.preferred_document_types",
        "matched_topic.preferred_content_hints",
        "topic.label",
        "topic.aliases",
        "topic.key",
    }
)

BROAD_ROUTING_INTENTS = frozenset(
    {"entity_overview", "topic_overview", "category_overview", "unknown"}
)


@dataclass
class IntentMatchResult:
    rule_key: str
    routing_intent: str
    matched_topic: ImportantTopic | None = None
    matched_aliases: list[str] = field(default_factory=list)
    matched_patterns: list[str] = field(default_factory=list)
    answer_strategy: str = "generic"
    rule_label: str = ""


class KnowledgeProfileService:
    @staticmethod
    def default_profile() -> KnowledgeProfile:
        return generic_corporate_profile()

    @staticmethod
    def from_settings(settings: Settings) -> KnowledgeProfile:
        raw = getattr(settings, "knowledge_profile_json", None) or ""
        if not raw or raw.strip() in ("", "{}"):
            return KnowledgeProfileService.default_profile()
        try:
            data = json.loads(raw)
            if not data:
                return KnowledgeProfileService.default_profile()
            return KnowledgeProfile.model_validate(data)
        except Exception:
            return KnowledgeProfileService.default_profile()

    @staticmethod
    def to_json(profile: KnowledgeProfile) -> str:
        return profile.model_dump_json(indent=2)

    @staticmethod
    def resolve_intent_rules(profile: KnowledgeProfile) -> list[IntentRule]:
        if profile.intents:
            return sorted(profile.intents, key=lambda r: -r.priority)
        return _generic_intent_rules()

    @staticmethod
    def topic_by_key(profile: KnowledgeProfile, key: str) -> ImportantTopic | None:
        needle = (key or "").lower().strip()
        for topic in profile.important_topics:
            if topic.key.lower() == needle:
                return topic
        return None

    @staticmethod
    def resolve_rule_patterns(
        rule: IntentRule,
        profile: KnowledgeProfile,
        *,
        topic: ImportantTopic | None = None,
    ) -> list[str]:
        topic = topic or (
            KnowledgeProfileService.topic_by_key(profile, rule.topic_key)
            if rule.topic_key
            else None
        )
        patterns: list[str] = []
        for raw in rule.patterns:
            if not raw:
                continue
            if raw == "{{topic.aliases}}":
                if topic:
                    patterns.extend(a.lower().strip() for a in topic.aliases if a.strip())
                continue
            if raw == "{{topic.label}}":
                if topic and topic.label:
                    patterns.append(topic.label.lower().strip())
                continue
            for expanded in KnowledgeProfileService.expand_placeholders_with_context(
                raw, profile, topic=topic
            ):
                patterns.append(expanded.lower().strip())
        if rule.topic_key and topic:
            for alias in topic.aliases:
                a = alias.lower().strip()
                if a and a not in patterns:
                    patterns.append(a)
            key = topic.key.lower().strip()
            if key and key not in patterns:
                patterns.append(key)
        return [p for p in patterns if p and len(p) >= 2]

    @staticmethod
    def match_intent(profile: KnowledgeProfile, query: str) -> IntentMatchResult:
        raw = (query or "").strip().lower()
        if not raw:
            return IntentMatchResult(rule_key="unknown", routing_intent="unknown")

        rules = KnowledgeProfileService.resolve_intent_rules(profile)
        for rule in rules:
            topic = (
                KnowledgeProfileService.topic_by_key(profile, rule.topic_key)
                if rule.topic_key
                else None
            )
            patterns = KnowledgeProfileService.resolve_rule_patterns(rule, profile, topic=topic)
            matched_patterns = [p for p in patterns if p in raw]
            if not matched_patterns:
                continue
            if rule.topic_required and topic is None:
                continue
            matched_aliases = matched_patterns
            if topic is not None:
                _, topic_aliases = KnowledgeProfileService.match_topic(profile, raw)
                matched_aliases = topic_aliases or matched_patterns
            return IntentMatchResult(
                rule_key=rule.key,
                routing_intent=rule.routing_intent,
                matched_topic=topic,
                matched_aliases=matched_aliases,
                matched_patterns=matched_patterns,
                answer_strategy=rule.default_answer_strategy,
                rule_label=rule.label or rule.key,
            )

        topic, matched_aliases = KnowledgeProfileService.match_topic(profile, raw)
        if topic is not None:
            return IntentMatchResult(
                rule_key=f"topic_{topic.key}",
                routing_intent="topic_overview",
                matched_topic=topic,
                matched_aliases=matched_aliases,
                answer_strategy=topic.answer_strategy,
                rule_label=topic.label or topic.key,
            )

        for pattern in profile.overview_query_patterns:
            p = pattern.lower().strip()
            if p and p in raw:
                return IntentMatchResult(
                    rule_key="entity_overview",
                    routing_intent="entity_overview",
                    matched_aliases=[pattern],
                    matched_patterns=[pattern],
                    answer_strategy="overview",
                    rule_label="Entity overview",
                )

        org_hits = KnowledgeProfileService.match_organization_markers(raw, profile)
        if org_hits:
            return IntentMatchResult(
                rule_key="entity_overview",
                routing_intent="entity_overview",
                matched_aliases=org_hits,
                answer_strategy="overview",
                rule_label="Entity overview",
            )

        if any(
            m in raw
            for m in ("?", "який", "яка", "what ", "how ", "when ", "where ", "which ")
        ):
            return IntentMatchResult(
                rule_key="specific_fact",
                routing_intent="specific_fact",
                answer_strategy="fact",
                rule_label="Specific fact",
            )

        tokens = re.findall(r"\w{2,}", raw, re.UNICODE)
        if len(tokens) <= 3:
            return IntentMatchResult(
                rule_key="entity_overview",
                routing_intent="entity_overview",
                answer_strategy="overview",
                rule_label="Entity overview",
            )

        return IntentMatchResult(rule_key="unknown", routing_intent="unknown")

    @staticmethod
    def match_organization_markers(raw: str, profile: KnowledgeProfile) -> list[str]:
        hits: list[str] = []
        for value in (
            profile.organization_name,
            profile.site_display_name,
            profile.entity_type,
        ):
            v = (value or "").lower().strip()
            if v and v in raw:
                hits.append(value or v)
        for alias in profile.organization_aliases:
            a = alias.lower().strip()
            if a and a in raw:
                hits.append(alias)
        for token in re.findall(r"\w{3,}", (profile.site_subject or "").lower()):
            if token in raw and token not in hits:
                hits.append(token)
        return hits

    @staticmethod
    def auto_repair_profile(profile: KnowledgeProfile) -> tuple[KnowledgeProfile, list[str]]:
        warnings: list[str] = []
        repaired = deepcopy(profile)
        hint_types = {r.content_type_hint for r in repaired.content_hint_rules}
        doc_types = {r.document_type for r in repaired.document_type_rules}
        max_hint_priority = max((r.priority for r in repaired.content_hint_rules), default=0)

        for topic in repaired.important_topics:
            for hint in topic.preferred_content_hints:
                if hint and hint not in hint_types and hint not in {"generic", "overview"}:
                    max_hint_priority += 1
                    repaired.content_hint_rules.append(
                        ContentHintRule(
                            content_type_hint=hint,
                            patterns=[hint.replace("_", " ")],
                            priority=max_hint_priority,
                        )
                    )
                    hint_types.add(hint)
                    warnings.append(
                        f"Auto-created content hint '{hint}' referenced by topic '{topic.key}'."
                    )
            for dt in topic.preferred_document_types:
                if dt and dt not in doc_types and dt not in {"homepage", "generic_page"}:
                    warnings.append(
                        f"Topic '{topic.key}' references unknown document type '{dt}' (not auto-created)."
                    )

        if not repaired.intents:
            repaired.intents = _generic_intent_rules() + _topic_intent_rules(
                repaired.important_topics
            )

        return repaired, warnings

    @staticmethod
    def validate_profile(profile: KnowledgeProfile) -> list[str]:
        errors: list[str] = []
        topic_keys = [t.key for t in profile.important_topics]
        if len(topic_keys) != len(set(topic_keys)):
            errors.append("Important topic keys must be unique.")

        intent_keys = [r.key for r in profile.intents]
        if len(intent_keys) != len(set(intent_keys)):
            errors.append("Intent rule keys must be unique.")

        hint_keys = [r.content_type_hint for r in profile.content_hint_rules]
        if len(hint_keys) != len(set(hint_keys)):
            errors.append("Content hint keys must be unique.")

        doc_types = {r.document_type for r in profile.document_type_rules}
        hint_types = {r.content_type_hint for r in profile.content_hint_rules}
        routing_intents = {r.routing_intent for r in profile.intents} | {
            r.query_intent for r in profile.source_priority_rules
        }

        for rule in profile.intents:
            if rule.topic_key and rule.topic_key not in topic_keys:
                errors.append(
                    f"Intent '{rule.key}' references unknown topic_key '{rule.topic_key}'."
                )
            for pattern in rule.patterns:
                for match in _PLACEHOLDER_RE.findall(pattern):
                    if match not in KNOWN_PLACEHOLDERS and not match.startswith("topic."):
                        errors.append(
                            f"Intent '{rule.key}' uses unknown placeholder '{{{{{match}}}}}'."
                        )

        for topic in profile.important_topics:
            for dt in topic.preferred_document_types:
                if dt and dt not in doc_types and dt not in {"homepage", "generic_page"}:
                    errors.append(
                        f"Topic '{topic.key}' references unknown document type '{dt}'."
                    )
            for hint in topic.preferred_content_hints:
                if hint and hint not in hint_types and hint not in {"generic", "overview"}:
                    errors.append(
                        f"Topic '{topic.key}' references unknown content hint '{hint}'."
                    )

        for rule in profile.source_priority_rules:
            if rule.query_intent not in routing_intents and rule.query_intent not in {
                "entity_overview",
                "topic_overview",
                "category_overview",
                "specific_fact",
                "faq_like",
                "contacts_query",
                "news_query",
                "unknown",
            }:
                errors.append(
                    f"Priority rule references unknown intent '{rule.query_intent}'."
                )
            if not 0.0 <= rule.score_boost <= 1.0:
                errors.append(
                    f"Priority rule '{rule.query_intent}' has invalid score_boost."
                )
            for dt in rule.boost_document_types + rule.deprioritize_document_types:
                if dt and dt not in doc_types and dt not in {"homepage", "generic_page"}:
                    errors.append(
                        f"Priority rule '{rule.query_intent}' references unknown document type '{dt}'."
                    )
            for hint in rule.boost_content_hints + rule.deprioritize_content_hints:
                if hint and hint not in hint_types and hint not in {"generic", "overview"}:
                    errors.append(
                        f"Priority rule '{rule.query_intent}' references unknown content hint '{hint}'."
                    )

        for rule in profile.query_expansion_rules:
            trigger = rule.trigger_intent or rule.intent
            if trigger and trigger not in routing_intents and trigger not in {
                "entity_overview",
                "topic_overview",
                "category_overview",
                "specific_fact",
                "faq_like",
                "contacts_query",
                "news_query",
                "unknown",
            }:
                errors.append(
                    f"Query expansion rule references unknown trigger_intent '{trigger}'."
                )
            for term in rule.add_terms:
                for match in _PLACEHOLDER_RE.findall(term):
                    if match not in KNOWN_PLACEHOLDERS and not match.startswith("topic."):
                        errors.append(
                            f"Query expansion uses unknown placeholder '{{{{{match}}}}}'."
                        )
        return errors

    @staticmethod
    def expand_placeholders_with_context(
        text: str,
        profile: KnowledgeProfile,
        *,
        topic: ImportantTopic | None = None,
        matched_topic: ImportantTopic | None = None,
    ) -> list[str]:
        topic = matched_topic or topic
        results: list[str] = []

        def replacer(match: re.Match[str]) -> str:
            key = match.group(1)
            if key == "organization_name":
                return profile.organization_name or profile.site_display_name or ""
            if key == "site_display_name":
                return profile.site_display_name or profile.organization_name or ""
            if key == "site_subject":
                return profile.site_subject or ""
            if key == "entity_type":
                return profile.entity_type or ""
            if key == "organization_aliases":
                return " ".join(profile.organization_aliases)
            if topic is not None:
                if key in {"matched_topic.label", "topic.label"}:
                    return topic.label or topic.key
                if key in {"matched_topic.key", "topic.key"}:
                    return topic.key
                if key in {"matched_topic.aliases", "topic.aliases"}:
                    return " ".join(topic.aliases)
                if key in {
                    "matched_topic.preferred_document_types",
                    "topic.preferred_document_types",
                }:
                    return " ".join(topic.preferred_document_types)
                if key in {
                    "matched_topic.preferred_content_hints",
                    "topic.preferred_content_hints",
                }:
                    return " ".join(topic.preferred_content_hints)
            return match.group(0)

        expanded = _PLACEHOLDER_RE.sub(replacer, text).strip()
        if "{{organization_aliases}}" in text:
            for alias in profile.organization_aliases:
                if alias.strip():
                    results.append(alias.strip())
        if topic is not None and "{{matched_topic.aliases}}" in text:
            results.extend(a.strip() for a in topic.aliases if a.strip())
        if expanded and expanded not in results and not expanded.startswith("{{"):
            results.append(expanded)
        return [r for r in results if r]

    @staticmethod
    def expand_placeholders(text: str, profile: KnowledgeProfile) -> list[str]:
        return KnowledgeProfileService.expand_placeholders_with_context(text, profile)

    @staticmethod
    def build_boost_tables(
        profile: KnowledgeProfile,
    ) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
        doc_boosts: dict[str, dict[str, float]] = {}
        hint_boosts: dict[str, dict[str, float]] = {}
        for rule in profile.source_priority_rules:
            intent = rule.query_intent
            doc_boosts.setdefault(intent, {})
            hint_boosts.setdefault(intent, {})
            base = rule.score_boost
            for i, dt in enumerate(rule.boost_document_types):
                doc_boosts[intent][dt] = max(doc_boosts[intent].get(dt, 0), base - i * 0.03)
            for i, dt in enumerate(rule.deprioritize_document_types):
                doc_boosts[intent][dt] = min(doc_boosts[intent].get(dt, 0), -0.28 - i * 0.02)
            for i, hint in enumerate(rule.boost_content_hints):
                hint_boosts[intent][hint] = max(hint_boosts[intent].get(hint, 0), base * 0.85 - i * 0.03)
            for i, hint in enumerate(rule.deprioritize_content_hints):
                hint_boosts[intent][hint] = min(hint_boosts[intent].get(hint, 0), -0.20 - i * 0.02)
        return doc_boosts, hint_boosts

    @staticmethod
    def priority_rule_for_intent(
        profile: KnowledgeProfile, intent: str
    ) -> SourcePriorityRule | None:
        for rule in profile.source_priority_rules:
            if rule.query_intent == intent:
                return rule
        return None

    @staticmethod
    def applied_config_for_intent(
        profile: KnowledgeProfile, intent: str
    ) -> AppliedKnowledgeConfig:
        rule = KnowledgeProfileService.priority_rule_for_intent(profile, intent)
        if rule is None:
            return AppliedKnowledgeConfig(detected_intent=intent)
        return AppliedKnowledgeConfig(
            detected_intent=intent,
            boosted_document_types=list(rule.boost_document_types),
            deprioritized_document_types=list(rule.deprioritize_document_types),
            boosted_content_hints=list(rule.boost_content_hints),
            deprioritized_content_hints=list(rule.deprioritize_content_hints),
        )

    @staticmethod
    def export_profile(profile: KnowledgeProfile) -> dict:
        return profile.model_dump()

    @staticmethod
    def import_profile(data: dict) -> KnowledgeProfile:
        profile = KnowledgeProfile.model_validate(data)
        errors = KnowledgeProfileService.validate_profile(profile)
        if errors:
            raise ValueError("; ".join(errors))
        return profile

    @staticmethod
    def load_preset(name: str) -> KnowledgeProfile:
        if name not in PRESETS:
            raise KeyError(name)
        return deepcopy(PRESETS[name])

    @staticmethod
    def list_presets() -> list[dict[str, str]]:
        labels = {
            "generic_corporate": "Generic corporate website",
            "bank_financial": "Bank / financial services",
            "ecommerce": "Ecommerce store",
            "saas": "SaaS / software product",
            "documentation_portal": "Documentation portal",
            "government": "Government / public service",
            "university": "University / education",
        }
        return [{"id": k, "label": labels.get(k, k)} for k in PRESETS]

    @staticmethod
    def _pattern_matches(pattern: str, *, url: str, haystack: str) -> bool:
        """Match document-type patterns with path-segment safety for `/…` URL rules."""
        p = (pattern or "").lower().strip()
        if not p:
            return False
        # Slash-prefixed URL rules: match path segments, not substring-in-slug.
        if p.startswith("/") and url:
            path = (urlparse(url.lower()).path or "/").rstrip("/") or "/"
            needle = p.strip("/")
            if not needle:
                return path == "/"
            segments = [s for s in path.split("/") if s]
            if "/" in needle:
                return needle in "/".join(segments) or path.endswith("/" + needle)
            return needle in segments
        return p in haystack

    @staticmethod
    def match_document_type(
        profile: KnowledgeProfile,
        *,
        url: str,
        title: str = "",
        headings: str = "",
        source_type: str = "page",
        is_homepage: bool = False,
    ) -> str:
        if is_homepage:
            return "homepage"
        if source_type in ("pdf", "docx", "txt"):
            haystack = f"{title} {url}".lower()
        else:
            haystack = f"{url} {title} {headings}".lower()

        rules = sorted(profile.document_type_rules, key=lambda r: -r.priority)
        for rule in rules:
            patterns = rule.url_patterns + rule.title_patterns + rule.heading_patterns
            if any(
                KnowledgeProfileService._pattern_matches(p, url=url, haystack=haystack)
                for p in patterns
                if p
            ):
                return rule.document_type
        return "generic_page"

    @staticmethod
    def match_content_hint(profile: KnowledgeProfile, *parts: str) -> str:
        haystack = " ".join(p for p in parts if p).lower()
        if not haystack:
            return "generic"
        rules = sorted(profile.content_hint_rules, key=lambda r: -r.priority)
        for rule in rules:
            if any(p.lower() in haystack for p in rule.patterns if p):
                return rule.content_type_hint
        return "generic"

    @staticmethod
    def match_topic(
        profile: KnowledgeProfile, query: str
    ) -> tuple[ImportantTopic | None, list[str]]:
        raw = (query or "").lower()
        for topic in profile.important_topics:
            matched: list[str] = []
            for alias in topic.aliases:
                a = alias.lower().strip()
                if a and a in raw:
                    matched.append(alias)
            if matched:
                return topic, matched
            if topic.key.lower() in raw:
                matched.append(topic.key)
                return topic, matched
        return None, []
