"""Document quality estimation for retrieval ranking."""
from __future__ import annotations

import re

from app.services.retrieval_engine.types import DocumentQualityMetrics

_NAV_PATTERNS = re.compile(
    r"\b(menu|navigation|footer|breadcrumb|sidebar|cookie|privacy policy|"
    r"terms of use|all rights reserved|©)\b",
    re.I,
)
_TEMPLATE_PATTERNS = re.compile(
    r"\b(click here|read more|learn more|subscribe|sign up|log in)\b",
    re.I,
)


class DocumentQualityService:
    @staticmethod
    def estimate(
        *,
        text: str,
        title: str = "",
        heading: str = "",
        boilerplate_ratio: float = 0.0,
        main_content_chars: int = 0,
    ) -> DocumentQualityMetrics:
        body = (text or "").strip()
        content_length = main_content_chars or len(body)
        if not body and not title:
            return DocumentQualityMetrics(quality_score=0.0)

        words = body.split()
        word_count = max(1, len(words))
        nav_hits = len(_NAV_PATTERNS.findall(body))
        template_hits = len(_TEMPLATE_PATTERNS.findall(body))
        short_line_ratio = sum(1 for line in body.splitlines() if len(line.strip()) < 40) / max(
            1, len(body.splitlines())
        )

        navigation_ratio = min(1.0, nav_hits / max(1, word_count / 50))
        template_ratio = min(1.0, template_hits / max(1, word_count / 80))
        nav_line_penalty = short_line_ratio * 0.3

        unique_words = len(set(w.lower() for w in words if len(w) > 2))
        information_density = unique_words / word_count

        duplicate_ratio = 0.0
        if word_count > 20:
            seen: set[str] = set()
            dup = 0
            for w in words:
                wl = w.lower()
                if wl in seen:
                    dup += 1
                seen.add(wl)
            duplicate_ratio = dup / word_count

        bp = float(boilerplate_ratio or 0.0)
        penalty = (
            bp * 0.35
            + navigation_ratio * 0.25
            + template_ratio * 0.15
            + nav_line_penalty * 0.15
            + duplicate_ratio * 0.10
        )
        quality_score = max(0.05, 1.0 - min(0.95, penalty))

        if information_density < 0.25 and content_length > 200:
            quality_score *= 0.85

        return DocumentQualityMetrics(
            content_length=content_length,
            information_density=information_density,
            boilerplate_ratio=bp,
            navigation_ratio=navigation_ratio,
            template_ratio=template_ratio,
            duplicate_ratio=duplicate_ratio,
            quality_score=quality_score,
        )

    @staticmethod
    def ranking_penalty(metrics: DocumentQualityMetrics) -> float:
        """Penalty to subtract from final score (0..0.4)."""
        if metrics.boilerplate_ratio >= 0.55:
            return 0.25 * metrics.boilerplate_ratio
        if metrics.navigation_ratio >= 0.4:
            return 0.20
        if metrics.quality_score < 0.35:
            return 0.18
        return max(0.0, (1.0 - metrics.quality_score) * 0.12)
