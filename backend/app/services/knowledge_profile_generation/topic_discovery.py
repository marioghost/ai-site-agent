"""Stage 5 — topic discovery via clustering (URL, headings, entities)."""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from app.services.knowledge_profile_generation.confidence_engine import ConfidenceEngine
from app.services.knowledge_profile_generation.lexical_grounding import labels_overlap
from app.services.knowledge_profile_generation.models import (
    DiscoveredTopic,
    EvidenceItem,
    ExtractedEntity,
    PageRecord,
    WebsiteHierarchy,
)
from app.services.knowledge_profile_generation.structural_filters import (
    first_meaningful_path_segment,
    is_locale_like_path_segment,
)
from app.services.knowledge_understanding.models import Concept, EvidenceLink
from app.services.knowledge_understanding.normalizer import concept_key_for

_GENERIC_LABELS = frozenset(
    {
        "general",
        "products",
        "product",
        "support",
        "pricing",
        "information",
        "other",
        "services",
        "service",
        "news",
        "page",
        "pages",
        "content",
        "main",
        "home",
    }
)


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return s[:48] or "topic"


class TopicDiscovery:
    def __init__(self) -> None:
        self.confidence = ConfidenceEngine()

    def discover(
        self,
        pages: list[PageRecord],
        hierarchy: WebsiteHierarchy,
        entities: list[ExtractedEntity],
        organization_name: str = "",
        understanding_concepts: list[Concept] | None = None,
        understanding_evidence: list[EvidenceLink] | None = None,
    ) -> list[DiscoveredTopic]:
        semantic_topics = self._from_understanding(
            pages,
            understanding_concepts or [],
            understanding_evidence or [],
            organization_name=organization_name,
        )
        if len(semantic_topics) >= 2:
            return semantic_topics
        semantic_topics = self._from_source_intelligence(
            pages,
            organization_name=organization_name,
        )
        if len(semantic_topics) >= 2:
            return semantic_topics

        total = max(len(pages), 1)
        clusters: dict[str, dict] = defaultdict(
            lambda: {
                "urls": set(),
                "headings": Counter(),
                "menu_hits": 0,
                "entity_hits": 0,
                "title": "",
                "category": "",
            }
        )

        cat_by_url = {c.url: c.category for c in hierarchy.categories}
        menu_set = set(hierarchy.menu_links)

        for page in pages:
            cat = cat_by_url.get(page.url, "")
            if cat in ("general", "homepage", "") or is_locale_like_path_segment(cat):
                key = self._cluster_key_from_page(page)
            else:
                key = cat
            if not key or is_locale_like_path_segment(key):
                continue
            cluster = clusters[key]
            cluster["urls"].add(page.url)
            cluster["category"] = cat or key
            if not cluster["title"]:
                cluster["title"] = self._humanize(key, page.title)
            for h in page.headings:
                cluster["headings"][h.lower()] += 1
            for seg in page.path_segments[:2]:
                if seg in menu_set:
                    cluster["menu_hits"] += 1

        for key, data in list(clusters.items()):
            label_l = self._humanize(key, "").lower()
            for ent in entities:
                if ent.entity_type in ("branch", "atm"):
                    continue
                if label_l in ent.name.lower() or ent.name.lower() in label_l:
                    data["entity_hits"] += ent.frequency

        topics: list[DiscoveredTopic] = []
        seen_ids: set[str] = set()

        for key, data in sorted(clusters.items(), key=lambda x: -len(x[1]["urls"])):
            page_count = len(data["urls"])
            title = data["title"] or self._humanize(key, key)
            label_l = title.lower()

            if is_locale_like_path_segment(key) or is_locale_like_path_segment(label_l):
                continue
            if self._is_generic(title, page_count, total):
                continue
            if organization_name and label_l == organization_name.lower():
                continue

            topic_id = _slug(key)
            if topic_id in seen_ids:
                topic_id = _slug(f"{key}_{page_count}")
            seen_ids.add(topic_id)

            heading_hits = sum(data["headings"].values())
            conf, evidence = self.confidence.topic_score(
                page_count=page_count,
                total_pages=total,
                menu_hits=data["menu_hits"],
                heading_hits=min(heading_hits, 20),
                entity_freq=data["entity_hits"],
            )

            if page_count < 2 and conf < 0.4 and total > 10:
                continue
            if page_count < 1:
                continue

            aliases = self._aliases(title, key, data["headings"])
            topics.append(
                DiscoveredTopic(
                    id=topic_id,
                    title=title,
                    description=f"Cluster from {page_count} pages in '{key}' section",
                    aliases=aliases,
                    page_count=page_count,
                    confidence=round(conf, 3),
                    evidence=evidence,
                    preferred_content_hints=[],
                    preferred_document_types=["category_page"],
                    answer_strategy="generic",
                    cluster_key=key,
                )
            )

        topics.sort(key=lambda t: (-t.page_count, -t.confidence))
        return topics[:15]

    def _from_understanding(
        self,
        pages: list[PageRecord],
        concepts: list[Concept],
        evidence: list[EvidenceLink],
        *,
        organization_name: str,
    ) -> list[DiscoveredTopic]:
        """Project the existing site-wide understanding into profile topics."""
        if not concepts or not evidence:
            return []

        pages_by_id = {page.source_id: page for page in pages}
        explaining: dict[str, set[int]] = defaultdict(set)
        for link in evidence:
            if link.relation == "explains" and link.source_id in pages_by_id:
                explaining[link.concept_key].add(link.source_id)

        supported_counts = [len(ids) for ids in explaining.values() if ids]
        if not supported_counts:
            return []
        max_support = max(supported_counts)
        minimum_support = 1 if len(pages) == 1 else 2
        broad_support = max(minimum_support, math.ceil(len(pages) * 0.01))
        topics: list[DiscoveredTopic] = []

        for concept in concepts:
            source_ids = explaining.get(concept.concept_key, set())
            page_count = len(source_ids)
            label = " ".join((concept.label or "").split())
            if page_count < minimum_support or not label:
                continue
            purpose_diversity = self._purpose_diversity(
                source_ids,
                pages_by_id,
            )
            if (
                page_count < broad_support
                and concept.canonical_source_id is None
                and purpose_diversity < 2
            ):
                continue
            if organization_name and label.casefold() == organization_name.casefold():
                continue
            if self._is_document_purpose_cluster(label, source_ids, pages_by_id):
                continue

            confidence = self.confidence.understanding_topic_score(
                concept_confidence=concept.confidence,
                evidence_count=page_count,
                max_evidence_count=max_support,
            )
            aliases = list(
                dict.fromkeys(
                    value
                    for value in (label, *concept.aliases)
                    if value and value.casefold() != label.casefold()
                )
            )[:8]
            topics.append(
                DiscoveredTopic(
                    id=concept.concept_key,
                    title=label,
                    description=f"Understood from {page_count} independent sources",
                    aliases=aliases,
                    page_count=page_count,
                    confidence=round(confidence, 3),
                    evidence=[
                        self._understanding_evidence(page_count, confidence)
                    ],
                    preferred_content_hints=[],
                    preferred_document_types=["category_page"],
                    answer_strategy="generic",
                    cluster_key=concept.concept_key,
                )
            )

        topics.sort(key=lambda topic: (-topic.confidence, -topic.page_count, topic.title.casefold()))
        return self._distinct_topics(topics)[:15]

    def _from_source_intelligence(
        self,
        pages: list[PageRecord],
        *,
        organization_name: str,
    ) -> list[DiscoveredTopic]:
        """Fallback projection when no persisted Understanding snapshot exists.

        Source Intelligence remains the semantic authority; this method only
        aggregates its observed labels and does not infer an ontology.
        """
        groups: dict[str, dict] = {}
        for page in pages:
            semantic = page.semantic_profile
            label = " ".join((semantic.main_topic if semantic else "").split())
            if not semantic or not label:
                continue
            key = label.casefold()
            group = groups.setdefault(
                key,
                {
                    "label": label,
                    "source_ids": set(),
                    "confidence": [],
                    "aliases": [],
                    "canonical_count": 0,
                    "purposes": set(),
                },
            )
            group["source_ids"].add(page.source_id)
            group["confidence"].append(
                float(semantic.main_topic_confidence or semantic.confidence)
            )
            group["aliases"].extend(semantic.synonyms or [])
            group["canonical_count"] += int(page.canonical)
            if semantic.document_purpose:
                group["purposes"].add(semantic.document_purpose.casefold())

        if not groups:
            return []
        minimum_support = 1 if len(pages) == 1 else max(
            2, math.ceil(math.log10(max(len(pages), 10)))
        )
        max_support = max(len(group["source_ids"]) for group in groups.values())
        broad_support = max(minimum_support, math.ceil(len(pages) * 0.01))
        pages_by_id = {page.source_id: page for page in pages}
        topics: list[DiscoveredTopic] = []

        for key, group in groups.items():
            source_ids: set[int] = group["source_ids"]
            label: str = group["label"]
            if len(source_ids) < minimum_support:
                continue
            if (
                len(source_ids) < broad_support
                and not group["canonical_count"]
                and len(group["purposes"]) < 2
            ):
                continue
            if is_locale_like_path_segment(label):
                continue
            if organization_name and key == organization_name.casefold():
                continue
            if self._is_document_purpose_cluster(label, source_ids, pages_by_id):
                continue
            semantic_confidence = sum(group["confidence"]) / max(
                len(group["confidence"]), 1
            )
            confidence = self.confidence.understanding_topic_score(
                concept_confidence=semantic_confidence,
                evidence_count=len(source_ids),
                max_evidence_count=max_support,
            )
            aliases = list(
                dict.fromkeys(
                    alias.strip()
                    for alias in group["aliases"]
                    if alias.strip() and alias.casefold() != key
                )
            )[:8]
            topics.append(
                DiscoveredTopic(
                    id=concept_key_for(label),
                    title=label,
                    description=f"Understood by Source Intelligence across {len(source_ids)} sources",
                    aliases=aliases,
                    page_count=len(source_ids),
                    confidence=round(confidence, 3),
                    evidence=[
                        EvidenceItem(
                            source="source_intelligence",
                            weight=round(confidence * 100, 3),
                            detail=f"{len(source_ids)} independent sources",
                        )
                    ],
                    preferred_content_hints=[],
                    preferred_document_types=["category_page"],
                    answer_strategy="generic",
                    cluster_key=key,
                )
            )

        topics.sort(
            key=lambda topic: (-topic.confidence, -topic.page_count, topic.title.casefold())
        )
        return self._distinct_topics(topics)[:15]

    @staticmethod
    def _distinct_topics(
        topics: list[DiscoveredTopic],
    ) -> list[DiscoveredTopic]:
        """Keep one representative when labels express the same concept."""
        selected: list[DiscoveredTopic] = []
        for topic in topics:
            if any(
                labels_overlap(topic.title, existing.title)
                for existing in selected
            ):
                continue
            selected.append(topic)
        return selected

    @staticmethod
    def _understanding_evidence(page_count: int, confidence: float) -> EvidenceItem:
        return EvidenceItem(
            source="knowledge_understanding",
            weight=round(confidence * 100, 3),
            detail=f"{page_count} independent sources",
        )

    @staticmethod
    def _is_document_purpose_cluster(
        label: str,
        source_ids: set[int],
        pages_by_id: dict[int, PageRecord],
    ) -> bool:
        """Reject content-format clusters using SI's own purpose evidence."""
        label_tokens = set(re.findall(r"\w+", label.casefold(), re.UNICODE))
        if not label_tokens:
            return True
        purpose_counts: Counter[str] = Counter()
        for source_id in source_ids:
            semantic = pages_by_id[source_id].semantic_profile
            purpose = (semantic.document_purpose if semantic else "").strip()
            if purpose:
                purpose_counts[purpose] += 1
        if not purpose_counts:
            return False
        purpose, count = purpose_counts.most_common(1)[0]
        if count / max(len(source_ids), 1) < 0.8:
            return False
        purpose_tokens = set(re.findall(r"\w+", purpose.casefold(), re.UNICODE))
        return bool(purpose_tokens) and (
            label_tokens <= purpose_tokens or purpose_tokens <= label_tokens
        )

    @staticmethod
    def _purpose_diversity(
        source_ids: set[int],
        pages_by_id: dict[int, PageRecord],
    ) -> int:
        purposes: set[str] = set()
        for source_id in source_ids:
            semantic = pages_by_id[source_id].semantic_profile
            if semantic and semantic.document_purpose:
                purposes.add(semantic.document_purpose.casefold())
        return len(purposes)

    def _cluster_key_from_page(self, page: PageRecord) -> str:
        seg = first_meaningful_path_segment(list(page.path_segments or []))
        if seg:
            return seg
        return _slug(page.title[:30]) if page.title else "topic"

    def _humanize(self, key: str, fallback: str) -> str:
        # Prefer a clean page title over the URL slug — labels must be site-grounded.
        if fallback and "|" not in fallback:
            part = re.split(r"[|\-–—]", fallback)[0].strip()
            if part and 2 <= len(part) <= 60:
                return part
        return key.replace("-", " ").replace("_", " ").title()

    def _is_generic(self, title: str, page_count: int, total: int) -> bool:
        label = title.lower().strip()
        if label in _GENERIC_LABELS and page_count < total * 0.12:
            return True
        return False

    def _aliases(self, title: str, key: str, headings: Counter[str]) -> list[str]:
        aliases = [title, key.replace("-", " "), key.replace("_", " ")]
        for h, _ in headings.most_common(3):
            if 4 <= len(h) <= 60:
                aliases.append(h)
        return list(dict.fromkeys(a for a in aliases if a))[:8]
