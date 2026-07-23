"""Site statistics aggregation (Stage statistics)."""
from __future__ import annotations

from collections import Counter

from app.services.knowledge_profile_generation.models import (
    MetadataDataset,
    PageRecord,
    SiteStatistics,
)


class StatisticsBuilder:
    def build(
        self,
        pages: list[PageRecord],
        metadata: MetadataDataset,
        *,
        file_count: int = 0,
        chunk_count: int = 0,
    ) -> SiteStatistics:
        seg_counter: Counter[str] = Counter()
        doc_counter: Counter[str] = Counter()
        heading_counter: Counter[str] = Counter()
        currencies: list[str] = []

        for page in pages:
            doc_counter[page.document_type] += 1
            seg_counter.update(page.path_segments)
            for h in page.headings:
                heading_counter[h.lower()] += 1

        for meta in metadata.pages:
            if meta.currency:
                currencies.append(meta.currency)

        langs = [m.language for m in metadata.pages if m.language]
        lang_guess = Counter(langs).most_common(1)[0][0] if langs else "en"

        countries = [m.country for m in metadata.pages if m.country]
        country_guess = Counter(countries).most_common(1)[0][0] if countries else ""

        return SiteStatistics(
            indexed_page_count=len(pages),
            indexed_file_count=file_count,
            total_chunks=chunk_count,
            site_url=metadata.site_url,
            top_url_segments=[s for s, _ in seg_counter.most_common(30)],
            document_type_counts=dict(doc_counter),
            heading_counts=dict(heading_counter.most_common(100)),
            language_guess=lang_guess,
            country_guess=country_guess,
            currency_mentions=sorted(set(currencies))[:10],
        )
