"""Profile-driven canonical source selection and news deprioritization."""
from __future__ import annotations

from app.models.settings import Settings
from app.schemas.knowledge_profile import ImportantTopic, KnowledgeProfile
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.query_intent_service import OVERVIEW_INTENTS, QueryIntent
from app.services.qdrant_service import SearchHit
from app.services.settings_flags import setting_bool


def _score(hit: SearchHit) -> float:
    return hit.final_score or hit.score


def _preferred_types(profile: KnowledgeProfile, intent: str) -> frozenset[str]:
    rule = KnowledgeProfileService.priority_rule_for_intent(profile, intent)
    if rule is None:
        return frozenset()
    return frozenset(rule.boost_document_types)


def _deprioritized_types(profile: KnowledgeProfile, intent: str) -> frozenset[str]:
    rule = KnowledgeProfileService.priority_rule_for_intent(profile, intent)
    if rule is None:
        return frozenset()
    return frozenset(rule.deprioritize_document_types)


class CanonicalSourceService:
    @staticmethod
    def prefer_profile_order(
        hits: list[SearchHit],
        intent: QueryIntent,
        *,
        profile: KnowledgeProfile | None = None,
        settings: Settings | None = None,
    ) -> list[SearchHit]:
        """Soft-order hits using Knowledge Profile preferred/deprioritized types.

        Does not drop sources — only reorders so preferred document types lead
        and deprioritized types trail. Safe when the legacy canonical path is off.
        """
        if not hits:
            return []
        if profile is None and settings is not None:
            profile = KnowledgeProfileService.from_settings(settings)
        if profile is None:
            return list(hits)
        rule = KnowledgeProfileService.priority_rule_for_intent(profile, intent)
        preferred_list = list(rule.boost_document_types) if rule else []
        preferred = frozenset(preferred_list)
        deprioritized = (
            frozenset(rule.deprioritize_document_types) if rule else frozenset()
        )
        if not preferred and not deprioritized:
            return list(hits)

        def rank_key(hit: SearchHit) -> tuple:
            doc = (hit.document_type or "").lower()
            if preferred and doc in preferred:
                tier = 0
                # Preserve Knowledge Profile boost list order among preferred types.
                try:
                    pref_rank = preferred_list.index(doc)
                except ValueError:
                    pref_rank = len(preferred_list)
            elif deprioritized and doc in deprioritized:
                tier = 2
                pref_rank = 0
            else:
                tier = 1
                pref_rank = 0
            return (tier, pref_rank, -_score(hit))

        return sorted(hits, key=rank_key)

    @staticmethod
    def select_context(
        hits: list[SearchHit],
        intent: QueryIntent,
        top_k: int,
        settings: Settings,
        profile: KnowledgeProfile | None = None,
    ) -> list[SearchHit]:
        profile = profile or KnowledgeProfileService.from_settings(settings)
        if not hits:
            return []
        if not setting_bool(settings, "enable_canonical_source_selection"):
            return hits[:top_k]

        preferred = _preferred_types(profile, intent)
        deprioritized = _deprioritized_types(profile, intent)
        overview = intent in OVERVIEW_INTENTS

        for hit in hits:
            hit.is_canonical = hit.document_type in preferred
            hit.excluded_as_news = False

        if (
            overview
            and setting_bool(settings, "enable_news_deprioritization_for_overview_queries")
            and preferred
        ):
            canonical = [h for h in hits if h.is_canonical]
            noisy = [h for h in hits if h.document_type in deprioritized]
            if noisy and canonical:
                for h in noisy:
                    h.excluded_as_news = True
                ordered = sorted(canonical, key=_score, reverse=True)
                fillers = [
                    h
                    for h in sorted(hits, key=_score, reverse=True)
                    if not h.excluded_as_news and h not in ordered
                ]
                ordered.extend(fillers)
                return ordered[:top_k]
            if noisy and not canonical:
                for h in noisy:
                    h.excluded_as_news = True

        ordered = sorted(hits, key=lambda h: (not h.is_canonical, -_score(h)))
        return ordered[:top_k]

    @staticmethod
    def context_for_llm(hits: list[SearchHit], intent: QueryIntent) -> list[SearchHit]:
        if intent in OVERVIEW_INTENTS:
            filtered = [h for h in hits if not h.excluded_as_news]
            if filtered:
                return filtered
        return hits

    @staticmethod
    def needs_canonical_fallback(
        hits: list[SearchHit],
        intent: QueryIntent,
        settings: Settings,
        profile: KnowledgeProfile | None = None,
    ) -> bool:
        profile = profile or KnowledgeProfileService.from_settings(settings)
        if not setting_bool(settings, "fallback_second_pass_enabled"):
            return False
        if intent not in OVERVIEW_INTENTS | {"contacts_query"}:
            return False
        if not hits:
            return True
        preferred = _preferred_types(profile, intent)
        deprioritized = _deprioritized_types(profile, intent)
        if not preferred:
            return False
        if intent in OVERVIEW_INTENTS:
            has_canonical = any(h.document_type in preferred for h in hits)
            noisy_heavy = sum(
                1 for h in hits[:5] if h.document_type in deprioritized
            ) >= max(2, len(hits[:5]) // 2)
            return (not has_canonical) or noisy_heavy
        return not any(h.document_type in preferred for h in hits)

    @staticmethod
    def merge_hits(*pools: list[SearchHit]) -> list[SearchHit]:
        merged: dict[str, SearchHit] = {}
        for pool in pools:
            for hit in pool:
                key = f"{hit.source_id}:{hit.chunk_index}"
                existing = merged.get(key)
                if existing is None or _score(hit) > _score(existing):
                    merged[key] = hit
        return sorted(merged.values(), key=_score, reverse=True)
