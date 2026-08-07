"""Stage 4 — entity extraction from metadata and page structure."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from app.services.knowledge_profile_generation.models import (
    ExtractedEntity,
    MetadataDataset,
    PageRecord,
)
from app.services.knowledge_profile_generation.structural_filters import (
    SECTION_NOISE_LABELS,
)

# Shape-based extractors only (no industry phrase catalogs).
_ORG_TOKEN = re.compile(r"\b([A-ZА-ЯІЇЄ][A-ZА-ЯІЇЄ0-9\-]{2,})\b")
_CURRENCY = re.compile(r"\b(USD|EUR|UAH|GBP|CHF|PLN|JPY|CNY)\b")


class EntityExtractor:
    def extract(
        self,
        pages: list[PageRecord],
        metadata: MetadataDataset,
        organization_name: str = "",
    ) -> list[ExtractedEntity]:
        freq: Counter[tuple[str, str]] = Counter()
        page_map: dict[tuple[str, str], set[str]] = defaultdict(set)

        org_blocklist = {organization_name.lower()} if organization_name else set()

        for page in pages:
            blob = " ".join([page.title] + page.headings + page.texts)
            for name in _ORG_TOKEN.findall(blob):
                if name.lower() in org_blocklist or name.lower() in SECTION_NOISE_LABELS:
                    continue
                key = ("organization", name)
                freq[key] += 1
                page_map[key].add(page.url)
            for name in _CURRENCY.findall(blob):
                key = ("currency", name.upper())
                freq[key] += 1
                page_map[key].add(page.url)

            for seg in page.path_segments[:1]:
                slug = seg.lower()
                if slug in ("branches", "branch"):
                    key = ("branch", seg)
                    freq[key] += 1
                    page_map[key].add(page.url)

        for name, count in metadata.aggregated_org_mentions.items():
            if organization_name and name.lower() == organization_name.lower():
                continue
            key = ("organization_mention", name)
            freq[key] += count
            for meta in metadata.pages:
                if name in meta.organization_mentions:
                    page_map[key].add(meta.url)

        for meta in metadata.pages:
            for name in meta.product_names:
                key = ("product", name)
                freq[key] += 2
                page_map[key].add(meta.url)
            for name in meta.service_names:
                key = ("service", name)
                freq[key] += 2
                page_map[key].add(meta.url)

        entities: list[ExtractedEntity] = []
        for (entity_type, name), count in freq.most_common(80):
            if count < 2 and entity_type not in ("currency",):
                continue
            pages_list = sorted(page_map[(entity_type, name)])[:20]
            confidence = min(0.98, 0.35 + count * 0.08)
            entities.append(
                ExtractedEntity(
                    name=name,
                    entity_type=entity_type,
                    aliases=[name.lower()] if name.lower() != name else [],
                    frequency=count,
                    pages=pages_list,
                    confidence=round(confidence, 3),
                )
            )
        return entities
