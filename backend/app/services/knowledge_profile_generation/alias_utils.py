"""Helpers for normalizing topic aliases in generated profiles."""
from __future__ import annotations

from app.schemas.knowledge_profile import ImportantTopic, KnowledgeProfile


def dedupe_topic_aliases(profile: KnowledgeProfile) -> tuple[KnowledgeProfile, int]:
    """Keep the first occurrence of each alias globally across topics."""
    seen: set[str] = set()
    removed = 0
    updated: list[ImportantTopic] = []

    for topic in profile.important_topics:
        kept: list[str] = []
        for alias in topic.aliases:
            normalized = alias.lower().strip()
            if not normalized:
                continue
            if normalized in seen:
                removed += 1
                continue
            seen.add(normalized)
            kept.append(alias.strip())

        if not kept:
            for fallback in (topic.label, topic.key.replace("_", " "), topic.key):
                candidate = fallback.strip()
                normalized = candidate.lower()
                if not candidate:
                    continue
                if normalized not in seen:
                    seen.add(normalized)
                    kept = [candidate]
                    break

        updated.append(topic.model_copy(update={"aliases": kept}))

    return profile.model_copy(update={"important_topics": updated}), removed
