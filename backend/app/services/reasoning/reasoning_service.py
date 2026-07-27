"""ReasoningService — stateless reasoning seam (RFC-100 Steps 039–043).

Step 039: passthrough facade over Rag.
Step 041: when Evidence Assembly is also enabled, Reasoning owns the order of
legacy RPS adapters (prepare → assemble → finalize) and injects the result into
Rag so retrieval/LLM each run once. Language remains in Rag.
Step 043: advisory evidence-sufficiency assessment — does not change answers.

Does not store knowledge, mutate Epistemic Memory, or render final language.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.chat_response_builder import DiagnosticsCollector
from app.services.feature_flags import evidence_assembly_enabled
from app.services.rag_service import RagResult, RagService
from app.services.rag_streaming import RagStreamingService
from app.services.reasoning.evidence_sufficiency import (
    assess_evidence_sufficiency,
    build_reasoning_diagnostics,
)
from app.services.reasoning.types import (
    REASONING_PATH_SERVICE,
    ReasoningRequest,
    ReasoningResult,
)
from app.services.retrieval_pipeline_service import (
    RETRIEVAL_COORDINATOR_REASONING,
    PipelineResult,
    RetrievalPipelineService,
)
from app.services.trace_service import TraceBuilder


class ReasoningService:
    """Own reasoning responsibility; coordinate evidence when both flags ON.

    Stateless: no instance caches of answers, claims, or tensions. Constructed
    per request (or reused only as a thin holder of Session/Settings deps).
    """

    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._rag = RagService(db, settings)
        self._streaming = RagStreamingService(self._rag)

    def run(self, request: ReasoningRequest) -> ReasoningResult:
        """Execute reasoning for one turn.

        Reasoning ON + EA OFF: Rag passthrough (RPS→DFP).
        Reasoning ON + EA ON: Reasoning orders RPS adapters; Rag runs language.
        Step 043: sufficiency assessed after legacy answer — advisory only.
        """
        provider = (
            self._coordinate_pipeline if evidence_assembly_enabled() else None
        )
        legacy = self._rag.answer(
            request.message,
            request.session_id,
            request_id=request.request_id,
            user_ip=request.user_ip,
            user_agent=request.user_agent,
            referrer=request.referrer,
            debug=request.debug,
            bypass_cache=request.bypass_cache,
            pipeline_provider=provider,
        )
        return self._wrap(legacy)

    def answer(
        self,
        message: str,
        session_id: str | None,
        *,
        request_id: str,
        user_ip: str | None = None,
        user_agent: str | None = None,
        referrer: str | None = None,
        debug: bool = False,
        bypass_cache: bool = False,
    ) -> RagResult:
        """Convenience API matching Executive/Rag signatures — returns RagResult."""
        result = self.run(
            ReasoningRequest(
                message=message,
                session_id=session_id,
                request_id=request_id,
                user_ip=user_ip,
                user_agent=user_agent,
                referrer=referrer,
                debug=debug,
                bypass_cache=bypass_cache,
            )
        )
        return result.as_rag_result()

    def answer_stream(
        self,
        message: str,
        session_id: str | None,
        *,
        request_id: str,
        collector: DiagnosticsCollector | None = None,
        user_ip: str | None = None,
        user_agent: str | None = None,
        referrer: str | None = None,
        debug: bool = False,
        bypass_cache: bool = False,
    ) -> Iterator[tuple[str, dict]]:
        """Streaming path — same coordinator rules; stamp advisory sufficiency on final."""
        provider = (
            self._coordinate_pipeline if evidence_assembly_enabled() else None
        )
        for event, data in self._streaming.iter_events(
            message,
            session_id,
            request_id=request_id,
            collector=collector,
            user_ip=user_ip,
            user_agent=user_agent,
            referrer=referrer,
            debug=debug,
            bypass_cache=bypass_cache,
            pipeline_provider=provider,
        ):
            if event == "final" and isinstance(data, dict):
                data = self._stamp_stream_final(data)
            yield event, data

    def _coordinate_pipeline(
        self,
        message: str,
        normalized: str,
        *,
        query_vector: list[float] | None = None,
        debug: bool = False,
        trace: TraceBuilder | None = None,
        profile: KnowledgeProfile | None = None,
    ) -> PipelineResult:
        """Order legacy adapters: prepare → assemble (EA) → finalize.

        Does not own Qdrant/DFP internals, prompts, or LLM calls.
        """
        rps = RetrievalPipelineService(
            self._db,
            self._settings,
            self._rag.embedding_service,
            self._rag.qdrant_service,
        )
        prepared = rps.prepare_query(
            message,
            normalized,
            query_vector=query_vector,
            profile=profile,
        )
        doc_result = rps.assemble_evidence(prepared)
        return rps.finalize_pipeline(
            prepared,
            doc_result,
            debug=debug,
            trace=trace,
            retrieval_coordinator=RETRIEVAL_COORDINATOR_REASONING,
        )

    @staticmethod
    def _wrap(legacy: RagResult) -> ReasoningResult:
        assessment = assess_evidence_sufficiency(legacy)
        diagnostics = build_reasoning_diagnostics(
            assessment, reasoning_path=REASONING_PATH_SERVICE
        )
        legacy.reasoning_path = REASONING_PATH_SERVICE
        legacy.reasoning_diagnostics = diagnostics
        # Derive a coarse information_need label from legacy signals (advisory).
        strategy = ""
        if isinstance(legacy.applied_knowledge_config, dict):
            strategy = str(legacy.applied_knowledge_config.get("answer_strategy") or "")
        information_need = legacy.query_intent or strategy or None
        return ReasoningResult(
            legacy_result=legacy,
            reasoning_path=REASONING_PATH_SERVICE,
            information_need=information_need,
            evidence_sufficient=assessment.evidence_sufficient,
            speech_act=None,  # Step 043: do not change speech act
            refusal_reason=None,
            clarification_needed=None,
            reasoning_diagnostics=diagnostics,
            sufficiency=assessment,
        )

    @staticmethod
    def _stamp_stream_final(data: dict) -> dict:
        """Attach path + sufficiency diagnostics without changing answer text."""
        response = data.get("response")
        answer_blob = response if isinstance(response, dict) else data

        # Reconstruct a minimal RagResult-shaped view for assessment.
        sources_raw = answer_blob.get("sources") or data.get("sources") or []
        from app.services.rag_service import RagSource

        sources = []
        for s in sources_raw:
            if isinstance(s, dict):
                sources.append(
                    RagSource(
                        title=s.get("title") or "",
                        url=s.get("url") or "",
                        source_type=s.get("source_type") or "page",
                        score=float(s.get("score") or 0.0),
                    )
                )
            else:
                sources.append(s)

        meta = answer_blob.get("metadata") or {}
        query_intent = "unknown"
        if isinstance(meta, dict):
            query_intent = meta.get("query_intent") or "unknown"
        applied = None
        if isinstance(meta, dict):
            applied = meta.get("applied_knowledge_config")

        stub = RagResult(
            answer=str(answer_blob.get("answer") or ""),
            sources=sources,
            used_context=bool(answer_blob.get("used_context", False)),
            request_id=str(data.get("request_id") or ""),
            query_intent=str(query_intent),
            applied_knowledge_config=applied if isinstance(applied, dict) else None,
        )
        assessment = assess_evidence_sufficiency(stub)
        diagnostics = build_reasoning_diagnostics(
            assessment, reasoning_path=REASONING_PATH_SERVICE
        )

        stamped = {**data, "reasoning_path": REASONING_PATH_SERVICE}
        debug_blob = stamped.get("retrieval_debug")
        if isinstance(debug_blob, dict):
            stamped["retrieval_debug"] = {
                **debug_blob,
                "reasoning_path": REASONING_PATH_SERVICE,
                "reasoning_diagnostics": diagnostics,
                "evidence_sufficiency": diagnostics["evidence_sufficiency"],
            }
        else:
            stamped["evidence_sufficiency"] = diagnostics["evidence_sufficiency"]
            stamped["reasoning_diagnostics"] = diagnostics

        if isinstance(response, dict):
            stamped["response"] = {
                **response,
                "reasoning_path": REASONING_PATH_SERVICE,
            }
        return stamped
