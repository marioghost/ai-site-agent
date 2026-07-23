"""Knowledge graph builder — links entities, pages, and categories."""
from __future__ import annotations

from app.services.knowledge_profile_generation.models import (
    ExtractedEntity,
    KnowledgeGraph,
    KnowledgeGraphNode,
    PageRecord,
    WebsiteHierarchy,
)


class KnowledgeGraphBuilder:
    def build(
        self,
        pages: list[PageRecord],
        hierarchy: WebsiteHierarchy,
        entities: list[ExtractedEntity],
    ) -> KnowledgeGraph:
        nodes: list[KnowledgeGraphNode] = []
        edges: list[tuple[str, str, str]] = []

        cat_pages: dict[str, list[str]] = {}
        for cat in hierarchy.categories:
            cat_pages.setdefault(cat.category, []).append(cat.url)

        for category, urls in cat_pages.items():
            node_id = f"cat:{category}"
            nodes.append(
                KnowledgeGraphNode(
                    node_id=node_id,
                    label=category,
                    node_type="category",
                    weight=float(len(urls)),
                    page_urls=urls[:50],
                )
            )

        for entity in entities[:40]:
            node_id = f"ent:{entity.entity_type}:{entity.name[:40]}"
            nodes.append(
                KnowledgeGraphNode(
                    node_id=node_id,
                    label=entity.name,
                    node_type=entity.entity_type,
                    weight=float(entity.frequency),
                    page_urls=entity.pages[:20],
                )
            )
            for url in entity.pages[:5]:
                for cat in hierarchy.categories:
                    if cat.url == url:
                        edges.append((node_id, f"cat:{cat.category}", "appears_in"))
                        break

        for page in pages[:100]:
            pid = f"page:{page.source_id}"
            nodes.append(
                KnowledgeGraphNode(
                    node_id=pid,
                    label=page.title or page.url,
                    node_type="page",
                    weight=1.0,
                    page_urls=[page.url],
                )
            )

        return KnowledgeGraph(nodes=nodes[:200], edges=edges[:300])
