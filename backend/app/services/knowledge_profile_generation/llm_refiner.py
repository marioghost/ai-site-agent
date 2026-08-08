"""Stage 7 — constrained LLM refinement (labels/descriptions only)."""
from __future__ import annotations

import json
import re
from copy import deepcopy

from app.models.settings import Settings
from app.schemas.knowledge_profile import ImportantTopic, KnowledgeProfile
from app.services.knowledge_profile_generation.alias_utils import dedupe_topic_aliases
from app.services.knowledge_profile_generation.models import (
    DetectedOrganization,
    DiscoveredTopic,
    PipelineContext,
)
from app.services.knowledge_profile_generation.site_identity import ground_topic_label
from app.services.ollama_service import OllamaError, OllamaService


class LlmRefiner:
    def refine(
        self,
        ctx: PipelineContext,
        settings: Settings,
    ) -> tuple[KnowledgeProfile | None, dict]:
        if ctx.profile is None:
            return None, {"llm_tokens": 0, "llm_used": False}

        allowed_topic_ids = [t.id for t in ctx.topics]
        allowed_hints = sorted(ctx.extras.get("registered_hint_ids", []))

        summary = {
            "organization": ctx.organization.name if ctx.organization else "",
            "organization_evidence": [
                e.model_dump() for e in (ctx.organization.evidence if ctx.organization else [])
            ],
            "site_subject": ctx.profile.site_subject,
            "entity_type": ctx.profile.entity_type,
            "statistics": ctx.statistics.model_dump() if ctx.statistics else {},
            "entities": [e.model_dump() for e in ctx.entities[:30]],
            "topic_candidates": [
                {
                    "id": t.id,
                    "title": t.title,
                    "aliases": t.aliases,
                    "page_count": t.page_count,
                    "description": t.description,
                }
                for t in ctx.topics
            ],
            "allowed_topic_ids": allowed_topic_ids,
            "allowed_content_hints": allowed_hints,
            "current_profile": ctx.profile.model_dump(),
        }

        system = (
            "You refine a KnowledgeProfile JSON for a website RAG agent. "
            "Return ONLY valid JSON with the same top-level schema as current_profile. "
            "RULES: "
            "1) Do NOT change organization_name, site_subject, or entity_type. "
            "2) Do NOT invent new important_topics keys — only use allowed_topic_ids. "
            "3) Do NOT reference content hints outside allowed_content_hints. "
            "4) You MAY improve topic labels only using words that appear in topic_candidates. "
            "5) Do NOT invent URLs or document types not in the input. "
            "6) Do NOT replace labels with generic English like 'About the organization'."
        )
        user = json.dumps(summary, ensure_ascii=False)[:14000]

        try:
            ollama = OllamaService(timeout=settings.ollama_generation_timeout_seconds)
            raw = ollama.chat(
                settings.llm_model,
                system,
                user,
                temperature=0.15,
                max_tokens=4096,
            )
        except OllamaError as exc:
            return ctx.profile, {"llm_tokens": 0, "llm_used": False, "llm_error": str(exc)}

        cleaned = raw.content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            data = json.loads(cleaned)
            refined = KnowledgeProfile.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            return ctx.profile, {"llm_tokens": len(user.split()), "llm_used": False, "llm_parse_error": True}

        refined = self._enforce_constraints(refined, ctx, allowed_topic_ids, allowed_hints)
        return refined, {
            "llm_tokens": len(user.split()) + len(raw.split()),
            "llm_used": True,
        }

    def _enforce_constraints(
        self,
        profile: KnowledgeProfile,
        ctx: PipelineContext,
        allowed_topic_ids: list[str],
        allowed_hints: list[str],
    ) -> KnowledgeProfile:
        allowed_ids = set(allowed_topic_ids)
        hint_set = set(allowed_hints)

        if ctx.organization:
            profile.organization_name = ctx.organization.name
            profile.site_display_name = ctx.organization.name
            profile.organization_aliases = list(ctx.organization.aliases)

        # Identity is inferred deterministically — never trust LLM rewrites.
        if ctx.profile is not None:
            profile.site_subject = ctx.profile.site_subject
            profile.entity_type = ctx.profile.entity_type

        filtered_topics: list[ImportantTopic] = []
        topic_map = {t.id: t for t in ctx.topics}
        allowed_doc_types = {
            r.document_type for r in profile.document_type_rules
        } | {"homepage", "generic_page", "category_page"}
        for topic in profile.important_topics:
            if topic.key not in allowed_ids:
                continue
            src = topic_map.get(topic.key)
            hints = [h for h in topic.preferred_content_hints if h in hint_set]
            if src and not hints:
                hints = [h for h in src.preferred_content_hints if h in hint_set]
            doc_types = [
                d for d in topic.preferred_document_types if d in allowed_doc_types
            ]
            if not doc_types and src:
                doc_types = [
                    d for d in src.preferred_document_types if d in allowed_doc_types
                ]
            if not doc_types:
                doc_types = ["category_page"]
            evidence = " ".join(
                [
                    src.title if src else "",
                    " ".join(src.aliases) if src else "",
                    topic.label,
                ]
            )
            label = ground_topic_label(
                topic.label,
                evidence_text=evidence,
                fallback=(src.title if src else topic.key.replace("_", " ")),
            )
            filtered_topics.append(
                topic.model_copy(
                    update={
                        "label": label,
                        "preferred_content_hints": hints,
                        "preferred_document_types": doc_types,
                    }
                )
            )

        if not filtered_topics and ctx.topics:
            filtered_topics = self._topics_from_discovered(ctx.topics, hint_set)

        profile.important_topics = filtered_topics
        profile.content_hint_rules = [
            r for r in profile.content_hint_rules if r.content_type_hint in hint_set
        ]
        profile, _ = dedupe_topic_aliases(profile)
        return profile

    def _topics_from_discovered(
        self, topics: list[DiscoveredTopic], hint_set: set[str]
    ) -> list[ImportantTopic]:
        out: list[ImportantTopic] = []
        for t in topics:
            hints = [h for h in t.preferred_content_hints if h in hint_set]
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
        return out
