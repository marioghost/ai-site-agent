"""Stage 7 — constrained LLM refinement (labels/descriptions only)."""
from __future__ import annotations

import json
import re
from copy import deepcopy

from app.models.settings import Settings
from app.schemas.knowledge_profile import ImportantTopic, KnowledgeProfile
from app.services.knowledge_profile_generation.alias_utils import dedupe_topic_aliases
from app.services.knowledge_profile_generation.lexical_grounding import labels_overlap
from app.services.knowledge_profile_generation.models import (
    DetectedOrganization,
    DiscoveredTopic,
    PipelineContext,
)
from app.services.knowledge_profile_generation.site_identity import (
    ground_topic_label,
    is_grounded_in_evidence,
)
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
            "identity_evidence": [
                str(text)[:350]
                for text in ctx.extras.get("identity_evidence_snippets", [])[:6]
            ],
            "topic_candidates": [
                {
                    "id": t.id,
                    "title": t.title,
                    "page_count": t.page_count,
                }
                for t in ctx.topics
            ],
            "allowed_topic_ids": allowed_topic_ids,
        }

        system = (
            "You refine site identity and topic selection from supplied evidence. "
            "Return ONLY compact JSON with this exact shape: "
            '{"site_subject":"...", "entity_type":"...", '
            '"topic_keys":["existing-id"], "topic_labels":{"existing-id":"grounded label"}}. '
            "RULES: "
            "1) Do NOT change organization_name. "
            "You MAY improve site_subject and entity_type only when identity_evidence "
            "or recurring topic_candidates support the result; describe the site's "
            "enduring identity, never episodic or page-local content. "
            "entity_type must be the most specific enduring kind supported by the "
            "evidence; do not keep a generic type when the corpus clearly supports a "
            "more specific one. Return entity_type as a concise entity class, not a "
            "relationship phrase or page-content type. "
            "2) Do NOT invent new important_topics keys — only use allowed_topic_ids. "
            "3) Do NOT reference content hints outside allowed_content_hints. "
            "4) You MAY improve topic labels only using words that appear in topic_candidates. "
            "Keep a compact set of semantically distinct, enduring knowledge areas; "
            "omit duplicate formulations, document formats, and temporary events. "
            "Prefer 4–8 distinct topics when that many are supported; do not collapse "
            "unrelated areas merely to shorten the list. "
            "5) Do NOT replace labels with generic English like 'About the organization'."
        )
        user = json.dumps(summary, ensure_ascii=False)[:6000]

        try:
            ollama = OllamaService(timeout=settings.ollama_generation_timeout_seconds)
            raw = ollama.chat(
                settings.llm_model,
                system,
                user,
                temperature=0.15,
                max_tokens=1536,
            )
        except OllamaError as exc:
            return ctx.profile, {"llm_tokens": 0, "llm_used": False, "llm_error": str(exc)}

        cleaned = self._json_object(raw.content)

        try:
            data = json.loads(cleaned)
            if not isinstance(data, dict):
                raise ValueError("LLM response is not an object")
            refined = self._apply_patch(ctx.profile, data)
        except (json.JSONDecodeError, ValueError, TypeError):
            return ctx.profile, {
                "llm_tokens": raw.prompt_eval_count + raw.eval_count,
                "llm_used": False,
                "llm_parse_error": True,
            }

        refined = self._enforce_constraints(refined, ctx, allowed_topic_ids, allowed_hints)
        return refined, {
            "llm_tokens": raw.prompt_eval_count + raw.eval_count,
            "llm_used": True,
        }

    @staticmethod
    def _json_object(content: str) -> str:
        cleaned = (content or "").strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        return cleaned[start : end + 1] if start >= 0 and end > start else cleaned

    @staticmethod
    def _apply_patch(profile: KnowledgeProfile, data: dict) -> KnowledgeProfile:
        refined = deepcopy(profile)
        if isinstance(data.get("site_subject"), str):
            refined.site_subject = data["site_subject"].strip()[:160]
        if isinstance(data.get("entity_type"), str):
            refined.entity_type = data["entity_type"].strip()[:80]

        labels = data.get("topic_labels")
        labels = labels if isinstance(labels, dict) else {}
        requested = data.get("topic_keys")
        requested = requested if isinstance(requested, list) else []
        topics_by_key = {topic.key: topic for topic in refined.important_topics}
        selected: list[ImportantTopic] = []
        seen: set[str] = set()
        for raw_key in requested:
            key = str(raw_key)
            if key in seen or key not in topics_by_key:
                continue
            seen.add(key)
            topic = topics_by_key[key]
            proposed = labels.get(key)
            if isinstance(proposed, str) and proposed.strip():
                topic = topic.model_copy(update={"label": proposed.strip()[:80]})
            selected.append(topic)
        if selected:
            refined.important_topics = selected
        return refined

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

        # Organization is deterministic. LLM identity refinements survive only
        # when their vocabulary is grounded in the selected site evidence.
        if ctx.profile is not None:
            identity_evidence = list(
                ctx.extras.get("identity_evidence_snippets", [])
            )
            if not is_grounded_in_evidence(
                profile.site_subject,
                identity_evidence,
            ):
                profile.site_subject = ctx.profile.site_subject
            if not is_grounded_in_evidence(
                profile.entity_type,
                identity_evidence,
                minimum_token_coverage=0.5,
            ):
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
                ]
            )
            label = ground_topic_label(
                topic.label,
                evidence_text=evidence,
                fallback=(src.title if src else topic.key.replace("_", " ")),
            )
            if src and not is_grounded_in_evidence(
                label,
                [evidence],
                minimum_token_coverage=0.5,
            ):
                label = src.title
            if any(labels_overlap(label, item.label) for item in filtered_topics):
                continue
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
