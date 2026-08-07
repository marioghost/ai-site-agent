"""Budget-aware packing of selected evidence."""
from __future__ import annotations

from app.models.settings import Settings
from app.services.evidence_planning.types import SelectedEvidence
from app.services.llm_mode_service import effective_generation_settings
from app.services.retrieval_engine.context_budget import ContextBudgetService


def pack_selected_evidence(
    selected: list[SelectedEvidence],
    *,
    settings: Settings,
    system_prompt: str,
    user_message: str,
    has_instruction: bool = False,
) -> tuple[list[SelectedEvidence], list[dict], bool]:
    if not selected:
        return [], [], False

    budget = ContextBudgetService.compute(
        settings,
        system_prompt=system_prompt,
        user_message=user_message,
        user_framing_tokens=ContextBudgetService.estimate_user_framing_tokens(
            user_message,
            has_instruction=has_instruction,
        ),
    )
    max_chars = ContextBudgetService.tokens_to_chars(budget.available_context_tokens)
    eff = effective_generation_settings(settings)
    max_pages = int(eff.get("max_sources_in_prompt") or getattr(settings, "max_sources_in_prompt", 3) or 3)
    per_source_cap = max(400, max_chars // max(1, max_pages))

    kept: list[SelectedEvidence] = []
    decisions: list[dict] = []
    total = 0
    truncated = False

    for item in sorted(
        selected,
        key=lambda s: (
            -float(s.candidate.authority_fitness or 0.0),
            -float(s.marginal_value or 0.0),
            s.final_order,
        ),
    ):
        text = item.candidate.section_text or item.candidate.text
        piece = min(len(text), per_source_cap) + len(item.candidate.title) + len(item.candidate.url) + 80
        if len(kept) >= max_pages:
            decisions.append(
                {
                    "url": item.candidate.url,
                    "reason": "page_limit",
                    "marginal_value": item.marginal_value,
                }
            )
            truncated = True
            continue
        if total + piece > max_chars and kept:
            if _is_critical(item):
                while kept and total + piece > max_chars:
                    dropped = kept.pop()
                    total -= _piece_len(dropped, per_source_cap)
                    decisions.append(
                        {
                            "url": dropped.candidate.url,
                            "reason": "budget_trade_for_critical",
                            "marginal_value": dropped.marginal_value,
                        }
                    )
                    truncated = True
            if total + piece > max_chars:
                decisions.append(
                    {
                        "url": item.candidate.url,
                        "reason": "token_budget",
                        "marginal_value": item.marginal_value,
                    }
                )
                truncated = True
                continue
        kept.append(item)
        total += piece

    # Prompt order follows fitness so the model sees strongest evidence first.
    for idx, item in enumerate(kept):
        item.final_order = idx

    return kept, decisions, truncated


def _piece_len(item: SelectedEvidence, cap: int) -> int:
    text = item.candidate.section_text or item.candidate.text
    return min(len(text), cap) + len(item.candidate.title) + len(item.candidate.url) + 80


def _is_critical(item: SelectedEvidence) -> bool:
    return bool(item.aspects_new) and item.candidate.authority_fitness >= 0.55
