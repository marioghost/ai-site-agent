"""Shared chat response assembly for streaming and non-streaming paths."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from app.schemas.chat import CacheStatusRead, ChatResponse
from app.schemas.common import ChatSource
from app.schemas.semantic_diagnostics import UnderstandingTraceRead, empty_understanding_trace
from app.schemas.trace import RequestMetadataRead, TimingMetrics, TracePayload
from app.services.feature_flags import semantic_diagnostics_v2_enabled
from app.services.rag_service import CacheStatusInfo, RagResult, RagSource


@dataclass
class DiagnosticsCollector:
    """Collects pipeline diagnostics for both transport modes."""

    request_id: str
    session_id: str
    stages: list[dict] = field(default_factory=list)
    prompt_diagnostics: dict | None = None
    interrupted: bool = False

    def status(self, stage: str, status: str, duration_ms: int | None = None) -> dict:
        # Never leave a stage stuck in running when a later stage completes.
        if status in ("completed", "failed", "skipped"):
            for entry in self.stages:
                if entry.get("status") == "running" and entry.get("stage") != stage:
                    entry["status"] = "completed"
        entry: dict = {"stage": stage, "status": status}
        if duration_ms is not None:
            entry["duration_ms"] = duration_ms
        existing = next((e for e in self.stages if e.get("stage") == stage), None)
        if existing is not None:
            existing.update(entry)
            return existing
        self.stages.append(entry)
        return entry

    def merge_retrieval_stages(self, stages: list[dict]) -> None:
        """Merge document-first retrieval sub-stages into the collector."""
        for stage in stages:
            name = stage.get("stage", "")
            if not name:
                continue
            mapped = {
                "intent_detection": "intent_detection",
                "query_expansion": "query_expansion",
                "chunk_retrieval": "retrieval",
                "document_aggregation": "retrieval",
                "document_scoring": "reranking",
                "source_intelligence": "reranking",
                "document_reranking": "reranking",
                "context_building": "context_building",
            }.get(name, name)
            self.status(
                mapped,
                stage.get("status", "completed"),
                duration_ms=stage.get("duration_ms"),
            )

    def set_prompt_diagnostics(self, diagnostics: dict | None) -> None:
        if diagnostics:
            self.prompt_diagnostics = diagnostics

    def partial_timing(self, **kwargs: int) -> dict:
        return {k: v for k, v in kwargs.items() if v is not None}

    def to_persistence_json(self, response: ChatResponse) -> str:
        metadata = response.metadata
        trace_payload = response.trace
        payload = {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "timing": response.timing.model_dump(),
            "trace": trace_payload.model_dump() if trace_payload else None,
            "metadata": metadata.model_dump() if metadata else None,
            "retrieval_debug": response.retrieval_debug,
            "prompt_diagnostics": response.prompt_diagnostics or self.prompt_diagnostics,
            "cache": response.cache.model_dump() if response.cache else None,
            "error_type": response.error_type,
            "query_intent": metadata.query_intent if metadata else "unknown",
            "applied_knowledge_config": metadata.applied_knowledge_config if metadata else None,
            "pipeline_stages": self.stages,
            "interrupted": self.interrupted,
        }
        if response.understanding_trace is not None:
            payload["understanding_trace"] = response.understanding_trace.model_dump()
        return json.dumps(payload, ensure_ascii=False)


class ChatResponseBuilder:
    """Builds ChatResponse objects from RagResult with a single code path."""

    def __init__(self, settings) -> None:
        self.settings = settings

    def semantic_v2_enabled(self) -> bool:
        return semantic_diagnostics_v2_enabled(self.settings)

    @staticmethod
    def resolve_understanding_trace(
        *,
        existing: UnderstandingTraceRead | None,
        debug: bool,
        semantic_v2_enabled: bool,
    ) -> UnderstandingTraceRead | None:
        """Apply Step 013 stub when flag ON and debug enabled; preserve explicit values."""
        if existing is not None:
            return existing
        if semantic_v2_enabled and debug:
            return empty_understanding_trace()
        return None

    def build_metadata(
        self,
        *,
        request_id: str,
        session_id: str,
        result: RagResult,
        user_ip: str | None,
        user_agent: str | None,
        referrer: str | None,
    ) -> RequestMetadataRead:
        return RequestMetadataRead(
            request_id=request_id,
            session_id=session_id,
            user_ip=user_ip,
            user_agent=user_agent,
            referrer=referrer,
            knowledge_version=self.settings.knowledge_version or 1,
            retrieval_mode=self.settings.retrieval_mode or "hybrid",
            query_intent=result.query_intent,
            applied_knowledge_config=result.applied_knowledge_config,
            created_at=result.created_at,
        )

    @staticmethod
    def build_retrieval_debug(result: RagResult) -> dict | None:
        if not (result.retrieval_debug or result.retrieval_diagnostics):
            return None
        payload: dict = {
            **(result.retrieval_debug or {}),
            **(result.retrieval_diagnostics or {}),
        }
        if result.cache:
            payload["cache"] = asdict(result.cache)
        if result.prompt_diagnostics:
            payload["prompt_diagnostics"] = result.prompt_diagnostics
        return payload

    def from_rag_result(
        self,
        result: RagResult,
        *,
        request_id: str,
        session_id: str,
        user_ip: str | None = None,
        user_agent: str | None = None,
        referrer: str | None = None,
        debug: bool = False,
    ) -> ChatResponse:
        timing = TimingMetrics(
            total_ms=result.total_ms,
            retrieval_ms=result.retrieval_ms,
            generation_ms=result.generation_ms,
            polish_ms=result.polish_ms,
        )
        trace_payload = TracePayload(**result.trace) if result.trace else None
        metadata = self.build_metadata(
            request_id=request_id,
            session_id=session_id,
            result=result,
            user_ip=user_ip,
            user_agent=user_agent,
            referrer=referrer,
        )
        cache = self._cache_read(result.cache)
        sources = [
            ChatSource(title=s.title, url=s.url, source_type=s.source_type, score=s.score)
            for s in result.sources
        ]
        return ChatResponse(
            session_id=session_id,
            request_id=request_id,
            answer=result.answer,
            sources=sources,
            used_context=result.used_context,
            cache_hit=result.cache_hit,
            cache_type=result.cache_type or "none",
            error_type=result.error_type,
            prompt_diagnostics=result.prompt_diagnostics,
            cache=cache,
            timing=timing,
            trace=trace_payload,
            metadata=metadata,
            retrieval_debug=self.build_retrieval_debug(result),
            understanding_trace=self.resolve_understanding_trace(
                existing=None,
                debug=debug,
                semantic_v2_enabled=self.semantic_v2_enabled(),
            ),
        )

    def from_stream_payload(
        self,
        data: dict,
        *,
        request_id: str,
        session_id: str,
        user_ip: str | None = None,
        user_agent: str | None = None,
        referrer: str | None = None,
        debug: bool = False,
    ) -> ChatResponse:
        timing = TimingMetrics(**(data.get("timing") or {}))
        trace_payload = TracePayload(**data["trace"]) if data.get("trace") else None
        metadata_raw = data.get("metadata") or {}
        metadata = RequestMetadataRead(
            request_id=data.get("request_id", request_id),
            session_id=data.get("session_id", session_id),
            user_ip=user_ip,
            user_agent=user_agent,
            referrer=referrer,
            knowledge_version=metadata_raw.get(
                "knowledge_version", self.settings.knowledge_version or 1
            ),
            retrieval_mode=metadata_raw.get(
                "retrieval_mode", self.settings.retrieval_mode or "hybrid"
            ),
            query_intent=metadata_raw.get("query_intent", "unknown"),
            applied_knowledge_config=metadata_raw.get("applied_knowledge_config"),
            created_at=metadata_raw.get("created_at"),
        )
        cache_raw = data.get("cache")
        cache = CacheStatusRead(**cache_raw) if cache_raw else None
        sources = [ChatSource(**s) for s in data.get("sources") or []]
        existing_raw = data.get("understanding_trace")
        existing = (
            UnderstandingTraceRead.model_validate(existing_raw) if existing_raw else None
        )
        return ChatResponse(
            session_id=data.get("session_id", session_id),
            request_id=data.get("request_id", request_id),
            answer=data.get("answer", ""),
            sources=sources,
            used_context=bool(data.get("used_context")),
            cache_hit=bool(data.get("cache_hit")),
            cache_type=data.get("cache_type") or "none",
            error_type=data.get("error_type"),
            prompt_diagnostics=data.get("prompt_diagnostics"),
            cache=cache,
            timing=timing,
            trace=trace_payload,
            metadata=metadata,
            retrieval_debug=data.get("retrieval_debug"),
            understanding_trace=self.resolve_understanding_trace(
                existing=existing,
                debug=debug,
                semantic_v2_enabled=self.semantic_v2_enabled(),
            ),
        )

    def response_dict(self, response: ChatResponse) -> dict:
        return response.model_dump()

    def final_event_payload(self, response: ChatResponse) -> dict:
        return {"response": self.response_dict(response)}

    @staticmethod
    def sources_to_json(sources: list[RagSource] | list[ChatSource]) -> str:
        if not sources:
            return "[]"
        if isinstance(sources[0], RagSource):
            return json.dumps([asdict(s) for s in sources], ensure_ascii=False)
        return json.dumps([s.model_dump() for s in sources], ensure_ascii=False)

    @staticmethod
    def _cache_read(cache: CacheStatusInfo | None) -> CacheStatusRead | None:
        if not cache:
            return None
        return CacheStatusRead(**asdict(cache))
