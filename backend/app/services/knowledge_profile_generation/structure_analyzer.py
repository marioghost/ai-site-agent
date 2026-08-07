"""Stage 2 — website structure from URL hierarchy (no industry catalogs)."""
from __future__ import annotations

from collections import Counter

from app.services.knowledge_profile_generation.models import (
    MetadataDataset,
    PageCategory,
    PageRecord,
    WebsiteHierarchy,
)
from app.services.knowledge_profile_generation.structural_filters import (
    first_meaningful_path_segment,
    is_locale_like_path_segment,
)

# Universal Latin URL stems only — no language/industry vocabularies.
_STRUCTURAL_ALIASES: dict[str, str] = {
    "index": "homepage",
    "home": "homepage",
    "main": "homepage",
    "about-us": "about",
    "about_us": "about",
    "contact-us": "contacts",
    "contact": "contacts",
    "contacts": "contacts",
    "faq": "faq",
    "help": "support",
    "support": "support",
    "news": "news",
    "blog": "news",
    "press": "news",
    "privacy": "privacy",
    "terms": "terms",
    "legal": "terms",
    "docs": "documents",
    "documents": "documents",
    "download": "documents",
}


class WebsiteStructureAnalyzer:
    def analyze(
        self,
        pages: list[PageRecord],
        metadata: MetadataDataset,
    ) -> WebsiteHierarchy:
        del metadata  # reserved for future structural signals
        categories: list[PageCategory] = []
        menu_counter: Counter[str] = Counter()

        for page in pages:
            cat, conf, signals = self._categorize_page(page)
            categories.append(
                PageCategory(
                    category=cat,
                    url=page.url,
                    title=page.title,
                    confidence=conf,
                    signals=signals,
                )
            )
            for seg in page.path_segments[:2]:
                if seg and not is_locale_like_path_segment(seg):
                    menu_counter[seg] += 1

        menu_links = [seg for seg, _ in menu_counter.most_common(25)]
        # Assembler never seeds industry PRESETS; keep a stable structural label.
        return WebsiteHierarchy(
            categories=categories,
            menu_links=menu_links,
            preset_seed="generic_corporate",
            preset_confidence=0.9 if pages else 0.45,
            preset_secondary="",
        )

    def _categorize_page(self, page: PageRecord) -> tuple[str, float, list[str]]:
        if page.is_homepage:
            return "homepage", 0.95, ["is_homepage"]

        seg = first_meaningful_path_segment(list(page.path_segments or []))
        if not seg:
            return "general", 0.3, ["no_path_segment"]

        key = seg.lower().replace("_", "-")
        cat = _STRUCTURAL_ALIASES.get(key, key.replace("-", "_"))
        if is_locale_like_path_segment(cat):
            return "general", 0.3, [f"locale_segment:{seg}"]
        return cat, 0.7, [f"url_segment:{seg}"]
