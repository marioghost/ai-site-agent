"""Concept alias merge via embedding similarity — never regex synonym tables."""
from __future__ import annotations

import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

EmbedFn = Callable[[list[str]], list[list[float]]]
ProgressFn = Callable[[str, str, dict], None]
StopFn = Callable[[], bool]

# Near-duplicate gate. Distinct single-token labels never fuzzy-merge.
DEFAULT_MERGE_THRESHOLD = 0.88
_TOKEN_RE = re.compile(r"[\w\u0400-\u04FF]+", re.UNICODE)
# Cooperative progress while comparing pairs (large corpora).
_PROGRESS_EVERY_PAIRS = 25_000
_PROGRESS_EVERY_SECONDS = 2.0


class ConceptNormalizeStopped(Exception):
    """Cooperative stop requested during concept normalization."""


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

    def normalize(
        self,
        raw: list[RawConcept],
        *,
        on_progress: ProgressFn | None = None,
        should_stop: StopFn | None = None,
    ) -> list[NormalizedConcept]:
        items = [c for c in raw if (c.label or "").strip()]
        if not items:
            return []

        if should_stop and should_stop():
            raise ConceptNormalizeStopped()

        labels = [c.label.strip() for c in items]
        labels_l = [lab.lower() for lab in labels]
        token_sets = [_tokens(lab) for lab in labels]

        if on_progress:
            on_progress(
                "rebuilding_understanding",
                f"Embedding {len(items)} concept labels",
                {
                    "current_phase": "rebuilding_understanding",
                    "understanding_raw_concepts": len(items),
                },
            )

        embeddings = self._embed(labels)
        if len(embeddings) != len(items):
            raise RuntimeError("embed_fn returned unexpected length")

        if should_stop and should_stop():
            raise ConceptNormalizeStopped()

        # Precompute norms once — same cosine, far fewer repeated sqrt/sums.
        norms = [
            math.sqrt(sum(x * x for x in emb)) if emb else 0.0 for emb in embeddings
        ]

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

        # Phase 1 — exact label merge in O(n). Semantically required anyway.
        first_by_label: dict[str, int] = {}
        for i, key in enumerate(labels_l):
            prev = first_by_label.get(key)
            if prev is None:
                first_by_label[key] = i
            else:
                union(i, prev)

        if on_progress:
            on_progress(
                "rebuilding_understanding",
                f"Merging concept aliases ({len(first_by_label)} unique labels)",
                {
                    "current_phase": "rebuilding_understanding",
                    "understanding_unique_labels": len(first_by_label),
                    "understanding_raw_concepts": len(items),
                },
            )

        # Phase 2 — fuzzy merge only across different components.
        # Skip pairs that cannot merge (exact already united; single-token distinct).
        n = len(items)
        pairs_checked = 0
        pairs_total_est = max(1, n * (n - 1) // 2)
        last_progress_at = time.monotonic()

        def maybe_progress(force: bool = False) -> None:
            nonlocal last_progress_at
            if not on_progress:
                return
            now = time.monotonic()
            if (
                not force
                and pairs_checked % _PROGRESS_EVERY_PAIRS != 0
                and (now - last_progress_at) < _PROGRESS_EVERY_SECONDS
            ):
                return
            last_progress_at = now
            on_progress(
                "rebuilding_understanding",
                f"Comparing concept similarity ({pairs_checked:,} checks)",
                {
                    "current_phase": "rebuilding_understanding",
                    "understanding_merge_checks": pairs_checked,
                    "understanding_merge_checks_est": pairs_total_est,
                    "understanding_unique_labels": len(first_by_label),
                },
            )

        for i in range(n):
            if should_stop and should_stop():
                raise ConceptNormalizeStopped()
            ri = find(i)
            ti = token_sets[i]
            single_i = len(ti) == 1
            for j in range(i + 1, n):
                pairs_checked += 1
                if find(j) == ri:
                    continue
                # Distinct single-token labels never fuzzy-merge — skip cosine.
                if single_i and len(token_sets[j]) == 1:
                    continue
                if labels_l[i] == labels_l[j]:
                    union(i, j)
                    ri = find(i)
                    continue
                na, nb = norms[i], norms[j]
                if na <= 0.0 or nb <= 0.0:
                    sim = 0.0
                else:
                    # Inline cosine with cached norms (identical math to cosine()).
                    emb_i, emb_j = embeddings[i], embeddings[j]
                    if len(emb_i) != len(emb_j):
                        sim = 0.0
                    else:
                        dot = 0.0
                        for x, y in zip(emb_i, emb_j):
                            dot += x * y
                        sim = dot / (na * nb)
                if should_merge_labels(
                    labels[i],
                    labels[j],
                    sim,
                    threshold=self._threshold,
                ):
                    union(i, j)
                    ri = find(i)
                if pairs_checked % 4096 == 0:
                    maybe_progress()
                    if should_stop and should_stop():
                        raise ConceptNormalizeStopped()

        maybe_progress(force=True)

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
            n_members = float(len(idxs_sorted))
            emb = [v / n_members for v in emb_acc]
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
            n_seen = seen.get(key, 0)
            seen[key] = n_seen + 1
            if n_seen:
                key = f"{key}-{n_seen + 1}"
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
