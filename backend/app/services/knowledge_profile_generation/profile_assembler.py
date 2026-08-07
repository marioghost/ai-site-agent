"""Assemble final KnowledgeProfile from pipeline context."""
from __future__ import annotations

import re
from copy import deepcopy

from app.schemas.knowledge_profile import (
    DocumentTypeRule,
    ImportantTopic,
    KnowledgeProfile,
    QueryExpansionRule,
    SourcePriorityRule,
)
from app.services.knowledge_profile_generation.alias_utils import dedupe_topic_aliases
from app.services.knowledge_profile_generation.models import (
    AssembledProfile,
    PipelineContext,
)
from app.services.knowledge_profile_generation.structural_filters import (
    derive_site_subject,
)
from app.services.knowledge_profile_service import generic_corporate_profile


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return s[:48] or "topic"


class ProfileAssembler:
    def assemble(self, ctx: PipelineContext) -> AssembledProfile:
        assert ctx.organization is not None
        assert ctx.hierarchy is not None
        assert ctx.statistics is not None

        # Always assemble from the generic base — never seed industry PRESETS.
        base = deepcopy(generic_corporate_profile())

        hint_rules = ctx.extras.get("hint_rules", [])
        doc_rules = self._document_rules(ctx, base)
        topics = self._important_topics(ctx)

        homepage_texts: list[str] = []
        for page in ctx.pages:
            if page.is_homepage and page.texts:
                homepage_texts = list(page.texts)
                break

        site_subject = derive_site_subject(
            organization_name=ctx.organization.name,
            homepage_texts=homepage_texts,
        )

        overview_patterns = self._overview_patterns(ctx, base)
        expansions = self._expansions(ctx, topics, base)
        priorities = self._priorities(doc_rules, base, ctx)

        profile = KnowledgeProfile(
            site_display_name=ctx.organization.name,
            organization_name=ctx.organization.name,
            organization_aliases=list(ctx.organization.aliases),
            site_subject=site_subject,
            entity_type="organization",
            overview_query_patterns=overview_patterns,
            important_topics=topics,
            document_type_rules=doc_rules,
            content_hint_rules=hint_rules or base.content_hint_rules,
            source_priority_rules=priorities,
            query_expansion_rules=expansions,
        )
        profile, _ = dedupe_topic_aliases(profile)

        return AssembledProfile(
            profile=profile,
            organization=ctx.organization,
            topics=ctx.topics,
            hint_candidates=ctx.hint_candidates,
            entities=ctx.entities,
            hierarchy=ctx.hierarchy,
            statistics=ctx.statistics,
            overview_patterns=overview_patterns,
            query_expansion_rules=expansions,
            source_priority_rules=priorities,
        )

    def _important_topics(self, ctx: PipelineContext) -> list[ImportantTopic]:
        hint_ids = ctx.extras.get("registered_hint_ids", set())
        out: list[ImportantTopic] = []
        for t in ctx.topics:
            hints = [h for h in t.preferred_content_hints if h in hint_ids or not hint_ids]
            out.append(
                ImportantTopic(
                    key=t.id,
                    label=t.title,
                    aliases=t.aliases,
                    preferred_document_types=t.preferred_document_types,
                    preferred_content_hints=hints,
                    answer_strategy=t.answer_strategy,  # type: ignore[arg-type]
                )
            )
        return out[:15]

    def _document_rules(
        self, ctx: PipelineContext, base: KnowledgeProfile
    ) -> list[DocumentTypeRule]:
        rules = deepcopy(base.document_type_rules)
        seen = {r.document_type for r in rules}
        if ctx.statistics:
            from collections import Counter

            for seg, count in Counter(ctx.statistics.top_url_segments).most_common(20):
                if count < 2:
                    continue
                doc_type = f"{_slug(seg)}_page"
                if doc_type in seen:
                    continue
                seen.add(doc_type)
                rules.append(
                    DocumentTypeRule(
                        document_type=doc_type,
                        url_patterns=[f"/{seg}", f"{seg}/"],
                        title_patterns=[seg.replace("-", " ").title()],
                        priority=45,
                    )
                )
        return rules

    def _overview_patterns(
        self, ctx: PipelineContext, base: KnowledgeProfile
    ) -> list[str]:
        patterns = list(base.overview_query_patterns)
        org = ctx.organization.name if ctx.organization else ""
        if org:
            patterns.append(org.lower())
        return list(dict.fromkeys(patterns))

    def _expansions(
        self,
        ctx: PipelineContext,
        topics: list[ImportantTopic],
        base: KnowledgeProfile,
    ) -> list[QueryExpansionRule]:
        rules = deepcopy(base.query_expansion_rules)
        for topic in topics[:6]:
            rules.append(
                QueryExpansionRule(
                    trigger_patterns=topic.aliases[:3] or [topic.label.lower()],
                    add_terms=list(topic.aliases) + ["{{organization_name}}"],
                    intent="topic_overview",
                )
            )
        return rules

    def _priorities(
        self,
        doc_rules: list[DocumentTypeRule],
        base: KnowledgeProfile,
        ctx: PipelineContext,
    ) -> list[SourcePriorityRule]:
        doc_types = [r.document_type for r in doc_rules]
        hint_ids = set(ctx.extras.get("registered_hint_ids", []))
        rules = deepcopy(base.source_priority_rules)
        if "faq" in hint_ids:
            rules.append(
                SourcePriorityRule(
                    query_intent="faq_like",
                    boost_document_types=[d for d in doc_types if "faq" in d] + ["faq_page"],
                    boost_content_hints=["faq"],
                )
            )
        if "contacts" in hint_ids:
            rules.append(
                SourcePriorityRule(
                    query_intent="contacts_query",
                    boost_document_types=[d for d in doc_types if "contact" in d]
                    + ["contact_page"],
                    boost_content_hints=["contacts"],
                )
            )
        return rules
