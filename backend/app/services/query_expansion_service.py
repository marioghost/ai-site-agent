"""Profile-driven query expansion for retrieval recall."""
from __future__ import annotations

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.content_signals import tokenize
from app.services.knowledge_profile_service import KnowledgeProfileService

_SHORT_QUERY_MAX_TOKENS = 4


class QueryExpansionService:
    def __init__(self, profile: KnowledgeProfile | None = None) -> None:
        self.profile = profile or KnowledgeProfileService.default_profile()

    @staticmethod
    def is_short_query(query: str) -> bool:
        return 1 <= len(tokenize(query)) <= _SHORT_QUERY_MAX_TOKENS

    def expanded_terms(self, normalized_query: str, *, intent: str = "") -> list[str]:
        tokens = tokenize(normalized_query)
        terms: list[str] = list(dict.fromkeys(tokens))
        raw = (normalized_query or "").lower()

        for topic in self.profile.important_topics:
            for alias in topic.aliases:
                a = alias.lower().strip()
                if a and a in raw:
                    for part in tokenize(alias):
                        if part not in terms:
                            terms.append(part)
                    for hint in topic.preferred_content_hints:
                        if hint not in terms:
                            terms.append(hint)

        for rule in self.profile.query_expansion_rules:
            if rule.intent and intent and rule.intent != intent:
                continue
            if not any(p.lower() in raw for p in rule.trigger_patterns if p):
                continue
            for term in rule.add_terms:
                for expanded in KnowledgeProfileService.expand_placeholders(term, self.profile):
                    for part in tokenize(expanded):
                        if part not in terms:
                            terms.append(part)
                    if expanded and expanded not in terms:
                        terms.append(expanded)

        return terms

    def variants(self, normalized_query: str, *, intent: str = "") -> list[str]:
        out: list[str] = []
        if normalized_query:
            out.append(normalized_query)
        keyword_only = " ".join(tokenize(normalized_query))
        if keyword_only and keyword_only not in out:
            out.append(keyword_only)
        expanded = " ".join(self.expanded_terms(normalized_query, intent=intent))
        if expanded and expanded not in out:
            out.append(expanded)
        return out
