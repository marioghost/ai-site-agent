"""Context builder v3 — full article content, chunk fusion, token budget."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.models.source import Source
from app.services.context_builder_service import BuiltContext, PageContextBlock
from app.services.llm_mode_service import effective_generation_settings
from app.services.retrieval_engine.chunk_fusion import ChunkFusionService
from app.services.retrieval_engine.context_budget import ContextBudgetService
from app.services.retrieval_engine.content_sanitizer import (
    clean_context_text,
    extract_lead_paragraphs,
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

  def to_dict(self) -> dict:
    return {
      "token_budget": self.token_budget,
      "selected_blocks": self.selected_blocks,
      "rejected_blocks": self.rejected_blocks,
      "fusion_ms": self.fusion_ms,
      "build_ms": self.build_ms,
    }


class RetrievalContextBuilder:
  """Build LLM context from fused chunks and source main content."""

  def __init__(self, db: Session | None = None) -> None:
    self.db = db
    self._fusion = ChunkFusionService()

  def build(
    self,
    hits: list[SearchHit],
    *,
    settings: Settings,
    user_message: str = "",
    system_prompt_estimate: str = "",
    max_pages: int | None = None,
    max_chunks_per_page: int | None = None,
  ) -> tuple[BuiltContext, ContextBuildReport]:
    from time import perf_counter

    t0 = perf_counter()
    mode = (getattr(settings, "context_builder_mode", None) or "full_content").lower()
    max_pages = max_pages or int(getattr(settings, "max_pages_in_context", 3) or 3)
    max_chunks = max_chunks_per_page or int(getattr(settings, "max_chunks_per_page", 2) or 2)
    merge_enabled = bool(getattr(settings, "chunk_merge_enabled", True))

    budget = ContextBudgetService.compute(
      settings,
      system_prompt=system_prompt_estimate,
      user_message=user_message,
    )
    max_total_chars = ContextBudgetService.tokens_to_chars(budget.available_context_tokens)
    eff = effective_generation_settings(settings)
    profile_chars = int(eff.get("max_chars_per_source") or 0)
    settings_chars = int(getattr(settings, "max_chars_per_source", 800) or 800)
    # Prefer mode profile cap when set; never exceed page share of total budget.
    max_chars_per_source = profile_chars or settings_chars
    max_chars_per_source = min(
      max_chars_per_source,
      max(400, max_total_chars // max(1, max_pages)),
    )

    if not hits:
      return (
        BuiltContext(blocks=[], prompt_text="", total_chunks=0, page_count=0),
        ContextBuildReport(token_budget=budget.to_dict()),
      )

    source_meta = self._load_sources({h.source_id for h in hits})
    grouped = self._fusion.group_by_source(hits)
    page_scores = sorted(
      ((sid, max(h.final_score or h.score for h in grp)) for sid, grp in grouped.items()),
      key=lambda x: -x[1],
    )

    blocks: list[PageContextBlock] = []
    report = ContextBuildReport(token_budget=budget.to_dict())
    total_chars = 0
    total_chunks = 0

    for sid, page_score in page_scores:
      if len(blocks) >= max_pages:
        report.rejected_blocks.append(
          {"source_id": sid, "reason": "page_limit", "score": page_score}
        )
        continue
      group = grouped[sid]
      fused = self._fusion.fuse_source_chunks(
        group,
        merge_neighbours=merge_enabled,
        max_chunks=max(max_chunks, 4 if merge_enabled else max_chunks),
      )
      meta = source_meta.get(sid, {})
      text = self._compose_content(
        fused,
        meta,
        mode=mode,
        max_chars=max_chars_per_source,
      )
      if not text.strip():
        report.rejected_blocks.append(
          {"source_id": sid, "reason": "empty_content", "score": page_score}
        )
        continue
      rep = fused[0]
      header_len = len(rep.title or "") + len(rep.url or "") + 80
      piece_len = header_len + len(text)
      if total_chars + piece_len > max_total_chars and blocks:
        report.rejected_blocks.append(
          {"source_id": sid, "reason": "token_budget", "score": page_score}
        )
        continue
      block = PageContextBlock(
        source_id=sid,
        title=rep.title or rep.url,
        url=rep.url,
        chunks_used=len(fused),
        text=text,
        score=page_score,
        content_categories=sorted(
          {getattr(h, "content_category", "generic") or "generic" for h in fused}
        ),
        document_type=getattr(rep, "document_type", "generic_page") or "generic_page",
        page_role=getattr(rep, "page_role", "generic") or "generic",
        source_summary=meta.get("summary", "") or getattr(rep, "source_profile_summary", "") or "",
      )
      blocks.append(block)
      total_chunks += len(fused)
      total_chars += piece_len
      report.selected_blocks.append(
        {
          "source_id": sid,
          "url": block.url,
          "chunks": len(fused),
          "chars": len(text),
          "raw_chars": meta.get("raw_chars", 0),
          "cleaned_chars": len(text),
          "score": round(page_score, 4),
          "mode": mode,
          "selection_reason": getattr(rep, "selection_reason", "") or "",
        }
      )

    prompt_text = self._format_prompt(blocks)
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

  def _load_sources(self, source_ids: set[int]) -> dict[int, dict]:
    if not self.db or not source_ids:
      return {}
    rows = self.db.execute(select(Source).where(Source.id.in_(source_ids))).scalars().all()
    return {
      s.id: {
        "main_content": (s.main_content_text or "").strip(),
        "summary": (s.llm_summary or "").strip(),
        "boilerplate_ratio": float(s.boilerplate_ratio or 0.0),
        "document_type": s.document_type or "generic_page",
      }
      for s in rows
    }

  def _compose_content(
    self,
    fused: list[SearchHit],
    meta: dict,
    *,
    mode: str,
    max_chars: int,
  ) -> str:
    main_content = strip_ui_junk(meta.get("main_content", ""))
    summary = strip_ui_junk(meta.get("summary", ""))
    meta["raw_chars"] = len(main_content)
    chunk_segments: list[str] = []
    for hit in fused:
      heading = strip_ui_junk((hit.heading or "").strip())
      body = strip_ui_junk((hit.text or "").strip())
      if heading and body and heading.lower() not in body.lower()[:80]:
        chunk_segments.append(f"## {heading}\n{body}")
      elif body:
        chunk_segments.append(body)
      elif heading:
        chunk_segments.append(f"## {heading}")

    chunk_text = clean_context_text(
      ChunkFusionService.merge_text_segments(chunk_segments),
      max_chars=max_chars,
    )
    parts: list[str] = []

    if summary and summary.lower() not in (chunk_text or "").lower()[:120]:
      parts.append(f"Summary: {summary[: min(500, len(summary))]}")

    if mode == "full_content" and main_content:
      excerpt = self._extract_relevant_excerpt(main_content, chunk_text, max_chars)
      excerpt = clean_context_text(excerpt, max_chars=max_chars)
      if excerpt and len(excerpt) >= 200:
        parts.append(excerpt)
      elif main_content:
        lead = extract_lead_paragraphs(main_content, max_chars)
        if lead:
          parts.append(lead)
      if chunk_text and len(chunk_text) >= 120:
        if not parts or chunk_text[:80] not in parts[-1][:200]:
          parts.append(chunk_text[: max(300, max_chars // 3)])
    elif chunk_text:
      parts.append(chunk_text[:max_chars])
    elif main_content:
      parts.append(extract_lead_paragraphs(main_content, max_chars))
    else:
      return ""

    combined = "\n\n".join(p for p in parts if p.strip())
    return clean_context_text(combined, max_chars=max_chars)

  @staticmethod
  def _extract_relevant_excerpt(main_content: str, chunk_hint: str, max_chars: int) -> str:
    if len(main_content) <= max_chars:
      return main_content
    if not chunk_hint:
      return main_content[:max_chars]
    hint_words = {w.lower() for w in chunk_hint.split() if len(w) > 3}
    if not hint_words:
      return main_content[:max_chars]
    best_start = 0
    best_score = -1
    step = max(200, max_chars // 4)
    for start in range(0, max(1, len(main_content) - max_chars), step):
      window = main_content[start : start + max_chars]
      score = sum(1 for w in hint_words if w in window.lower())
      if score > best_score:
        best_score = score
        best_start = start
    return main_content[best_start : best_start + max_chars]

  @staticmethod
  def _format_prompt(blocks: list[PageContextBlock]) -> str:
    parts: list[str] = []
    for i, block in enumerate(blocks, start=1):
      header = f"Source {i}:\nTitle: {block.title}\nURL: {block.url}"
      if block.document_type and block.document_type != "generic_page":
        header += f"\nType: {block.document_type}"
      # Summary lives in Content via _compose_content — do not duplicate here.
      parts.append(f"{header}\nContent:\n{block.text}")
    return "\n\n---\n\n".join(parts)
