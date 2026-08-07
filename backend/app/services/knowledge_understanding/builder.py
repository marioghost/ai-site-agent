"""Understanding Builder — SI profiles → site-wide semantic understanding."""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.models.source import Source
from app.schemas.source_intelligence import SourceSemanticProfile
from app.services.knowledge_understanding.models import EvidenceLink
from app.services.knowledge_understanding.normalizer import (
    ConceptNormalizer,
    NormalizedConcept,
    RawConcept,
)

# Cap subtopics per source (SEMANTIC_UNDERSTANDING_MVP §8 / §15).
_MAX_SUBTOPICS = 6

EmbedFn = Callable[[list[str]], list[list[float]]]


@dataclass
class BuiltUnderstanding:
    concepts: list[NormalizedConcept]
    evidence: list[EvidenceLink] = field(default_factory=list)
    canonical_by_concept: dict[str, int] = field(default_factory=dict)
    sources_linked: int = 0
    sources_total: int = 0


def extract_raw_concepts(source: Source) -> list[RawConcept]:
    """Extract generic concepts from one source's SI — no domain rules."""
    semantic = _semantic_for(source)
    if semantic is None:
        return []

    out: list[RawConcept] = []
    conf = float(semantic.confidence or 0.0)
    topic_conf = float(semantic.main_topic_confidence or conf)
    aliases = _alias_pool(semantic)
    is_canonical = bool(getattr(source, "canonical", False))
    source_id = int(source.id)

    main = (semantic.main_topic or "").strip()
    if main:
        out.append(
            RawConcept(
                label=main,
                aliases=list(aliases),
                confidence=max(topic_conf, conf),
                source_id=source_id,
                relation="explains",
                weight=max(topic_conf, conf, 0.35),
                is_canonical_source=is_canonical,
            )
        )

    for sub in (semantic.subtopics or [])[:_MAX_SUBTOPICS]:
        label = (sub or "").strip()
        if not label or (main and label.lower() == main.lower()):
            continue
        out.append(
            RawConcept(
                label=label,
                aliases=[],
                confidence=max(0.0, conf * 0.75),
                source_id=source_id,
                relation="explains",
                weight=max(0.2, conf * 0.55),
                is_canonical_source=is_canonical,
            )
        )

    entity_type = (semantic.entity_type or "").strip()
    entity_conf = float(semantic.entity_type_confidence or 0.0)
    if entity_type and entity_conf > 0.4:
        # Label is the entity type from SI; page title is an alias only.
        # Using title as the concept label polluted the index with page chrome.
        title = (source.title or "").strip()
        entity_aliases: list[str] = []
        if title and title.lower() != entity_type.lower():
            entity_aliases.append(title)
        out.append(
            RawConcept(
                label=entity_type,
                aliases=entity_aliases,
                confidence=entity_conf,
                source_id=source_id,
                relation="mentions",
                weight=entity_conf,
                is_entity=True,
                is_canonical_source=is_canonical,
            )
        )

    return out


def _alias_pool(semantic: SourceSemanticProfile) -> list[str]:
    """Concept aliases from SI lexical fields only.

    ``suitable_for`` / ``supported_intents`` are need-type associations, not
    concept aliases — stuffing them into aliases poisoned lexical resolution.
    """
    seen: set[str] = set()
    out: list[str] = []
    for bucket in (
        semantic.search_keywords,
        semantic.synonyms,
        semantic.semantic_tags,
    ):
        for item in bucket or []:
            text = (item or "").strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            out.append(text)
    return out


def _need_types(semantic: SourceSemanticProfile) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for bucket in (semantic.suitable_for, semantic.supported_intents):
        for item in bucket or []:
            text = (item or "").strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            out.append(text)
    return out


