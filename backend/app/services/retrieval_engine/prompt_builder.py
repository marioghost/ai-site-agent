"""Compact prompt builder — admin system prompt owns behavior.

User message is structural only: Sources + optional typed Instruction + Question.
No hardcoded answer style, refuse/qualify wording, or intent prose templates.
"""
from __future__ import annotations

from app.services.context_builder_service import BuiltContext
from app.services.qdrant_service import SearchHit
from app.services.source_intelligence_constants import PROMPT_TEMPLATE_VERSION
from app.services.system_prompt_defaults import DEFAULT_SYSTEM_PROMPT

# Re-export for callers that import from prompt_builder.
__all__ = ("CompactPromptBuilder", "DEFAULT_SYSTEM_PROMPT", "OVERVIEW_INTENTS")

# Intent taxonomy used by callers/tests — not prompt prose.
OVERVIEW_INTENTS = frozenset({
    "entity_overview",
    "site_overview",
    "organization_overview",
    "topic_overview",
    "category_overview",
})


class CompactPromptBuilder:
    VERSION = PROMPT_TEMPLATE_VERSION

    @classmethod
    def build(
        cls,
        *,
        message: str,
        hits: list[SearchHit],
        built_context: BuiltContext | None,
        intent: str,
        settings,
        org_name: str = "the organization",
        speech_act_guidance: str | None = None,
    ) -> tuple[str, str]:
        _ = intent
        _ = org_name

        if built_context and built_context.prompt_text:
            context_block = built_context.prompt_text
        else:
            context_block = cls._format_hits(hits)

        system = cls.resolve_system_prompt(settings)
        parts = [f"Sources:\n{context_block}"]
        instruction = (speech_act_guidance or "").strip()
        if instruction:
            parts.append(f"Instruction: {instruction}")
        parts.append(f"Question: {message.strip()}")
        parts.append("Answer:")
        user = "\n\n".join(parts)
        return system, user

    @classmethod
    def resolve_system_prompt(cls, settings) -> str:
        """Admin system prompt is the primary agent control surface."""
        custom = (getattr(settings, "system_prompt", None) or "").strip()
        return custom or DEFAULT_SYSTEM_PROMPT

    @staticmethod
    def _format_hits(hits: list[SearchHit]) -> str:
        parts: list[str] = []
        seen: set[str] = set()
        for i, hit in enumerate(hits, start=1):
            url = (hit.url or "").strip()
            if url in seen:
                continue
            seen.add(url)
            title = hit.title or url
            snippet = (hit.text or "").strip()
            header = f"Source {i}: {title}\nURL: {url}"
            parts.append(f"{header}\n{snippet}")
        return "\n\n".join(parts)

    @staticmethod
    def truncate_prompts(system: str, user: str, max_prompt: int) -> tuple[str, str]:
        """Trim source content under budget; never drop Question/Answer anchors."""
        combined = len(system) + len(user) + 2
        if combined <= max_prompt:
            return system, user
        overflow = combined - max_prompt
        marker = "\n\nQuestion:"
        idx = user.rfind(marker)
        if idx >= 0:
            head = user[:idx]
            tail = user[idx:]
            instr_marker = "\n\nInstruction:"
            instr_idx = head.rfind(instr_marker)
            if instr_idx >= 0:
                sources = head[:instr_idx]
                keep_tail = head[instr_idx:]
                keep = max(200, len(sources) - overflow)
                return system, sources[:keep].rstrip() + keep_tail + tail
            keep = max(200, len(head) - overflow)
            return system, head[:keep].rstrip() + tail
        return system, user[: max(200, len(user) - overflow)]

    @staticmethod
    def contains_debug_trace(text: str) -> bool:
        markers = ("trace_steps", "retrieval_debug", "score_breakdown", "===== DEBUG")
        lower = text.lower()
        return any(m.lower() in lower for m in markers)
