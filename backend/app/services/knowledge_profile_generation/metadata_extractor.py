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
_META_DESC_RE = re.compile(
    r'name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_SCHEMA_ORG_NAME_RE = re.compile(
    r'"@type"\s*:\s*"(?:Organization|Bank|Corporation|FinancialService)"[^}]*"name"\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)
_CURRENCY_RE = re.compile(
    r"\b(USD|EUR|UAH|GBP|CHF|PLN|JPY|CNY)\b|\b(долар|євро|гривн)\w*\b",
    re.IGNORECASE,
)
_ORG_CANDIDATE_RE = re.compile(
    r"\b([A-ZА-ЯІЇЄ][A-ZА-ЯІЇЄ0-9\-]{2,}(?:\s+[A-ZА-ЯІЇЄ][A-ZА-ЯІЇЄ0-9\-]{2,}){0,3})\b"
)
_BRANCH_ATM_NOISE = re.compile(
    r"\b(branches?\s+and\s+atms?|відділен\w*|банкомат\w*|atm\s+locator)\b",
    re.IGNORECASE,
)
_PRODUCT_SERVICE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("product", re.compile(r"\b(credit card|дебетов\w*\s+карт\w*|кредитн\w*\s+карт\w*)\b", re.I)),
    ("service", re.compile(r"\b(internet banking|online banking|мобільн\w*\s+банк\w*)\b", re.I)),
    ("loan", re.compile(r"\b(mortgage|кредит|loan|іпотек\w*)\b", re.I)),
    ("deposit", re.compile(r"\b(deposit|депозит\w*)\b", re.I)),
    ("rate", re.compile(r"\b(exchange rate|курс\w*\s+валют|currency rate)\b", re.I)),
]


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
                product_names=self._named_matches(full_text, "product"),
                service_names=self._named_matches(full_text, "service"),
                branch_mentions=self._find_branch_atm(full_text, "branch"),
                atm_mentions=self._find_branch_atm(full_text, "atm"),
                language=self._guess_language(full_text),
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
        tail = lines[-8:]
        return "\n".join(tail)[:800]

    def _org_mentions(self, text: str) -> list[str]:
        found: list[str] = []
        for m in _ORG_CANDIDATE_RE.findall(text):
            if _BRANCH_ATM_NOISE.search(m):
                continue
            if len(m) >= 4 and m not in found:
                found.append(m)
            if len(found) >= 10:
                break
        return found

    def _named_matches(self, text: str, kind: str) -> list[str]:
        names: list[str] = []
        for label, pat in _PRODUCT_SERVICE_PATTERNS:
            if label != kind and kind not in (label,):
                continue
            for m in pat.findall(text):
                val = m if isinstance(m, str) else m[0]
                if val and val not in names:
                    names.append(val.strip())
        return names[:10]

    def _find_branch_atm(self, text: str, kind: str) -> list[str]:
        pat = re.compile(
            r"\b(branches?\s+and\s+atms?|відділен\w*|банкомат\w*)\b" if kind == "branch"
            else r"\b(atm|банкомат\w*)\b",
            re.IGNORECASE,
        )
        return list(dict.fromkeys(pat.findall(text)))[:5]

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
                            "Bank",
                            "Corporation",
                            "FinancialService",
                        ):
                            n = item.get("name")
                            if isinstance(n, str) and n.strip():
                                names.append(n.strip())
            except json.JSONDecodeError:
                continue
        return names

    def _guess_language(self, text: str) -> str:
        sample = text[:2000].lower()
        uk = sum(sample.count(c) for c in "іїєґ")
        if uk >= 3:
            return "uk"
        if re.search(r"[а-яА-Я]", sample):
            return "ru"
        return "en"

    def _guess_currency(self, text: str) -> str:
        m = _CURRENCY_RE.search(text)
        return m.group(0).upper() if m else ""

    def _first_sentence(self, text: str, limit: int) -> str:
        clean = re.sub(r"\s+", " ", text).strip()
        return clean[:limit]

    def _clean_org_name(self, name: str) -> str:
        n = re.sub(r"\s+", " ", name).strip(" .,;|")
        if _BRANCH_ATM_NOISE.search(n):
            return ""
        if len(n) < 3 or len(n) > 80:
            return ""
        return n
