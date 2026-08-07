"""Stage 1 — deterministic website metadata extraction from indexed content."""
from __future__ import annotations

import json
import re
from collections import Counter

from app.services.knowledge_profile_generation.models import (
    MetadataDataset,
    PageMetadata,
    PageRecord,
)

from app.services.knowledge_profile_generation.structural_filters import (
    is_section_noise_label,
)

_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?(?:\(\d{2,4}\)[\s\-]?)?\d{2,4}[\s\-]?\d{2,4}[\s\-]?\d{2,4}(?:[\s\-]?\d{2,4})?"
)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_COPYRIGHT_RE = re.compile(
    r"(?:©|copyright|\(c\))\s*([^\n\r|]{3,80})",
    re.IGNORECASE,
)
_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_OG_SITE_RE = re.compile(
    r'property=["\']og:site_name["\'][^>]*content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_SCHEMA_ORG_NAME_RE = re.compile(
    r'"@type"\s*:\s*"(?:Organization|Corporation|LocalBusiness)"[^}]*"name"\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)
_CURRENCY_RE = re.compile(r"\b(USD|EUR|UAH|GBP|CHF|PLN|JPY|CNY)\b")
_ORG_CANDIDATE_RE = re.compile(
    r"\b([A-ZА-ЯІЇЄ][A-ZА-ЯІЇЄ0-9\-]{2,}(?:\s+[A-ZА-ЯІЇЄ][A-ZА-ЯІЇЄ0-9\-]{2,}){0,3})\b"
)


class WebsiteMetadataExtractor:
    def extract(self, pages: list[PageRecord], site_url: str = "") -> MetadataDataset:
        meta_pages: list[PageMetadata] = []
        org_counter: Counter[str] = Counter()
        all_phones: list[str] = []
        all_emails: list[str] = []

        for page in pages:
            full_text = "\n".join(page.texts)
            raw_join = "\n".join([page.title] + page.headings + page.texts)

            h1 = page.headings[0] if page.headings else ""
            h2_list = page.headings[1:6] if len(page.headings) > 1 else []

            meta = PageMetadata(
                url=page.url,
                title=page.title,
                meta_title=page.title,
                h1=h1 or page.title.split("|")[0].split("-")[0].strip(),
                h2_list=h2_list,
                breadcrumbs=page.path_segments,
                canonical_url=page.url,
                path_segments=page.path_segments,
                navigation_labels=self._nav_labels(page),
                phones=sorted(set(_PHONE_RE.findall(full_text)))[:5],
                emails=sorted(set(_EMAIL_RE.findall(full_text)))[:5],
                copyright_lines=_COPYRIGHT_RE.findall(full_text)[:3],
                footer_text=self._footer_snippet(full_text),
                organization_mentions=self._org_mentions(full_text),
                product_names=[],
                service_names=[],
                branch_mentions=self._section_mentions(page, "branches"),
                atm_mentions=self._section_mentions(page, "atm"),
                language="",
                currency=self._guess_currency(full_text),
            )

            meta.meta_description = self._first_sentence(full_text, 240)
            meta.schema_org_names = _SCHEMA_ORG_NAME_RE.findall(raw_join)
            meta.json_ld_names = self._json_ld_names(raw_join)
            meta.og_site_name = (_OG_SITE_RE.search(raw_join) or [None, ""])[1]

            for name in (
                meta.schema_org_names
                + meta.json_ld_names
                + ([meta.og_site_name] if meta.og_site_name else [])
                + meta.organization_mentions
            ):
                clean = self._clean_org_name(name)
                if clean:
                    org_counter[clean] += 1

            all_phones.extend(meta.phones)
            all_emails.extend(meta.emails)
            meta_pages.append(meta)

        return MetadataDataset(
            pages=meta_pages,
            site_url=site_url,
            aggregated_phones=sorted(set(all_phones))[:20],
            aggregated_emails=sorted(set(all_emails))[:20],
            aggregated_org_mentions=dict(org_counter.most_common(50)),
        )

    def _nav_labels(self, page: PageRecord) -> list[str]:
        labels: list[str] = []
        for seg in page.path_segments:
            label = seg.replace("-", " ").replace("_", " ").strip()
            if len(label) >= 3:
                labels.append(label.title())
        return labels[:12]

    def _footer_snippet(self, text: str) -> str:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return ""
        return "\n".join(lines[-8:])[:800]

    def _org_mentions(self, text: str) -> list[str]:
        found: list[str] = []
        for m in _ORG_CANDIDATE_RE.findall(text):
            if is_section_noise_label(m):
                continue
            if len(m) >= 4 and m not in found:
                found.append(m)
            if len(found) >= 10:
                break
        return found

    def _section_mentions(self, page: PageRecord, needle: str) -> list[str]:
        segs = [s.lower() for s in page.path_segments]
        if any(needle in s or s in needle for s in segs):
            return [needle]
        return []

    def _json_ld_names(self, raw: str) -> list[str]:
        names: list[str] = []
        for block in _JSON_LD_RE.findall(raw):
            try:
                data = json.loads(block.strip())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict):
                        if item.get("@type") in (
                            "Organization",
                            "Corporation",
                            "LocalBusiness",
                        ):
                            n = item.get("name")
                            if isinstance(n, str) and n.strip():
                                names.append(n.strip())
            except (json.JSONDecodeError, TypeError):
                continue
        return names[:10]

    def _guess_currency(self, text: str) -> str:
        m = _CURRENCY_RE.search(text)
        return m.group(0).upper() if m else ""

    def _first_sentence(self, text: str, max_len: int) -> str:
        raw = " ".join(text.split())
        if not raw:
            return ""
        for sep in (". ", "! ", "? "):
            if sep in raw:
                raw = raw.split(sep, 1)[0]
                break
        return raw[:max_len]

    def _clean_org_name(self, name: str) -> str:
        clean = re.sub(r"\s+", " ", (name or "").strip())
        if len(clean) < 3 or is_section_noise_label(clean):
            return ""
        return clean[:80]
