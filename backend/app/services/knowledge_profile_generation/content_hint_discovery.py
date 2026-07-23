"""Stage 6 — content hint discovery with registration and validation."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from app.services.knowledge_profile_generation.models import (
    ContentHintCandidate,
    DiscoveredTopic,
    EvidenceItem,
    PageRecord,
    WebsiteHierarchy,
)
from app.services.knowledge_profile_generation.confidence_engine import ConfidenceEngine

_BASE_HINTS: dict[str, list[str]] = {
    "about": ["about us", "про нас", "про банк", "about the company"],
    "contacts": ["contact", "контакт", "телефон", "email", "зв'яз"],
    "faq": ["faq", "question", "питання", "часті питання"],
    "rates": ["exchange rate", "курс", "валют", "currency"],
    "products": ["product", "card", "карт", "кредит", "loan", "deposit"],
    "news": ["news", "новин", "press", "announcement"],
    "pricing": ["price", "tariff", "тариф", "commission", "коміс"],
    "support": ["support", "help", "допомог", "служба підтримки"],
    "delivery": ["delivery", "достав", "shipping"],
    "docs": ["documentation", "документ", "api reference", "guide"],
}


def _slug_hint(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return s[:32] or "generic"


class ContentHintDiscovery:
    def __init__(self) -> None:
        self.confidence = ConfidenceEngine()
        self._registry: dict[str, ContentHintCandidate] = {}

    def discover(
        self,
        pages: list[PageRecord],
        hierarchy: WebsiteHierarchy,
        topics: list[DiscoveredTopic],
    ) -> list[ContentHintCandidate]:
        self._registry.clear()
        hint_pages: dict[str, set[str]] = defaultdict(set)
        heading_signals: Counter[str] = Counter()

        cat_by_url = {c.url: c.category for c in hierarchy.categories}

        for page in pages:
            cat = cat_by_url.get(page.url, "")
            if cat and cat not in ("general", "homepage"):
                hint_id = _slug_hint(cat)
                hint_pages[hint_id].add(page.url)
                for pat in _BASE_HINTS.get(cat, [cat.replace("_", " ")]):
                    heading_signals[hint_id] += 1

            for hint in page.content_hints:
                if hint and hint != "generic":
                    hid = _slug_hint(hint)
                    hint_pages[hid].add(page.url)

            for h in page.headings:
                hl = h.lower()
                for hint_id, patterns in _BASE_HINTS.items():
                    if any(p in hl for p in patterns):
                        hint_pages[hint_id].add(page.url)
                        heading_signals[hint_id] += 1

        for topic in topics:
            for hint in topic.preferred_content_hints:
                hid = _slug_hint(hint)
                hint_pages.setdefault(hid, set()).update(
                    p.url for p in pages if topic.cluster_key in p.url
                )

        for hint_id, urls in hint_pages.items():
            patterns = list(_BASE_HINTS.get(hint_id, [hint_id.replace("_", " ")]))
            page_count = len(urls)
            conf = self.confidence.hint_score(page_count, min(1.0, heading_signals[hint_id] / 10))
            candidate = ContentHintCandidate(
                hint_id=hint_id,
                patterns=patterns,
                confidence=round(conf, 3),
                evidence=[
                    EvidenceItem(
                        source="pages",
                        weight=min(40, page_count * 2),
                        detail=f"{page_count} pages",
                    )
                ],
                page_count=page_count,
            )
            self.register(candidate)

        if "generic" not in self._registry:
            self.register(
                ContentHintCandidate(
                    hint_id="generic",
                    patterns=["general content"],
                    confidence=0.3,
                    page_count=len(pages),
                )
            )

        return list(self._registry.values())

    def register(self, candidate: ContentHintCandidate) -> None:
        existing = self._registry.get(candidate.hint_id)
        if existing is None or candidate.page_count > existing.page_count:
            self._registry[candidate.hint_id] = candidate

    def registered_ids(self) -> set[str]:
        return set(self._registry.keys())

    def validate_topic_hints(self, topics: list[DiscoveredTopic]) -> list[DiscoveredTopic]:
        """Ensure topics only reference registered hint IDs."""
        reg = self.registered_ids()
        fixed: list[DiscoveredTopic] = []
        for topic in topics:
            valid_hints = [h for h in topic.preferred_content_hints if _slug_hint(h) in reg]
            if not valid_hints and topic.cluster_key:
                guess = _slug_hint(topic.cluster_key)
                if guess in reg:
                    valid_hints = [guess]
            fixed.append(topic.model_copy(update={"preferred_content_hints": valid_hints}))
        return fixed

    def to_rules(self) -> list:
        from app.schemas.knowledge_profile import ContentHintRule

        rules: list[ContentHintRule] = []
        for hint_id, cand in sorted(self._registry.items(), key=lambda x: -x[1].page_count):
            rules.append(
                ContentHintRule(
                    content_type_hint=hint_id,
                    patterns=cand.patterns or [hint_id.replace("_", " ")],
                    priority=min(100, 40 + cand.page_count),
                )
            )
        return rules
