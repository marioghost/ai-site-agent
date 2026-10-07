"""Stage 6 — content hint discovery from site structure (no industry vocab)."""
from __future__ import annotations

import re
import math
from collections import defaultdict

from app.services.knowledge_profile_generation.confidence_engine import ConfidenceEngine
from app.services.knowledge_profile_generation.models import (
    ContentHintCandidate,
    DiscoveredTopic,
    EvidenceItem,
    PageRecord,
    WebsiteHierarchy,
)


def _slug_hint(text: str) -> str:
    s = re.sub(r"[^\w]+", "_", text.casefold(), flags=re.UNICODE).strip("_")
    return s[:48] or "generic"


def _patterns_for(hint_id: str) -> list[str]:
    """Derive match patterns from the hint id itself (structural, not lexical catalogs)."""
    spaced = hint_id.replace("_", " ").strip()
    parts = [p for p in hint_id.split("_") if p]
    out = [spaced] if spaced else []
    out.extend(parts)
    return list(dict.fromkeys(a for a in out if a))[:6]


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
        hint_strengths: dict[str, list[float]] = defaultdict(list)
        del hierarchy, topics

        for page in pages:
            semantic = page.semantic_profile
            if semantic and semantic.document_purpose:
                purpose_id = _slug_hint(semantic.document_purpose)
                observed = {purpose_id} if purpose_id != "generic" else set()
                if purpose_id != "generic":
                    hint_strengths[purpose_id].append(
                        float(semantic.document_purpose_confidence or semantic.confidence)
                    )
            else:
                observed = set()
            if not observed:
                observed = {
                    _slug_hint(hint)
                    for hint in page.content_hints
                    if hint and _slug_hint(hint) != "generic"
                }
            for hint_id in observed:
                hint_pages[hint_id].add(page.url)

        page_total = len(pages)
        minimum_support = 1 if page_total <= 1 else max(2, math.ceil(math.log10(page_total)))
        candidates: list[ContentHintCandidate] = []
        for hint_id, urls in hint_pages.items():
            page_count = len(urls)
            if page_count < minimum_support:
                continue
            strengths = hint_strengths.get(hint_id, [])
            pattern_strength = (
                sum(strengths) / len(strengths)
                if strengths
                else min(1.0, page_count / 10)
            )
            conf = self.confidence.hint_score(
                page_count,
                pattern_strength,
                total_pages=page_total,
            )
            candidates.append(
                ContentHintCandidate(
                    hint_id=hint_id,
                    patterns=_patterns_for(hint_id),
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
            )

        output_limit = max(4, min(24, math.ceil(math.sqrt(max(page_total, 1)))))
        candidates.sort(
            key=lambda candidate: (
                -candidate.page_count,
                -candidate.confidence,
                candidate.hint_id,
            )
        )
        for candidate in candidates[:output_limit]:
            self.register(candidate)

        self.register(
            ContentHintCandidate(
                hint_id="generic",
                patterns=["general content"],
                confidence=0.3,
                page_count=page_total,
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
                    patterns=cand.patterns or _patterns_for(hint_id),
                    priority=min(100, 40 + cand.page_count),
                )
            )
        return rules
