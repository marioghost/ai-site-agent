"""HTML parsing and cleanup, plus link/file discovery.

Extraction splits main content from navigation/footer/header boilerplate.
Only main-content blocks feed chunking and embeddings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString, Tag

from app.core.logging import get_logger
from app.services.content_signals import detect_content_type, is_homepage_url
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.text_cleaner_service import TextCleanerService
from app.utils.url_utils import detect_file_type, resolve_url

logger = get_logger(__name__)

_STRIP_TAGS = ["script", "style", "noscript", "template", "svg", "iframe"]
_CHROME_TAGS = ["nav", "footer", "header", "aside"]
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_SHORT_BLOCK_CHARS = 400
_MAIN_ID_CLASS = re.compile(r"(^|[-_])(main|content|primary)([-_]|$)", re.I)


@dataclass
class ContentBlock:
    heading: str
    text: str
    content_type_hint: str = "generic"
    is_structured_block: bool = False


@dataclass
class ParsedPage:
    title: str
    text: str
    main_content_text: str = ""
    navigation_text: str = ""
    footer_text: str = ""
    header_text: str = ""
    boilerplate_text: str = ""
    links: list[str] = field(default_factory=list)
    file_links: list[tuple[str, str]] = field(default_factory=list)
    blocks: list[ContentBlock] = field(default_factory=list)
    is_homepage: bool = False


class HtmlParserService:
    def __init__(self, profile=None) -> None:
        self.profile = profile
        self.cleaner = TextCleanerService()

    @staticmethod
    def _tag_attr(el, key: str, default="") -> str:
        if not isinstance(el, Tag):
            return default
        attrs = getattr(el, "attrs", None)
        if not attrs:
            return default
        value = attrs.get(key, default)
        if value is None:
            return default
        if isinstance(value, list):
            return " ".join(str(v) for v in value if v)
        return str(value)

    @staticmethod
    def _tag_classes(el) -> str:
        return HtmlParserService._tag_attr(el, "class", "").lower()

    @staticmethod
    def _sanitize_broken_tags(soup) -> None:
        """Drop malformed tags (attrs=None) that crash BeautifulSoup/css selectors."""
        for el in list(soup.find_all(True)):
            if isinstance(el, Tag) and getattr(el, "attrs", None) is None:
                el.decompose()

    def parse(self, html: str, base_url: str) -> ParsedPage:
        soup = BeautifulSoup(html, "lxml")
        self._sanitize_broken_tags(soup)

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        links, file_links = self._extract_links(soup, base_url)

        navigation_text = self._collect_region_text(soup.find_all("nav"))
        footer_text = self._collect_region_text(soup.find_all("footer"))
        header_text = self._collect_region_text(soup.find_all("header"))
        aside_text = self._collect_region_text(soup.find_all("aside"))
        boilerplate_text = self.cleaner.clean(
            " ".join(p for p in (navigation_text, footer_text, header_text, aside_text) if p)
        )

        for tag_name in _STRIP_TAGS + _CHROME_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        self._strip_noise(soup)

        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
        title = title or base_url

        main_root = self._find_main_root(soup)
        self._flatten_tables(main_root)

        blocks = self._extract_blocks(main_root, page_url=base_url, page_title=title)
        main_content_text = "\n\n".join(
            (f"{b.heading}\n{b.text}" if b.heading else b.text) for b in blocks
        ).strip()
        if not main_content_text:
            main_content_text = self.cleaner.clean(main_root.get_text(separator="\n"))

        return ParsedPage(
            title=title,
            text=main_content_text,
            main_content_text=main_content_text,
            navigation_text=navigation_text,
            footer_text=footer_text,
            header_text=header_text,
            boilerplate_text=boilerplate_text,
            links=links,
            file_links=file_links,
            blocks=blocks,
            is_homepage=is_homepage_url(base_url),
        )

    @staticmethod
    def _collect_region_text(tags: list[Tag]) -> str:
        parts: list[str] = []
        for tag in tags:
            text = tag.get_text(" ", strip=True)
            if text:
                parts.append(text)
        return " ".join(parts)

    @staticmethod
    def _find_main_root(soup: BeautifulSoup):
        for selector in (
            lambda s: s.find("main"),
            lambda s: s.find(attrs={"role": "main"}),
            lambda s: s.find("article"),
        ):
            node = selector(soup)
            if node is not None:
                return node
        for el in soup.find_all(id=True):
            el_id = HtmlParserService._tag_attr(el, "id")
            if el_id and _MAIN_ID_CLASS.search(el_id):
                return el
        for el in soup.find_all(class_=True):
            classes = HtmlParserService._tag_classes(el)
            if classes and _MAIN_ID_CLASS.search(classes):
                return el
        return soup.body or soup

    def _extract_blocks(
        self, root, *, page_url: str = "", page_title: str = ""
    ) -> list[ContentBlock]:
        sections: list[tuple[str, list[str]]] = [("", [])]
        for node in root.descendants:
            name = getattr(node, "name", None)
            if name in _HEADING_TAGS:
                heading_text = node.get_text(" ", strip=True)
                if heading_text:
                    sections.append((heading_text, []))
                continue
            if isinstance(node, NavigableString):
                if self._inside_heading(node):
                    continue
                piece = str(node).strip()
                if piece:
                    sections[-1][1].append(piece)

        page_hint = "generic"
        if self.profile is not None:
            page_hint = KnowledgeProfileService.match_content_hint(
                self.profile, page_url, page_title
            )

        blocks: list[ContentBlock] = []
        for heading, parts in sections:
            body = self.cleaner.clean(" ".join(parts))
            if not body and not heading:
                continue
            if not body:
                continue
            hint = detect_content_type(heading, body, profile=self.profile)
            if hint == "generic" and page_hint != "generic":
                hint = page_hint
            is_structured = bool(
                (heading and len(body) <= _SHORT_BLOCK_CHARS) or hint != "generic"
            )
            blocks.append(
                ContentBlock(
                    heading=heading,
                    text=body,
                    content_type_hint=hint,
                    is_structured_block=is_structured,
                )
            )
        return blocks

    @staticmethod
    def _inside_heading(node) -> bool:
        for parent in node.parents:
            if getattr(parent, "name", None) in _HEADING_TAGS:
                return True
        return False

    def _flatten_tables(self, root) -> None:
        for table in root.find_all("table"):
            flat = self._flatten_table(table)
            table.replace_with(NavigableString(flat) if flat else NavigableString(""))

    @staticmethod
    def _flatten_table(table) -> str:
        caption_el = table.find("caption")
        caption = caption_el.get_text(" ", strip=True) if caption_el else ""
        rows: list[str] = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            if cells:
                rows.append(" | ".join(cells))
        if not rows:
            return caption
        body = " ; ".join(rows)
        return f"{caption}: {body}" if caption else body

    @staticmethod
    def _strip_noise(soup) -> None:
        for el in soup.select('[hidden], [aria-hidden="true"]'):
            el.decompose()
        for el in soup.find_all(class_=True):
            classes = HtmlParserService._tag_classes(el)
            if classes and any(
                k in classes for k in ("cookie", "consent", "banner", "breadcrumb", "menu")
            ):
                el.decompose()
        for el in soup.find_all(id=True):
            el_id = HtmlParserService._tag_attr(el, "id").lower()
            if el_id and any(
                k in el_id for k in ("cookie", "consent", "banner", "breadcrumb")
            ):
                el.decompose()

    def _extract_links(
        self, soup: BeautifulSoup, base_url: str
    ) -> tuple[list[str], list[tuple[str, str]]]:
        page_links: set[str] = set()
        file_links: dict[str, str] = {}
        for a in soup.find_all("a", href=True):
            resolved = resolve_url(base_url, a["href"])
            if not resolved:
                continue
            file_type = detect_file_type(resolved)
            if file_type and file_type != "html":
                file_links[resolved] = file_type
            else:
                page_links.add(resolved)
        return list(page_links), list(file_links.items())
