"""Deterministic text chunking service."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.content_signals import detect_content_type
from app.services.html_parser_service import ContentBlock


@dataclass
class TextChunk:
    index: int
    text: str


@dataclass
class EnrichedChunk:
    index: int
    text: str
    heading: str = ""
    content_type_hint: str = "generic"
    is_structured_block: bool = False


class ChunkingService:
    """Split cleaned text into overlapping, word-boundary-aware chunks."""

    def __init__(
        self, chunk_size: int = 800, chunk_overlap: int = 120, profile=None
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if chunk_overlap >= chunk_size:
            # Avoid an infinite loop; clamp overlap.
            chunk_overlap = chunk_size // 4
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.profile = profile

    def chunk(self, text: str) -> list[TextChunk]:
        """Split text into chunks of approx chunk_size characters with overlap.

        The splitter tries to break on whitespace boundaries so words are not
        cut in half, while remaining deterministic.
        """
        text = re.sub(r"\s+", " ", text or "").strip()
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [TextChunk(index=0, text=text)]

        chunks: list[TextChunk] = []
        start = 0
        index = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            # Try not to cut a word: walk back to the last space within window.
            if end < text_len:
                space = text.rfind(" ", start, end)
                if space != -1 and space > start:
                    end = space
            piece = text[start:end].strip()
            if piece:
                chunks.append(TextChunk(index=index, text=piece))
                index += 1
            if end >= text_len:
                break
            # Advance with overlap, but always make forward progress.
            next_start = end - self.chunk_overlap
            start = next_start if next_start > start else end

        return chunks

    def chunk_blocks(
        self, blocks: list[ContentBlock], page_title: str
    ) -> list[EnrichedChunk]:
        """Heading-aware chunking of structured page blocks.

        Each chunk is prefixed with the page title and section heading so both
        dense embeddings and lexical search "see" the section context. Short
        high-value blocks (rates, contacts, tariffs, schedule, FAQ) are kept as
        their own chunk; long blocks are split with the normal sliding window.
        """
        enriched: list[EnrichedChunk] = []
        index = 0
        page_title = (page_title or "").strip()
        for block in blocks:
            heading = block.heading.strip()
            prefix_parts = [p for p in (page_title, heading) if p]
            # Avoid repeating the title when it equals the heading.
            prefix = " — ".join(dict.fromkeys(prefix_parts))
            body = block.text.strip()
            if not body:
                continue

            if len(body) <= self.chunk_size:
                text = f"{prefix}\n{body}" if prefix else body
                enriched.append(
                    EnrichedChunk(
                        index=index,
                        text=text,
                        heading=heading,
                        content_type_hint=block.content_type_hint,
                        is_structured_block=block.is_structured_block,
                    )
                )
                index += 1
                continue

            for piece in self.chunk(body):
                text = f"{prefix}\n{piece.text}" if prefix else piece.text
                enriched.append(
                    EnrichedChunk(
                        index=index,
                        text=text,
                        heading=heading,
                        content_type_hint=block.content_type_hint,
                        is_structured_block=False,
                    )
                )
                index += 1
        return enriched

    def chunk_plain(self, text: str) -> list[EnrichedChunk]:
        """Plain chunking for non-HTML sources, with content-type detection."""
        hint = detect_content_type(text, profile=self.profile)
        out: list[EnrichedChunk] = []
        for piece in self.chunk(text):
            out.append(
                EnrichedChunk(
                    index=piece.index,
                    text=piece.text,
                    heading="",
                    content_type_hint=hint,
                    is_structured_block=False,
                )
            )
        return out
