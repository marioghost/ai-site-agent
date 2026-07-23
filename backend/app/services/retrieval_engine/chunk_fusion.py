"""Merge and deduplicate chunks while preserving document structure."""
from __future__ import annotations

from app.services.qdrant_service import SearchHit
from app.utils.hashing import content_hash


class ChunkFusionService:
    @staticmethod
    def group_by_source(hits: list[SearchHit]) -> dict[int, list[SearchHit]]:
        grouped: dict[int, list[SearchHit]] = {}
        for hit in hits:
            grouped.setdefault(hit.source_id, []).append(hit)
        for sid in grouped:
            grouped[sid].sort(key=lambda h: h.chunk_index)
        return grouped

    @classmethod
    def fuse_source_chunks(
        cls,
        hits: list[SearchHit],
        *,
        merge_neighbours: bool = True,
        max_chunks: int = 6,
    ) -> list[SearchHit]:
        if not hits:
            return []
        selected = hits[:max_chunks]
        if not merge_neighbours:
            return selected
        return cls._merge_neighbouring(selected)

    @staticmethod
    def _merge_neighbouring(hits: list[SearchHit]) -> list[SearchHit]:
        if len(hits) <= 1:
            return hits
        merged: list[SearchHit] = [hits[0]]
        for hit in hits[1:]:
            prev = merged[-1]
            if hit.chunk_index == prev.chunk_index + 1:
                prev.text = ChunkFusionService._dedupe_join(prev.text, hit.text)
                prev.final_score = max(prev.final_score, hit.final_score)
                prev.score = prev.final_score
                if hit.heading and hit.heading not in (prev.heading or ""):
                    prev.heading = (
                        f"{prev.heading}\n{hit.heading}".strip()
                        if prev.heading
                        else hit.heading
                    )
            else:
                merged.append(hit)
        return merged

    @staticmethod
    def _dedupe_join(a: str, b: str) -> str:
        a = (a or "").strip()
        b = (b or "").strip()
        if not a:
            return b
        if not b:
            return a
        if b in a or a.endswith(b[: min(80, len(b))]):
            return a
        return f"{a}\n\n{b}"

    @staticmethod
    def merge_text_segments(segments: list[str]) -> str:
        parts: list[str] = []
        seen: set[str] = set()
        for segment in segments:
            seg = (segment or "").strip()
            if not seg:
                continue
            h = content_hash(seg)
            if h in seen:
                continue
            seen.add(h)
            parts.append(seg)
        return "\n\n".join(parts)
