"""Semantic query expansion — intent/topic-aware, never keyword soup."""
from __future__ import annotations

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.content_signals import tokenize
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.retrieval_engine.types import ExpansionResult
from app.services.retrieval_intent_service import RetrievalIntentResult


class SemanticExpansionService:
    """Expand queries with at most N closely related semantic concepts."""

    def __init__(
        self,
        profile: KnowledgeProfile | None = None,
        *,
        max_expansions: int = 5,
        max_variants: int = 3,
    ) -> None:
        self.profile = profile or KnowledgeProfileService.default_profile()
        self.max_expansions = max(1, min(max_expansions, 10))
        self.max_variants = max(1, min(max_variants, 5))

    def expand(
        self,
        normalized_query: str,
        *,
        intent_result: RetrievalIntentResult | None = None,
    ) -> ExpansionResult:
        base_tokens = list(dict.fromkeys(tokenize(normalized_query)))
        terms: list[str] = list(base_tokens)
        rejected: list[str] = []
        raw = (normalized_query or "").lower()
        routing = intent_result.legacy_intent if intent_result else "unknown"
        matched_topic = intent_result.matched_topic if intent_result else None

        def _try_add(term: str, *, semantic: bool = True) -> bool:
            t = term.strip().lower()
            if not t or t in terms:
                return False
            if len(terms) >= self.max_expansions + len(base_tokens):
                if semantic:
                    rejected.append(t)
                return False
            terms.append(t)
            return True

        # Topic aliases — only when topic matched and alias overlaps query semantics.
        if matched_topic:
            for alias in matched_topic.aliases[:3]:
                alias_l = alias.lower().strip()
                if not alias_l:
                    continue
                if any(tok in alias_l for tok in base_tokens) or alias_l in raw:
                    for part in tokenize(alias):
                        _try_add(part)

        # Profile expansion rules — intent-gated, pattern-gated.
        for rule in self.profile.query_expansion_rules:
            trigger = rule.trigger_intent or rule.intent
            if trigger and trigger not in (routing, intent_result.intent if intent_result else ""):
                continue
            if rule.trigger_patterns and not any(
                p.lower() in raw for p in rule.trigger_patterns if p
            ):
                continue
            for term in rule.add_terms[:2]:
                expanded = KnowledgeProfileService.expand_placeholders_with_context(
                    term,
                    self.profile,
                    matched_topic=matched_topic,
                )
                for phrase in expanded[:1]:
                    for part in tokenize(phrase):
                        _try_add(part)

        # Supplemental queries from knowledge profile — max 2 short phrases.
        rule_cfg = KnowledgeProfileService.applied_config_for_intent(
            self.profile, routing
        )
        for q in (rule_cfg.supplemental_queries or [])[:2]:
                phrase = " ".join(tokenize(q)[:4])
                if phrase and phrase != normalized_query:
                    _try_add(phrase)

        # Organization name only when query is broad/overview.
        if intent_result and intent_result.is_broad:
            org = self.profile.organization_name or self.profile.site_display_name or ""
            if org:
                _try_add(org.lower())

        semantic_terms = [t for t in terms if t not in base_tokens]
        variants = self._build_variants(normalized_query, semantic_terms)
        return ExpansionResult(
            variants=variants,
            terms=terms[: self.max_expansions + len(base_tokens)],
            strategy="semantic",
            rejected_terms=rejected[:10],
        )

    def _build_variants(self, normalized_query: str, semantic_terms: list[str]) -> list[str]:
        out: list[str] = []
        if normalized_query:
            out.append(normalized_query)
        if semantic_terms:
            phrase = " ".join(semantic_terms[:3])
            if phrase and phrase not in out:
                out.append(phrase)
        keyword_only = " ".join(tokenize(normalized_query))
        if keyword_only and keyword_only not in out and len(out) < self.max_variants:
            out.append(keyword_only)
        return out[: self.max_variants]
