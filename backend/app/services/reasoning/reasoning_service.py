"""ReasoningService — stateless reasoning seam (RFC-100 Steps 039–045).

Step 039: passthrough facade over Rag.
Step 041: when Evidence Assembly is also enabled, Reasoning owns the order of
legacy RPS adapters (prepare → assemble → finalize) and injects the result into
Rag so retrieval/LLM each run once. Language remains in Rag.
Step 043: advisory evidence-sufficiency assessment.
Step 044: advisory speech-act selection (answer/qualify/clarify/refuse).
Step 045: when REASONING_SPEECH_ACTS_ENABLED, Language consumes the typed act
         (Reasoning still selects; Language renders). Flag is independently
         rollbackable and has no effect when Reasoning is OFF.

Does not store knowledge, mutate Epistemic Memory, or render final language.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.chat_response_builder import DiagnosticsCollector
from app.services.feature_flags import (
    evidence_assembly_enabled,
    memory_evidence_assist_enabled,
    reasoning_speech_acts_enabled,
)
from app.services.reasoning.memory_assist_policy import MemoryAssistPolicy
from app.services.reasoning.memory_canonical_shadow_comparator import (
    MemoryCanonicalShadowComparator,
)
from app.services.rag_service import RagResult, RagService
from app.services.rag_streaming import RagStreamingService
from app.services.reasoning.evidence_sufficiency import (
    assess_evidence_sufficiency,
    build_reasoning_diagnostics,
    enrich_assessment_with_memory_assist,
)
from app.services.reasoning.speech_act import SpeechActDecision, select_speech_act
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
        Steps 043–044: sufficiency + speech act assessed after legacy answer —
        advisory only when speech-acts flag OFF (answer text unchanged).
        Step 045: when speech-acts flag ON, Rag Language applies the act
        (clarify/refuse may skip LLM).
        """
        provider = (
            self._coordinate_pipeline
            if self._uses_coordination_pipeline()
            else None
        )
        apply_speech = reasoning_speech_acts_enabled()
        apply_memory = memory_evidence_assist_enabled(self._settings)
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
            apply_speech_acts=apply_speech,
            apply_memory_assist=apply_memory,
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
        """Streaming path — same coordinator rules; stamp diagnostics on final."""
        provider = (
            self._coordinate_pipeline
            if self._uses_coordination_pipeline()
            else None
        )
        apply_speech = reasoning_speech_acts_enabled()
        apply_memory = memory_evidence_assist_enabled(self._settings)
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
            apply_speech_acts=apply_speech,
            apply_memory_assist=apply_memory,
        ):
            if event == "final" and isinstance(data, dict):
                data = self._stamp_stream_final(data)
            yield event, data

    def _uses_coordination_pipeline(self) -> bool:
        if evidence_assembly_enabled():
            return True
        return memory_evidence_assist_enabled(self._settings)

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
        memory_assist = MemoryAssistPolicy(self._db).attempt(prepared, self._settings)
        prepared = prepared.with_memory_assist(memory_assist)
        doc_result = rps.assemble_evidence(prepared)
        pipe_result = rps.finalize_pipeline(
            prepared,
            doc_result,
            debug=debug,
            trace=trace,
            retrieval_coordinator=RETRIEVAL_COORDINATOR_REASONING,
        )
        shadow = MemoryCanonicalShadowComparator().compare_pipeline(
            self._settings,
            memory_assist,
            prepared,
            doc_result,
            pipe_result,
        )
        return pipe_result.with_canonical_shadow(shadow)

    @staticmethod
    def _wrap(legacy: RagResult) -> ReasoningResult:
        existing = dict(legacy.reasoning_diagnostics or {})
        if existing.get("speech_act_applied"):
            return ReasoningService._wrap_applied(legacy, existing)

        assessment = assess_evidence_sufficiency(legacy)
        memory_assist = getattr(legacy, "memory_assist", None)
        canonical_shadow = getattr(legacy, "canonical_shadow", None)
        assessment = enrich_assessment_with_memory_assist(assessment, memory_assist)
        strategy = ""
        if isinstance(legacy.applied_knowledge_config, dict):
            strategy = str(legacy.applied_knowledge_config.get("answer_strategy") or "")
        information_need = legacy.query_intent or strategy or None
        decision = select_speech_act(assessment, information_need=information_need)
        diagnostics = build_reasoning_diagnostics(
            assessment,
            reasoning_path=REASONING_PATH_SERVICE,
            speech_act=decision,
            memory_assist=memory_assist,
            canonical_shadow=canonical_shadow,
        )
        legacy.reasoning_path = REASONING_PATH_SERVICE
        legacy.reasoning_diagnostics = diagnostics
        return ReasoningResult(
            legacy_result=legacy,
            reasoning_path=REASONING_PATH_SERVICE,
            information_need=information_need,
            evidence_sufficient=assessment.evidence_sufficient,
            speech_act=decision.speech_act,
            refusal_reason=decision.refusal_reason,
            clarification_needed=decision.clarification_required,
            reasoning_diagnostics=diagnostics,
            sufficiency=assessment,
            speech_act_decision=decision,
        )

    @staticmethod
    def _wrap_applied(legacy: RagResult, existing: dict) -> ReasoningResult:
        """Preserve Language-applied speech act (do not re-decide from cleared sources)."""
        act_blob = existing.get("speech_act") or {}
        decision = SpeechActDecision(
            speech_act=act_blob.get("speech_act") or "answer",
            speech_act_reason=str(
                act_blob.get("speech_act_reason")
                or existing.get("speech_act_reason")
                or "applied"
            ),
            user_message_hint=str(
                act_blob.get("user_message_hint")
                or existing.get("language_instruction")
                or "answer_normally"
            ),
            qualification_required=bool(act_blob.get("qualification_required")),
            clarification_question_hint=act_blob.get("clarification_question_hint"),
            refusal_reason=act_blob.get("refusal_reason"),
        )
        steps = list(existing.get("understanding_steps") or [])
        if not any(s.get("phase") == "speech_act_rendered" for s in steps):
            steps.append(
                {
                    "phase": "speech_act_rendered",
                    "status": "completed",
                    "summary": (
                        f"Language instruction="
                        f"{existing.get('language_instruction')}; "
                        f"deterministic={existing.get('deterministic_response_used')}; "
                        f"llm_skipped={existing.get('llm_skipped')}."
                    ),
                }
            )
        diagnostics = {
            **existing,
            "reasoning_path": REASONING_PATH_SERVICE,
            "understanding_steps": steps,
            "speech_act": decision.to_diagnostics(),
            "speech_act_reason": decision.speech_act_reason,
            "qualification_required": decision.qualification_required,
            "clarification_required": decision.clarification_required,
            "refusal_required": decision.refusal_required,
        }
        legacy.reasoning_path = REASONING_PATH_SERVICE
        legacy.reasoning_diagnostics = diagnostics

        sufficiency = None
        evidence_sufficient = None
        suf = existing.get("evidence_sufficiency")
        if isinstance(suf, dict):
            evidence_sufficient = suf.get("evidence_sufficient")

        strategy = ""
        if isinstance(legacy.applied_knowledge_config, dict):
            strategy = str(legacy.applied_knowledge_config.get("answer_strategy") or "")
        information_need = legacy.query_intent or strategy or None

        return ReasoningResult(
            legacy_result=legacy,
            reasoning_path=REASONING_PATH_SERVICE,
            information_need=information_need,
            evidence_sufficient=evidence_sufficient,
            speech_act=decision.speech_act,
            refusal_reason=decision.refusal_reason,
            clarification_needed=decision.clarification_required,
            reasoning_diagnostics=diagnostics,
            sufficiency=sufficiency,
            speech_act_decision=decision,
        )

    @staticmethod
    def _stamp_stream_final(data: dict) -> dict:
        """Attach path + sufficiency/speech-act diagnostics without clobbering applied Language."""
        response = data.get("response")
        answer_blob = response if isinstance(response, dict) else data

        existing_diag = None
        debug_blob = data.get("retrieval_debug")
        if isinstance(debug_blob, dict):
            existing_diag = debug_blob.get("reasoning_diagnostics")
        if not isinstance(existing_diag, dict):
            existing_diag = data.get("reasoning_diagnostics")
        if isinstance(existing_diag, dict) and existing_diag.get("speech_act_applied"):
            stamped = {**data, "reasoning_path": REASONING_PATH_SERVICE}
            if isinstance(debug_blob, dict):
                stamped["retrieval_debug"] = {
                    **debug_blob,
                    "reasoning_path": REASONING_PATH_SERVICE,
                    "reasoning_diagnostics": existing_diag,
                    "evidence_sufficiency": existing_diag.get("evidence_sufficiency"),
                    "speech_act": existing_diag.get("speech_act"),
                }
            else:
                stamped["reasoning_diagnostics"] = existing_diag
                stamped["speech_act"] = existing_diag.get("speech_act")
                if existing_diag.get("evidence_sufficiency") is not None:
                    stamped["evidence_sufficiency"] = existing_diag["evidence_sufficiency"]
            if isinstance(response, dict):
                stamped["response"] = {
                    **response,
                    "reasoning_path": REASONING_PATH_SERVICE,
                }
            return stamped

        # Reconstruct a minimal RagResult-shaped view for advisory assessment.
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
        applied = None
        if isinstance(meta, dict):
            query_intent = meta.get("query_intent") or "unknown"
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
        memory_assist = None
        canonical_shadow = None
        if isinstance(debug_blob, dict):
            memory_assist = debug_blob.get("memory_assist")
            canonical_shadow = debug_blob.get("memory_canonical_shadow")
        assessment = enrich_assessment_with_memory_assist(assessment, memory_assist)
        strategy = ""
        if isinstance(applied, dict):
            strategy = str(applied.get("answer_strategy") or "")
        information_need = str(query_intent) if query_intent else strategy or None
        decision = select_speech_act(assessment, information_need=information_need)
        diagnostics = build_reasoning_diagnostics(
            assessment,
            reasoning_path=REASONING_PATH_SERVICE,
            speech_act=decision,
            memory_assist=memory_assist,
            canonical_shadow=canonical_shadow,
        )

        stamped = {**data, "reasoning_path": REASONING_PATH_SERVICE}
        if isinstance(debug_blob, dict):
            stamped["retrieval_debug"] = {
                **debug_blob,
                "reasoning_path": REASONING_PATH_SERVICE,
                "reasoning_diagnostics": diagnostics,
                "evidence_sufficiency": diagnostics["evidence_sufficiency"],
                "speech_act": diagnostics.get("speech_act"),
            }
        else:
            stamped["evidence_sufficiency"] = diagnostics["evidence_sufficiency"]
            stamped["reasoning_diagnostics"] = diagnostics
            stamped["speech_act"] = diagnostics.get("speech_act")

        if isinstance(response, dict):
            stamped["response"] = {
                **response,
                "reasoning_path": REASONING_PATH_SERVICE,
            }
        return stamped
