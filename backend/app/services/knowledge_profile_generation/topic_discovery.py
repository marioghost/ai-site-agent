"""Stage 5 — topic discovery via clustering (URL, headings, entities)."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from app.services.knowledge_profile_generation.confidence_engine import ConfidenceEngine
from app.services.knowledge_profile_generation.models import (
    DiscoveredTopic,
    ExtractedEntity,
    PageRecord,
    WebsiteHierarchy,
)
from app.services.knowledge_profile_generation.structural_filters import (
    first_meaningful_path_segment,
    is_locale_like_path_segment,
)

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
    ) -> list[DiscoveredTopic]:
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

    def _cluster_key_from_page(self, page: PageRecord) -> str:
        seg = first_meaningful_path_segment(list(page.path_segments or []))
        if seg:
            return seg
        return _slug(page.title[:30]) if page.title else "topic"

    def _humanize(self, key: str, fallback: str) -> str:
        if fallback and key in ("general", "") and "|" not in fallback:
            part = re.split(r"[|\-–—]", fallback)[0].strip()
            if part and len(part) <= 60:
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
