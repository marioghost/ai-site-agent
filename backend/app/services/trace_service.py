"""Answer trace builder — records each pipeline step for diagnostics."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from app.services.qdrant_service import SearchHit


def new_request_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TraceStep:
    name: str
    status: str = "ok"
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievedChunkTrace:
    title: str
    url: str
    source_type: str
    heading: str = ""
    document_type: str = "generic_page"
    content_type_hint: str = "generic"
    dense_score: float = 0.0
    lexical_score: float = 0.0
    final_score: float = 0.0
    used_in_context: bool = False
    is_canonical: bool = False
    excluded_as_news: bool = False
    text_preview: str = ""


class TraceBuilder:
    """Collects trace steps and chunk metadata for one chat request."""

    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        self.started_at = _now_iso()
        self._t0 = perf_counter()
        self.steps: list[TraceStep] = []
        self._open: dict[str, tuple[TraceStep, float]] = {}
        self.normalized_query: str = ""
        self.expanded_queries: list[str] = []
        self.retrieved_chunks: list[RetrievedChunkTrace] = []
        self.retrieval_mode: str = "hybrid"
        self.knowledge_version: int = 1
        self.query_intent: str = "unknown"

    def begin(self, name: str, details: dict[str, Any] | None = None) -> None:
        step = TraceStep(name=name, started_at=_now_iso(), details=details or {})
        self._open[name] = (step, perf_counter())

    def end(self, name: str, status: str = "ok", details: dict[str, Any] | None = None) -> None:
        entry = self._open.pop(name, None)
        if entry is None:
            return
        step, t_start = entry
        step.status = status
        step.finished_at = _now_iso()
        step.duration_ms = int((perf_counter() - t_start) * 1000)
        if details:
            step.details.update(details)
        self.steps.append(step)

    def skip(self, name: str, reason: str = "") -> None:
        self.steps.append(
            TraceStep(
                name=name,
                status="skipped",
                started_at=_now_iso(),
                finished_at=_now_iso(),
                duration_ms=0,
                details={"reason": reason} if reason else {},
            )
        )

    def set_chunks(self, hits: list[SearchHit], used_urls: set[str] | None = None) -> None:
        used = used_urls or set()
        self.retrieved_chunks = []
        for h in hits:
            preview = (h.text or "")[:280]
            if len(h.text or "") > 280:
                preview += "…"
            self.retrieved_chunks.append(
                RetrievedChunkTrace(
                    title=h.title or h.url,
                    url=h.url,
                    source_type=h.source_type or "page",
                    heading=h.heading or "",
                    document_type=h.document_type or "generic_page",
                    content_type_hint=h.content_type_hint or "generic",
                    dense_score=round(h.dense_score, 4),
                    lexical_score=round(h.lexical_score, 4),
                    final_score=round(h.final_score or h.score, 4),
                    used_in_context=bool(used and h.url in used),
                    is_canonical=bool(h.is_canonical),
                    excluded_as_news=bool(h.excluded_as_news),
                    text_preview=preview,
                )
            )

    def total_ms(self) -> int:
        return int((perf_counter() - self._t0) * 1000)

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "steps": [asdict(s) for s in self.steps],
            "retrieved_chunks": [asdict(c) for c in self.retrieved_chunks],
        }

    def to_storage_json(self) -> dict[str, str]:
        return {
            "trace_steps_json": json.dumps([asdict(s) for s in self.steps], ensure_ascii=False),
            "selected_chunks_json": json.dumps(
                [asdict(c) for c in self.retrieved_chunks], ensure_ascii=False
            ),
            "expanded_queries_json": json.dumps(self.expanded_queries, ensure_ascii=False),
        }
