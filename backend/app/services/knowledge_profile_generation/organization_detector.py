"""Stage 3 — deterministic organization detection with evidence."""
from __future__ import annotations

import re
from collections import Counter

from app.services.knowledge_profile_generation.models import (
    DetectedOrganization,
    EvidenceItem,
    MetadataDataset,
    PageRecord,
    WebsiteHierarchy,
)
from app.services.knowledge_profile_generation.confidence_engine import ConfidenceEngine
from app.services.knowledge_profile_generation.structural_filters import (
    is_section_noise_label,
)

_BRANCH_ATM_NOISE = re.compile(
    r"\b(branches?\s+and\s+atms?|atm\s+locator)\b",
    re.IGNORECASE,
)


class OrganizationDetector:
    def __init__(self) -> None:
        self.confidence = ConfidenceEngine()

    def detect(
        self,
        metadata: MetadataDataset,
        pages: list[PageRecord],
        hierarchy: WebsiteHierarchy,
    ) -> DetectedOrganization:
        candidates: dict[str, list[EvidenceItem]] = {}

        def add(name: str, source: str, weight: float, detail: str = "") -> None:
            clean = self._clean_name(name)
            if not clean:
                return
            candidates.setdefault(clean, []).append(
                EvidenceItem(source=source, weight=weight, detail=detail)
            )

        for meta in metadata.pages:
            for name in meta.schema_org_names:
                add(name, "schema.org", 40, meta.url)
            for name in meta.json_ld_names:
                add(name, "json_ld", 40, meta.url)
            if meta.og_site_name:
                add(meta.og_site_name, "og_site_name", 25, meta.url)
            if meta.h1 and len(meta.h1) <= 60:
                add(meta.h1.split("|")[0].strip(), "header_h1", 15, meta.url)
            for line in meta.copyright_lines:
                add(line, "footer_copyright", 20, meta.url)
            if meta.footer_text:
                for m in re.findall(r"©\s*([^\n\r|]{3,60})", meta.footer_text, re.I):
                    add(m, "footer", 20, meta.url)

        about_urls = {c.url for c in hierarchy.categories if c.category == "about"}
        contact_urls = {c.url for c in hierarchy.categories if c.category == "contacts"}
        homepage_urls = {c.url for c in hierarchy.categories if c.category == "homepage"}

        for page in pages:
            title_part = re.split(r"[|\-–—]", page.title)[0].strip()
            if page.is_homepage or page.url in homepage_urls:
                add(title_part, "homepage", 15, page.url)
            if page.url in about_urls:
                add(title_part, "about_page", 10, page.url)
                for h in page.headings[:2]:
                    add(h, "about_page", 8, page.url)
            if page.url in contact_urls:
                add(title_part, "contact_page", 8, page.url)

        for name, count in metadata.aggregated_org_mentions.items():
            freq_weight = min(15.0, count * 0.5)
            add(name, "frequency", freq_weight, f"{count} mentions")

        if not candidates:
            fallback = self._hostname_fallback(metadata.site_url)
            return DetectedOrganization(
                name=fallback or "Organization",
                confidence=0.35,
                evidence=[EvidenceItem(source="hostname", weight=10, detail=metadata.site_url)],
                aliases=[],
            )

        scored: list[tuple[str, float, list[EvidenceItem]]] = []
        for name, evidence in candidates.items():
            score = self.confidence.organization_score(evidence)
            scored.append((name, score, evidence))

        scored.sort(key=lambda x: (-x[1], len(x[0])))
        best_name, best_conf, best_evidence = scored[0]

        # Prefer canonical uppercase brand when variants tie (e.g. UKRSIBBANK vs mixed case)
        for name, conf, evidence in scored[:5]:
            if name.upper() == name and len(name) >= 4 and conf >= best_conf * 0.85:
                best_name, best_conf, best_evidence = name, conf, evidence
                break

        aliases = self._build_aliases(best_name, scored[1:4])
        return DetectedOrganization(
            name=best_name,
            confidence=round(min(0.99, best_conf), 3),
            evidence=self._dedupe_evidence(best_evidence),
            aliases=aliases,
        )

    def _clean_name(self, name: str) -> str:
        n = re.sub(r"\s+", " ", name).strip(" .,;|©")
        n = re.sub(r"\s+\d{4}\.?\s*.*$", "", n, flags=re.I).strip()
        n = re.sub(r"\s+all rights reserved.*$", "", n, flags=re.I).strip()
        if _BRANCH_ATM_NOISE.search(n):
            return ""
        if len(n) < 3 or len(n) > 80:
            return ""
        lower = n.lower()
        if lower in {"home", "welcome", "main", "index", "about us", "contacts"}:
            return ""
        if is_section_noise_label(n):
            return ""
        return n

    def _hostname_fallback(self, site_url: str) -> str:
        if not site_url:
            return ""
        from urllib.parse import urlparse

        host = urlparse(site_url).netloc.replace("www.", "")
        part = host.split(".")[0]
        return part.upper() if part else ""

    def _build_aliases(
        self, primary: str, alternates: list[tuple[str, float, list[EvidenceItem]]]
    ) -> list[str]:
        aliases: list[str] = []
        for variant in {primary, primary.upper(), primary.lower(), primary.title()}:
            if variant and variant not in aliases:
                aliases.append(variant)
        for alt_name, conf, _ in alternates:
            if conf >= 0.45 and alt_name.lower() != primary.lower():
                if alt_name not in aliases:
                    aliases.append(alt_name)
        return aliases[:8]

    def _dedupe_evidence(self, items: list[EvidenceItem]) -> list[EvidenceItem]:
        seen: set[str] = set()
        out: list[EvidenceItem] = []
        for item in sorted(items, key=lambda x: -x.weight):
            key = f"{item.source}:{item.detail[:40]}"
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out[:12]
