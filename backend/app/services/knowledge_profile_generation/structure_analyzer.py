"""Stage 2 — website structure and page category detection."""
from __future__ import annotations

import re
from collections import Counter

from app.services.knowledge_profile_generation.models import (
    MetadataDataset,
    PageCategory,
    PageRecord,
    WebsiteHierarchy,
)

_CATEGORY_PATTERNS: list[tuple[str, list[str]]] = [
    ("homepage", ["", "index", "home", "main"]),
    ("about", ["about", "about-us", "company", "pro-nas", "about_us", "history"]),
    ("contacts", ["contact", "contacts", "kontakty", "contact-us", "support/contact"]),
    ("faq", ["faq", "questions", "help/faq", "pitaniya"]),
    ("news", ["news", "novyny", "blog", "press", "media"]),
    ("products", ["product", "products", "catalog", "shop", "store"]),
    ("services", ["service", "services", "poslugi"]),
    ("categories", ["category", "categories", "catalog", "katalog"]),
    ("support", ["support", "help", "dopomoga"]),
    ("branches", ["branch", "branches", "office", "offices", "vidilennya", "locations"]),
    ("rates", ["rate", "rates", "exchange", "currency", "kurs", "valyut"]),
    ("cards", ["card", "cards", "karty", "credit-card", "debit"]),
    ("loans", ["loan", "loans", "credit", "kredyt", "mortgage", "ipoteka"]),
    ("deposits", ["deposit", "deposits", "depozyt"]),
    ("documents", ["document", "documents", "docs", "download"]),
    ("privacy", ["privacy", "confidential", "konfidenc"]),
    ("terms", ["terms", "conditions", "legal", "umovy"]),
]

_TYPE_KEYWORDS: dict[str, list[str]] = {
    "bank_financial": [
        "bank", "банк", "credit", "кредит", "deposit", "депозит", "card", "картк",
        "exchange", "валют", "rates", "курс", "atm", "iban", "loan", "іпотек",
    ],
    "ecommerce": [
        "shop", "store", "product", "cart", "checkout", "delivery", "доставка",
        "товар", "магазин", "каталог", "catalog", "buy", "купити",
    ],
    "saas": [
        "pricing", "api", "sdk", "subscription", "platform", "saas", "integration",
        "документація", "docs", "developer",
    ],
    "documentation_portal": [
        "docs", "documentation", "api reference", "guide", "tutorial", "документація",
    ],
    "university": [
        "university", "університет", "faculty", "факультет", "student", "студент",
        "admission", "приймальна",
    ],
    "government": [
        "gov", "government", "municipality", "держав", "муніцип", "ordinance",
    ],
}


class WebsiteStructureAnalyzer:
    def analyze(
        self,
        pages: list[PageRecord],
        metadata: MetadataDataset,
    ) -> WebsiteHierarchy:
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
                menu_counter[seg] += 1

        preset_id, preset_conf, secondary = self._classify_site(pages, metadata)
        menu_links = [seg for seg, _ in menu_counter.most_common(25)]

        return WebsiteHierarchy(
            categories=categories,
            menu_links=menu_links,
            preset_seed=preset_id,
            preset_confidence=preset_conf,
            preset_secondary=secondary,
        )

    def _categorize_page(self, page: PageRecord) -> tuple[str, float, list[str]]:
        path = "/".join(page.path_segments).lower()
        title_l = page.title.lower()
        signals: list[str] = []
        best_cat = "general"
        best_score = 0.0

        if page.is_homepage:
            return "homepage", 0.95, ["is_homepage"]

        for cat, patterns in _CATEGORY_PATTERNS:
            score = 0
            for pat in patterns:
                if not pat:
                    continue
                if pat in path or pat in title_l:
                    score += 2
                    signals.append(f"path:{pat}")
                for seg in page.path_segments:
                    if seg == pat or pat in seg:
                        score += 1
                        signals.append(f"segment:{seg}")
            if score > best_score:
                best_score = score
                best_cat = cat

        if best_score == 0:
            if page.path_segments:
                best_cat = page.path_segments[0].replace("-", "_")
                best_score = 1
                signals.append(f"url_segment:{page.path_segments[0]}")
            else:
                best_cat = "general"
                best_score = 0.3

        confidence = min(0.98, 0.35 + best_score * 0.12)
        return best_cat, confidence, signals[:6]

    def _classify_site(
        self, pages: list[PageRecord], metadata: MetadataDataset
    ) -> tuple[str, float, str]:
        corpus_parts: list[str] = []
        for p in pages:
            corpus_parts.extend(p.path_segments)
            corpus_parts.append(p.title.lower())
            corpus_parts.extend(h.lower() for h in p.headings[:3])
        corpus = " ".join(corpus_parts).lower()
        scores = {
            preset: sum(1 for kw in kws if kw in corpus)
            for preset, kws in _TYPE_KEYWORDS.items()
        }
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        best_id, best_score = ranked[0]
        second_id, second_score = ranked[1] if len(ranked) > 1 else ("", 0)
        if best_score == 0:
            return "generic_corporate", 0.45, ""
        total = best_score + second_score + 1
        confidence = min(0.98, 0.4 + best_score / total)
        secondary = second_id if second_score >= best_score * 0.5 else ""
        return best_id, confidence, secondary
