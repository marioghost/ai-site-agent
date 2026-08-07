"""Confidence scoring engine with explainable evidence weights."""
from __future__ import annotations

from app.services.knowledge_profile_generation.models import EvidenceItem

_ORG_SOURCE_WEIGHTS: dict[str, float] = {
    "schema.org": 40,
    "json_ld": 40,
    "og_site_name": 25,
    "header_h1": 15,
    "header_logo": 20,
    "footer_copyright": 20,
    "footer": 20,
    "homepage": 15,
    "about_page": 10,
    "contact_page": 8,
    "frequency": 8,
    "hostname": 35,
    "llm": 5,
}


class ConfidenceEngine:
    def organization_score(self, evidence: list[EvidenceItem]) -> float:
        by_source: dict[str, float] = {}
        for item in evidence:
            catalog = _ORG_SOURCE_WEIGHTS.get(item.source)
            if item.weight > 0:
                pts = float(item.weight)
            elif catalog is not None:
                pts = float(catalog)
            else:
                pts = 5.0
            by_source[item.source] = max(by_source.get(item.source, 0), pts)
        raw = sum(by_source.values())
        return min(1.0, raw / 100.0)

    def topic_score(
        self,
        *,
        page_count: int,
        total_pages: int,
        menu_hits: int = 0,
        heading_hits: int = 0,
        entity_freq: int = 0,
        embedding_cluster_size: int = 0,
    ) -> tuple[float, list[EvidenceItem]]:
        evidence: list[EvidenceItem] = []
        score = 0.0

        if total_pages > 0:
            page_ratio = page_count / total_pages
            page_pts = min(35.0, page_ratio * 100)
            score += page_pts
            evidence.append(
                EvidenceItem(
                    source="page_count",
                    weight=page_pts,
                    detail=f"{page_count} pages",
                )
            )

        if menu_hits > 0:
            menu_pts = min(20.0, menu_hits * 5)
            score += menu_pts
            evidence.append(
                EvidenceItem(source="navigation", weight=menu_pts, detail=f"{menu_hits} nav hits")
            )

        if heading_hits > 0:
            head_pts = min(20.0, heading_hits * 3)
            score += head_pts
            evidence.append(
                EvidenceItem(source="headings", weight=head_pts, detail=f"{heading_hits} headings")
            )

        if entity_freq > 0:
            ent_pts = min(15.0, entity_freq * 2)
            score += ent_pts
            evidence.append(
                EvidenceItem(source="entities", weight=ent_pts, detail=f"{entity_freq} entity hits")
            )

        if embedding_cluster_size > 0:
            emb_pts = min(10.0, embedding_cluster_size * 0.5)
            score += emb_pts
            evidence.append(
                EvidenceItem(
                    source="embeddings",
                    weight=emb_pts,
                    detail=f"cluster size {embedding_cluster_size}",
                )
            )

        return min(1.0, score / 100.0), evidence

    def hint_score(self, page_count: int, pattern_strength: float) -> float:
        return min(1.0, (page_count * 5 + pattern_strength * 40) / 100.0)

    def distribution(self, values: list[float]) -> dict[str, float]:
        if not values:
            return {}
        return {
            "min": round(min(values), 3),
            "max": round(max(values), 3),
            "avg": round(sum(values) / len(values), 3),
            "count": float(len(values)),
        }
