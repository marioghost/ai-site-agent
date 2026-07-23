"""Build LLM context grouped by page with merged neighbouring chunks."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.settings import Settings
from app.services.language_resolver_service import language_match_score, normalize_url_for_lang_dedupe
from app.services.qdrant_service import SearchHit
from app.utils.hashing import content_hash


@dataclass
class PageContextBlock:
    source_id: int
    title: str
    url: str
    chunks_used: int
    text: str
    score: float
    content_categories: list[str] = field(default_factory=list)
    document_type: str = "generic_page"
    page_role: str = "generic"
    source_summary: str = ""


@dataclass
class BuiltContext:
    blocks: list[PageContextBlock]
    prompt_text: str
    total_chunks: int
    page_count: int


class ContextBuilderService:
    def build(
        self,
        hits: list[SearchHit],
        *,
        max_pages: int = 3,
        max_chunks_per_page: int = 2,
        merge_neighbours: bool = True,
        max_chars_per_source: int = 1200,
        max_total_context_chars: int = 5000,
        settings: Settings | None = None,
    ) -> BuiltContext:
        if settings is not None:
            max_pages = int(getattr(settings, "max_sources_in_prompt", max_pages) or max_pages)
            max_pages = min(max_pages, int(getattr(settings, "max_pages_in_context", max_pages) or max_pages))
            max_chunks_per_page = int(
                getattr(settings, "max_chunks_per_page", max_chunks_per_page) or max_chunks_per_page
            )
            max_chars_per_source = int(
                getattr(settings, "max_chars_per_source", max_chars_per_source) or max_chars_per_source
            )
            max_total_context_chars = int(
                getattr(settings, "max_total_context_chars", max_total_context_chars)
                or max_total_context_chars
            )

        if not hits:
            return BuiltContext(blocks=[], prompt_text="", total_chunks=0, page_count=0)

        by_source: dict[int, list[SearchHit]] = {}
        for hit in hits:
            by_source.setdefault(hit.source_id, []).append(hit)

        page_scores: list[tuple[int, float]] = []
        for sid, group in by_source.items():
            best = max(h.final_score or h.score for h in group)
            page_scores.append((sid, best))
        page_scores.sort(key=lambda x: -x[1])

        blocks: list[PageContextBlock] = []
        total_chunks = 0

        for sid, page_score in page_scores[: max(1, max_pages)]:
            group = sorted(by_source[sid], key=lambda h: h.chunk_index)
            selected = group[: max(1, max_chunks_per_page)]
            if merge_neighbours:
                selected = self._merge_neighbouring(selected)
            merged_text = self._merge_text(selected)
            merged_text = merged_text[:max_chars_per_source]
            categories = sorted(
                {getattr(h, "content_category", "generic") or "generic" for h in selected}
            )
            rep = selected[0]
            blocks.append(
                PageContextBlock(
                    source_id=sid,
                    title=rep.title or rep.url,
                    url=rep.url,
                    chunks_used=len(selected),
                    text=merged_text,
                    score=page_score,
                    content_categories=categories,
                    document_type=getattr(rep, "document_type", "generic_page") or "generic_page",
                    page_role=getattr(rep, "page_role", "generic") or "generic",
                    source_summary=getattr(rep, "source_profile_summary", "") or "",
                )
            )
            total_chunks += len(selected)

        prompt_parts: list[str] = []
        total_chars = 0
        for i, block in enumerate(blocks, start=1):
            header = (
                f"Source {i}:\n"
                f"Title: {block.title}\n"
                f"URL: {block.url}"
            )
            if block.document_type and block.document_type != "generic_page":
                header += f"\nType: {block.document_type}"
            piece = f"{header}\nSnippet:\n{block.text}"
            if total_chars + len(piece) > max_total_context_chars:
                remaining = max(0, max_total_context_chars - total_chars - len(header) - 12)
                if remaining <= 0:
                    break
                piece = f"{header}\nSnippet:\n{block.text[:remaining]}"
            prompt_parts.append(piece)
            total_chars += len(piece)
            if total_chars >= max_total_context_chars:
                break

        return BuiltContext(
            blocks=blocks,
            prompt_text="\n\n---\n\n".join(prompt_parts),
            total_chunks=total_chunks,
            page_count=len(blocks),
        )

    @staticmethod
    def _merge_neighbouring(hits: list[SearchHit]) -> list[SearchHit]:
        if len(hits) <= 1:
            return hits
        merged: list[SearchHit] = [hits[0]]
        for hit in hits[1:]:
            prev = merged[-1]
            if hit.chunk_index == prev.chunk_index + 1:
                prev.text = f"{prev.text}\n\n{hit.text}".strip()
                prev.final_score = max(prev.final_score, hit.final_score)
                prev.score = max(prev.score, hit.score)
            else:
                merged.append(hit)
        return merged

    @staticmethod
    def _merge_text(hits: list[SearchHit]) -> str:
        parts: list[str] = []
        seen: set[str] = set()
        for hit in hits:
            heading = (hit.heading or "").strip()
            body = (hit.text or "").strip()
            if heading:
                segment = f"## {heading}\n{body}" if body else f"## {heading}"
            else:
                segment = body
            h = content_hash(segment)
            if h in seen:
                continue
            seen.add(h)
            if segment:
                parts.append(segment)
        return "\n\n".join(parts)

    @staticmethod
    def flatten_hits(blocks: list[PageContextBlock], original: list[SearchHit]) -> list[SearchHit]:
        by_source = {h.source_id: h for h in original}
        out: list[SearchHit] = []
        for block in blocks:
            hit = by_source.get(block.source_id)
            if hit:
                out.append(hit)
        return out or original[: len(blocks)]

    @staticmethod
    def dedupe_bilingual_hits(hits: list[SearchHit], query_language: str) -> list[SearchHit]:
        kept, _ = ContextBuilderService.dedupe_bilingual_hits_with_report(hits, query_language)
        return kept

    @staticmethod
    def dedupe_bilingual_hits_with_report(
        hits: list[SearchHit],
        query_language: str,
    ) -> tuple[list[SearchHit], list[dict]]:
        """Drop near-duplicate pages when a better language match exists."""
        if query_language not in {"uk", "en"}:
            return hits, []
        by_base: dict[str, list[SearchHit]] = {}
        for hit in hits:
            base = normalize_url_for_lang_dedupe(hit.url or "")
            by_base.setdefault(base, []).append(hit)

        kept: list[SearchHit] = []
        excluded: list[dict] = []
        seen_bases: set[str] = set()
        for hit in hits:
            base = normalize_url_for_lang_dedupe(hit.url or "")
            if base in seen_bases:
                continue
            group = by_base.get(base, [hit])
            if len(group) == 1:
                kept.append(hit)
                seen_bases.add(base)
                continue
            preferred = hit
            for candidate in group:
                lang = getattr(candidate, "source_language", "") or ""
                if lang == query_language:
                    preferred = candidate
                    break
                if language_match_score(query_language, lang) > language_match_score(
                    query_language, getattr(preferred, "source_language", "") or ""
                ):
                    preferred = candidate
            for candidate in group:
                if candidate is not preferred:
                    excluded.append(
                        {
                            "url": candidate.url,
                            "title": candidate.title,
                            "source_language": getattr(candidate, "source_language", ""),
                            "reason": f"language_duplicate_prefer_{query_language}",
                        }
                    )
            kept.append(preferred)
            seen_bases.add(base)
        return kept, excluded