def _semantic_for(source: Source) -> SourceSemanticProfile | None:
    """Read SI semantic profile from Source.intelligence_json (reuse SI storage)."""
    try:
        raw = json.loads(getattr(source, "intelligence_json", None) or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or not raw:
        return None
    return SourceSemanticProfile.from_storage(raw)


class UnderstandingBuilder:
    """Aggregate per-source SI into a site-wide understanding model."""

    def __init__(
        self,
        *,
        embed_fn: EmbedFn,
        merge_threshold: float | None = None,
    ) -> None:
        kwargs: dict = {"embed_fn": embed_fn}
        if merge_threshold is not None:
            kwargs["merge_threshold"] = merge_threshold
        self._normalizer = ConceptNormalizer(**kwargs)

    def build(
        self,
        sources: Sequence[Source],
        *,
        on_progress: Callable[[str, str, dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> BuiltUnderstanding:
        raw: list[RawConcept] = []
        sources_with_si = 0
        hash_to_sources: dict[str, list[int]] = defaultdict(list)
        need_types_by_source: dict[int, list[str]] = {}

        total_sources = len(sources)
        for idx, source in enumerate(sources, start=1):
            if should_stop and should_stop():
                from app.services.knowledge_understanding.normalizer import (
                    ConceptNormalizeStopped,
                )

                raise ConceptNormalizeStopped()
            if on_progress and (idx == 1 or idx % 50 == 0 or idx == total_sources):
                on_progress(
                    "rebuilding_understanding",
                    f"Extracting concepts from sources ({idx}/{total_sources})",
                    {
                        "current_phase": "rebuilding_understanding",
                        "understanding_sources_done": idx,
                        "understanding_sources": total_sources,
                    },
                )
            items = extract_raw_concepts(source)
            if items:
                sources_with_si += 1
            raw.extend(items)
            content_hash = (getattr(source, "content_hash", None) or "").strip()
            if content_hash and source.id is not None:
                hash_to_sources[content_hash].append(int(source.id))
            semantic = _semantic_for(source)
            if semantic is not None and source.id is not None:
                needs = _need_types(semantic)
                if needs:
                    need_types_by_source[int(source.id)] = needs

        concepts = self._normalizer.normalize(
            raw, on_progress=on_progress, should_stop=should_stop
        )
        evidence: list[EvidenceLink] = []
        canonical_by_concept: dict[str, int] = {}

        for concept in concepts:
            best_canonical: tuple[float, int] | None = None
            seen_links: set[tuple[int, str]] = set()
            for member in concept.members:
                if member.source_id is None:
                    continue
                link_key = (member.source_id, member.relation)
                if link_key in seen_links:
                    continue
                seen_links.add(link_key)
                evidence.append(
                    EvidenceLink(
                        concept_key=concept.concept_key,
                        source_id=member.source_id,
                        relation=member.relation,
                        weight=float(member.weight),
                        confidence=float(member.confidence),
                    )
                )
                if member.is_canonical_source:
                    cand = (member.confidence, member.source_id)
                    if best_canonical is None or cand > best_canonical:
                        best_canonical = cand

            if best_canonical is not None:
                canonical_by_concept[concept.concept_key] = best_canonical[1]
            else:
                explains = [
                    m
                    for m in concept.members
                    if m.source_id is not None and m.relation == "explains"
                ]
                if explains:
                    top = max(explains, key=lambda m: m.confidence)
                    if top.source_id is not None:
                        canonical_by_concept[concept.concept_key] = top.source_id

            # Need-type associations from SI (not aliases): one answers link per source.
            for member in concept.members:
                if member.source_id is None or member.relation != "explains":
                    continue
                if not need_types_by_source.get(member.source_id):
                    continue
                evidence.append(
                    EvidenceLink(
                        concept_key=concept.concept_key,
                        source_id=member.source_id,
                        relation="answers",
                        weight=max(0.35, float(member.weight) * 0.6),
                        confidence=float(member.confidence),
                    )
                )

        # Duplicate / support links from shared content_hash.
        for source_ids in hash_to_sources.values():
            if len(source_ids) < 2:
                continue
            primary = source_ids[0]
            for other in source_ids[1:]:
                for concept in concepts:
                    member_ids = {m.source_id for m in concept.members if m.source_id}
                    if primary in member_ids and other in member_ids:
                        evidence.append(
                            EvidenceLink(
                                concept_key=concept.concept_key,
                                source_id=other,
                                relation="supports",
                                weight=0.4,
                                confidence=0.4,
                            )
                        )

        uniq: dict[tuple[str, int, str], EvidenceLink] = {}
        for row in evidence:
            key = (row.concept_key, row.source_id, row.relation)
            prev = uniq.get(key)
            if prev is None or row.weight > prev.weight:
                uniq[key] = row

        return BuiltUnderstanding(
            concepts=concepts,
            evidence=list(uniq.values()),
            canonical_by_concept=canonical_by_concept,
            sources_linked=sources_with_si,
            sources_total=len(sources),
        )


def source_has_intelligence(source: Source) -> bool:
    raw = getattr(source, "intelligence_json", None) or "{}"
    if not raw or raw == "{}":
        return False
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return False
    return bool(data)
