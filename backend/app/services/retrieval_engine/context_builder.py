"""Context builder — serializes evidence selected by EvidencePlanner."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.models.source import Source
from app.services.context_builder_service import BuiltContext, PageContextBlock
from app.services.evidence_planning.types import EvidencePlan, SelectedEvidence
from app.services.llm_mode_service import effective_generation_settings
from app.services.llm_options_service import estimate_tokens
from app.services.retrieval_engine.chunk_fusion import ChunkFusionService
from app.services.retrieval_engine.context_budget import ContextBudgetService
from app.services.retrieval_engine.content_sanitizer import (
    clean_context_text,
    extract_lead_paragraphs,
    extract_overview_excerpt,
    dedupe_near_duplicate_text,
    strip_ui_junk,
)
from app.services.qdrant_service import SearchHit


@dataclass
class ContextBuildReport:
  token_budget: dict
  selected_blocks: list[dict] = field(default_factory=list)
  rejected_blocks: list[dict] = field(default_factory=list)
  fusion_ms: int = 0
  build_ms: int = 0
  evidence_plan: dict | None = None

  def to_dict(self) -> dict:
    return {
      "token_budget": self.token_budget,
      "selected_blocks": self.selected_blocks,
      "rejected_blocks": self.rejected_blocks,
      "fusion_ms": self.fusion_ms,
      "build_ms": self.build_ms,
      "evidence_plan": self.evidence_plan,
    }


class RetrievalContextBuilder:
  """Serialize planner-selected evidence into LLM context."""

  def __init__(self, db: Session | None = None) -> None:
    self.db = db
    self._fusion = ChunkFusionService()

  def build_from_plan(
    self,
    evidence_plan: EvidencePlan,
    *,
    settings: Settings,
    user_message: str = "",
    system_prompt_estimate: str = "",
  ) -> tuple[BuiltContext, ContextBuildReport]:
    from time import perf_counter

    t0 = perf_counter()
    budget = ContextBudgetService.compute(
      settings,
      system_prompt=system_prompt_estimate,
      user_message=user_message,
    )
    eff = effective_generation_settings(settings)
    per_source_chars = int(eff.get("max_chars_per_source") or getattr(settings, "max_chars_per_source", 800) or 800)
    source_meta = self._load_sources({s.candidate.source_id for s in evidence_plan.selected})

    blocks: list[PageContextBlock] = []
    report = ContextBuildReport(
      token_budget=budget.to_dict(),
      evidence_plan=evidence_plan.to_diagnostics(),
    )
    assembled: list[str] = []
    total_chunks = 0

    for item in evidence_plan.selected:
      cand = item.candidate
      meta = source_meta.get(cand.source_id, {})
      text = self._compose_block_text(
        cand.text,
        section_text=cand.section_text,
        summary=meta.get("summary", ""),
        page_role=cand.page_role,
        max_chars=per_source_chars,
      )
      if not text.strip():
        report.rejected_blocks.append({"source_id": cand.source_id, "reason": "empty_content"})
        continue
      if any(dedupe_near_duplicate_text(prev, text) for prev in assembled):
        report.rejected_blocks.append({"source_id": cand.source_id, "reason": "near_duplicate"})
        continue

      block = PageContextBlock(
        source_id=cand.source_id,
        title=cand.title,
        url=cand.url,
        chunks_used=1,
        text=text,
        score=cand.authority_fitness,
        content_categories=["generic"],
        document_type=cand.document_type,
        page_role=cand.page_role,
        source_summary=meta.get("summary", ""),
      )
      blocks.append(block)
      assembled.append(text)
      total_chunks += 1
      report.selected_blocks.append(
        {
          "source_id": cand.source_id,
          "url": cand.url,
          "chars": len(text),
          "token_estimate": estimate_tokens(len(text)),
          "authority_fitness": round(cand.authority_fitness, 4),
          "fitness_band": cand.fitness_band,
          "marginal_value": round(item.marginal_value, 4),
          "selection_reason": item.selection_reason,
          "aspects_new": list(item.aspects_new),
          "final_order": item.final_order,
          "broad_injected": cand.broad_injected,
        }
      )

    for rej in evidence_plan.rejected[:20]:
      report.rejected_blocks.append(rej.to_dict())

    prompt_text = self._format_prompt(blocks)
    report.token_budget["estimated_context_chars"] = len(prompt_text)
    report.token_budget["estimated_context_tokens"] = estimate_tokens(len(prompt_text))
    report.build_ms = int((perf_counter() - t0) * 1000)
    return (
      BuiltContext(
        blocks=blocks,
        prompt_text=prompt_text,
        total_chunks=total_chunks,
        page_count=len(blocks),
      ),
      report,
    )

  def build(
    self,
    hits: list[SearchHit],
    *,
    settings: Settings,
    user_message: str = "",
    system_prompt_estimate: str = "",
    evidence_plan: EvidencePlan | None = None,
    **kwargs,
  ) -> tuple[BuiltContext, ContextBuildReport]:
    if evidence_plan is not None:
      return self.build_from_plan(
        evidence_plan,
        settings=settings,
        user_message=user_message,
        system_prompt_estimate=system_prompt_estimate,
      )
    return self._build_from_hits(
      hits,
      settings=settings,
      user_message=user_message,
      system_prompt_estimate=system_prompt_estimate,
      max_pages=int(kwargs.get("max_pages", 3) or 3),
    )

  def _build_from_hits(
    self,
    hits: list[SearchHit],
    *,
    settings: Settings,
    user_message: str = "",
    system_prompt_estimate: str = "",
    max_pages: int = 3,
  ) -> tuple[BuiltContext, ContextBuildReport]:
    from time import perf_counter

    t0 = perf_counter()
    budget = ContextBudgetService.compute(
      settings,
      system_prompt=system_prompt_estimate,
      user_message=user_message,
    )
    eff = effective_generation_settings(settings)
    per_source_chars = int(eff.get("max_chars_per_source") or getattr(settings, "max_chars_per_source", 800) or 800)
    blocks: list[PageContextBlock] = []
    report = ContextBuildReport(token_budget=budget.to_dict())
    seen_urls: set[str] = set()

    for hit in hits[:max_pages]:
      url = (hit.url or "").strip()
      if url in seen_urls:
        continue
      seen_urls.add(url)
      text = self._compose_block_text(
        hit.text or "",
        section_text="",
        summary=getattr(hit, "source_profile_summary", "") or "",
        page_role=getattr(hit, "page_role", "") or "",
        max_chars=per_source_chars,
      )
      if not text.strip():
        continue
      blocks.append(
        PageContextBlock(
          source_id=hit.source_id,
          title=hit.title or url,
          url=url,
          chunks_used=1,
          text=text,
          score=float(hit.final_score or hit.score or 0.0),
          content_categories=["generic"],
          document_type=hit.document_type or "generic_page",
          page_role=getattr(hit, "page_role", "") or "",
          source_summary="",
        )
      )
      report.selected_blocks.append({"url": url, "chars": len(text)})

    prompt_text = self._format_prompt(blocks)
    report.build_ms = int((perf_counter() - t0) * 1000)
    return (
      BuiltContext(
        blocks=blocks,
        prompt_text=prompt_text,
        total_chunks=len(blocks),
        page_count=len(blocks),
      ),
      report,
    )

  def _load_sources(self, source_ids: set[int]) -> dict[int, dict]:
    if not self.db or not source_ids:
      return {}
    rows = self.db.execute(select(Source).where(Source.id.in_(source_ids))).scalars().all()
    return {
      s.id: {
        "summary": (s.llm_summary or "").strip(),
      }
      for s in rows
    }

  @staticmethod
  def _compose_block_text(
    raw_text: str,
    *,
    section_text: str,
    summary: str,
    page_role: str,
    max_chars: int,
  ) -> str:
    base_text = section_text or raw_text
    prefer_overview = page_role in {"organization_overview", "service_overview", "documentation", "faq"}
    if prefer_overview:
      body = extract_overview_excerpt(
        base_text,
        max_chars=max_chars,
        chunk_hint=section_text[:180] if section_text else "",
        prefer_identity=page_role != "faq",
      )
    else:
      body = extract_lead_paragraphs(base_text, max_chars)
    body = clean_context_text(body or base_text, max_chars=max_chars)

    summary_clean = strip_ui_junk(summary or "")
    # Skip rule-based SI template summaries — they burn tokens without facts.
    template_markers = (
        "this page describes",
        "this page contains",
        "this page provides",
        "this page is a",
        "this page offers",
    )
    if summary_clean and any(summary_clean.lower().startswith(m) for m in template_markers):
        summary_clean = ""
    if (
      summary_clean
      and body
      and not dedupe_near_duplicate_text(body, summary_clean)
      and summary_clean.lower() not in body.lower()[:180]
    ):
      remaining = max_chars - len(body) - len("\n\nPage summary:\n")
      if remaining > 120:
        body = f"{body}\n\nPage summary:\n{summary_clean[:remaining].strip()}"
    return body[:max_chars]

  @staticmethod
  def _format_prompt(blocks: list[PageContextBlock]) -> str:
    parts: list[str] = []
    for i, block in enumerate(blocks, start=1):
      header = f"Source {i}:\nTitle: {block.title}\nURL: {block.url}"
      # Type/Role stay in diagnostics; omit from prompt to free evidence tokens.
      parts.append(f"{header}\nEvidence excerpt:\n{block.text}")
    return "\n\n---\n\n".join(parts)
