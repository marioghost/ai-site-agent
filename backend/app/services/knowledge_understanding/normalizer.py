"""Concept alias merge via embedding similarity — never regex synonym tables."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from app.services.knowledge_understanding.similarity import cosine

EmbedFn = Callable[[list[str]], list[list[float]]]

# Near-duplicate gate. Distinct single-token labels never fuzzy-merge.
DEFAULT_MERGE_THRESHOLD = 0.88
_TOKEN_RE = re.compile(r"[\w\u0400-\u04FF]+", re.UNICODE)


@dataclass
class RawConcept:
    label: str
    aliases: list[str] = field(default_factory=list)
    confidence: float = 0.0
    source_id: int | None = None
    relation: str = "explains"
    weight: float = 1.0
    is_entity: bool = False
    is_canonical_source: bool = False


@dataclass
class NormalizedConcept:
    concept_key: str
    label: str
    aliases: list[str]
    confidence: float
    embedding: list[float]
    members: list[RawConcept]


def concept_key_for(label: str) -> str:
    toks = _TOKEN_RE.findall((label or "").lower())
    key = "-".join(toks)[:96]
    return key or "concept"


def _tokens(label: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((label or "").lower()) if len(t) >= 2}


def should_merge_labels(
    label_a: str,
    label_b: str,
    similarity: float,
    *,
    threshold: float = DEFAULT_MERGE_THRESHOLD,
) -> bool:
    """Conservative merge gate — prevents irreversible within-snapshot poison merges.

    Exact labels always merge. Distinct single-token labels never fuzzy-merge
    (``rates`` vs ``dates``). Multi-token labels merge on embedding similarity.
    """
    a = (label_a or "").strip().lower()
    b = (label_b or "").strip().lower()
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = _tokens(a), _tokens(b)
    # Single-token distinct labels: embedding noise must not collapse them.
    if len(ta) == 1 and len(tb) == 1:
        return False
    return similarity >= threshold


class ConceptNormalizer:
    """Merge concept aliases using embedding similarity only."""

    def __init__(
        self,
        *,
        embed_fn: EmbedFn,
        merge_threshold: float = DEFAULT_MERGE_THRESHOLD,
    ) -> None:
        self._embed = embed_fn
        self._threshold = merge_threshold

    def normalize(self, raw: list[RawConcept]) -> list[NormalizedConcept]:
        items = [c for c in raw if (c.label or "").strip()]
        if not items:
            return []

        labels = [c.label.strip() for c in items]
        embeddings = self._embed(labels)
        if len(embeddings) != len(items):
            raise RuntimeError("embed_fn returned unexpected length")

        parent = list(range(len(items)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[rj] = ri

        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                sim = (
                    1.0
                    if labels[i].lower() == labels[j].lower()
                    else cosine(embeddings[i], embeddings[j])
                )
                if should_merge_labels(
                    labels[i],
                    labels[j],
                    sim,
                    threshold=self._threshold,
                ):
                    union(i, j)

        clusters: dict[int, list[int]] = {}
        for i in range(len(items)):
            clusters.setdefault(find(i), []).append(i)

        out: list[NormalizedConcept] = []
        for idxs in clusters.values():
            idxs_sorted = sorted(
                idxs,
                key=lambda i: (items[i].confidence, len(items[i].label)),
                reverse=True,
            )
            primary_i = idxs_sorted[0]
            primary = items[primary_i]
            aliases: list[str] = []
            members: list[RawConcept] = []
            emb_acc = list(embeddings[primary_i])
            conf = primary.confidence
            for i in idxs_sorted:
                member = items[i]
                members.append(member)
                if i != primary_i and member.label.strip().lower() != primary.label.strip().lower():
                    aliases.append(member.label.strip())
                for a in member.aliases:
                    cleaned = (a or "").strip()
                    if cleaned and cleaned.lower() != primary.label.strip().lower():
                        aliases.append(cleaned)
                conf = max(conf, member.confidence)
                for k, v in enumerate(embeddings[i]):
                    if k < len(emb_acc):
                        emb_acc[k] += v
            n = float(len(idxs_sorted))
            emb = [v / n for v in emb_acc]
            aliases = list(dict.fromkeys(aliases))
            out.append(
                NormalizedConcept(
                    concept_key=concept_key_for(primary.label),
                    label=primary.label.strip(),
                    aliases=aliases,
                    confidence=conf,
                    embedding=emb,
                    members=members,
                )
            )

        seen: dict[str, int] = {}
        final: list[NormalizedConcept] = []
        for concept in out:
            key = concept.concept_key
            n = seen.get(key, 0)
            seen[key] = n + 1
            if n:
                key = f"{key}-{n + 1}"
            final.append(
                NormalizedConcept(
                    concept_key=key,
                    label=concept.label,
                    aliases=concept.aliases,
                    confidence=concept.confidence,
                    embedding=concept.embedding,
                    members=concept.members,
                )
            )
        return final
