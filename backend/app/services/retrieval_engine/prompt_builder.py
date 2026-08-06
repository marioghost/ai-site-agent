"""Compact prompt builder — pure renderer; consumes prepared plans only."""
from __future__ import annotations

from app.services.context_builder_service import BuiltContext
from app.services.qdrant_service import SearchHit
from app.services.rag_planning.intent_taxonomy import is_overview_intent
from app.services.rag_planning.contracts import AnswerPlan
from app.services.rag_planning.plan_builders import OVERVIEW_SCOPE_INSTRUCTION
from app.services.source_intelligence_constants import PROMPT_TEMPLATE_VERSION
from app.services.system_prompt_defaults import DEFAULT_SYSTEM_PROMPT

__all__ = ("CompactPromptBuilder", "DEFAULT_SYSTEM_PROMPT")


class CompactPromptBuilder:
    VERSION = PROMPT_TEMPLATE_VERSION

    @classmethod
    def build(
        cls,
        *,
        message: str,
        hits: list[SearchHit],
        built_context: BuiltContext | None,
        settings,
        org_name: str = "the organization",
        speech_act_guidance: str | None = None,
        answer_plan: AnswerPlan | None = None,
        additional_guidance: list[str] | None = None,
        intent: str = "",
    ) -> tuple[str, str]:
        _ = org_name, intent

        if built_context and built_context.prompt_text:
            context_block = built_context.prompt_text
        else:
            context_block = cls._format_hits(hits)

        system = cls.resolve_system_prompt(settings)
        parts = [f"Evidence:\n{context_block}"]
        instruction = (speech_act_guidance or "").strip()
        if not instruction and answer_plan and answer_plan.scope_instruction.strip():
            instruction = answer_plan.scope_instruction.strip()
        if not instruction:
            instruction = cls._default_instruction(intent)
        if instruction:
            parts.append(f"Instruction: {instruction}")
        task_lines = cls._task_lines(answer_plan, additional_guidance or [])
        if task_lines:
            parts.append("Task:\n" + "\n".join(f"- {line}" for line in task_lines))
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
        """Trim evidence under budget while preserving instruction/question anchors."""
        combined = len(system) + len(user) + 2
        if combined <= max_prompt:
            return system, user
        marker = "\n\nQuestion:"
        idx = user.rfind(marker)
        if idx < 0:
            return system, user[: max(0, max_prompt - len(system) - 2)]

        head = user[:idx]
        tail = user[idx:]
        instr_marker = "\n\nInstruction:"
        instr_idx = head.rfind(instr_marker)
        if instr_idx >= 0:
            evidence_part = head[:instr_idx]
            instr_part = head[instr_idx:]
        else:
            evidence_part = head
            instr_part = ""

        trimmed_evidence = CompactPromptBuilder._trim_evidence_block(
            evidence_part,
            allowed_len=max(0, max_prompt - len(system) - len(instr_part) - len(tail) - 2),
        )
        return system, trimmed_evidence + instr_part + tail

    @staticmethod
    def _trim_evidence_block(evidence_part: str, allowed_len: int) -> str:
        if len(evidence_part) <= allowed_len:
            return evidence_part
        prefix = "Evidence:\n"
        if not evidence_part.startswith(prefix):
            return evidence_part[:allowed_len]

        raw = evidence_part[len(prefix):]
        blocks = raw.split("\n\n---\n\n") if raw else []
        kept: list[str] = []
        total = len(prefix)
        for block in blocks:
            sep = 0 if not kept else len("\n\n---\n\n")
            if total + sep + len(block) <= allowed_len:
                kept.append(block)
                total += sep + len(block)
                continue
            break
        if not kept:
            return prefix.rstrip()
        return prefix + "\n\n---\n\n".join(kept)

    @staticmethod
    def contains_debug_trace(text: str) -> bool:
        return "DEBUG_TRACE" in (text or "")

    @staticmethod
    def extract_evidence_text(user_prompt: str) -> str:
        if not user_prompt:
            return ""
        prefix = "Evidence:\n"
        if not user_prompt.startswith(prefix):
            return ""
        end_markers = ("\n\nInstruction:", "\n\nQuestion:")
        end_idx = len(user_prompt)
        for marker in end_markers:
            idx = user_prompt.find(marker)
            if idx >= 0:
                end_idx = min(end_idx, idx)
        return user_prompt[len(prefix):end_idx].strip()

    @staticmethod
    def _default_instruction(intent: str) -> str:
        intent_l = (intent or "").lower()
        if is_overview_intent(intent_l):
            return OVERVIEW_SCOPE_INSTRUCTION
        if intent_l in {"contacts_query", "contact"}:
            return "Provide contact information clearly and concisely."
        if intent_l in {"faq_like", "support", "support_query", "faq", "troubleshooting"}:
            return "Answer the specific question directly using the evidence."
        if intent_l in {"listing", "product_query", "category_overview"}:
            return "List the relevant options found in the evidence; do not claim completeness unless stated."
        return ""

    @staticmethod
    def _task_lines(answer_plan: AnswerPlan | None, additional_guidance: list[str]) -> list[str]:
        lines: list[str] = []
        if answer_plan:
            required = ", ".join(answer_plan.required_slot_order)
            if required:
                lines.append(f"Cover first: {required}.")
            optional_keep = list(answer_plan.optional_slot_order[: answer_plan.optional_slot_limit])
            optional_drop = list(answer_plan.optional_slot_order[answer_plan.optional_slot_limit :])
            if optional_keep:
                lines.append(f"If space remains: {', '.join(optional_keep)}.")
            if optional_drop:
                lines.append(f"Drop first under output pressure: {', '.join(optional_drop)}.")
            if answer_plan.target_words or answer_plan.target_sentences:
                budget_parts: list[str] = []
                if answer_plan.target_words:
                    budget_parts.append(f"about {answer_plan.target_words} words")
                if answer_plan.target_sentences:
                    budget_parts.append(f"{answer_plan.target_sentences} short sentences")
                if budget_parts:
                    lines.append(f"Keep it to {' and '.join(budget_parts)}.")
        for entry in additional_guidance:
            text = (entry or "").strip()
            if text:
                lines.append(text)
        return lines
