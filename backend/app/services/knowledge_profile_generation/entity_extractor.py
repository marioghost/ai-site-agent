"""Stage 4 — entity extraction from metadata and page content."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from app.services.knowledge_profile_generation.models import (
    ExtractedEntity,
    MetadataDataset,
    PageRecord,
)

_ENTITY_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "organization": [
        re.compile(r"\b([A-ZА-ЯІЇЄ][A-ZА-ЯІЇЄ0-9\-]{2,})\b"),
    ],
    "product": [
        re.compile(r"\b(credit card|debit card|premium card|кредитн\w*\s+карт\w*)\b", re.I),
        re.compile(r"\b(mortgage loan|auto loan|споживч\w*\s+кредит)\b", re.I),
    ],
    "service": [
        re.compile(r"\b(internet banking|mobile banking|online banking)\b", re.I),
        re.compile(r"\b(payment system|apple pay|google pay)\b", re.I),
    ],
    "currency": [re.compile(r"\b(USD|EUR|UAH|GBP|CHF|PLN)\b")],
    "country": [re.compile(r"\b(Ukraine|Україна|USA|Poland)\b", re.I)],
    "city": [re.compile(r"\b(Kyiv|Kiev|Kharkiv|Lviv|Odesa|Дніпро)\b", re.I)],
    "branch": [re.compile(r"\b(branch office|відділен\w*)\b", re.I)],
    "atm": [re.compile(r"\b(ATM|банкомат\w*)\b", re.I)],
    "card_type": [re.compile(r"\b(visa|mastercard|mc|unionpay)\b", re.I)],
    "loan_type": [re.compile(r"\b(mortgage|consumer loan|auto loan|іпотек\w*)\b", re.I)],
    "deposit_type": [re.compile(r"\b(term deposit|savings deposit|депозит\w*)\b", re.I)],
}


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
            for entity_type, patterns in _ENTITY_PATTERNS.items():
                for pat in patterns:
                    for match in pat.findall(blob):
                        name = match if isinstance(match, str) else match[0]
                        name = re.sub(r"\s+", " ", name).strip()
                        if len(name) < 2:
                            continue
                        if entity_type == "organization":
                            if name.lower() in org_blocklist:
                                continue
                            if name.lower() in {"branch", "branches", "atm", "atms"}:
                                continue
                        key = (entity_type, name)
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
            if count < 2 and entity_type not in ("currency", "country", "city"):
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
