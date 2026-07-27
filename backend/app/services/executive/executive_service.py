"""ExecutiveService — orchestration entry point (MIG-001 / RFC-100 Step 001).

Passthrough shell: delegates to ReasoningService (Step 039, flag-gated) or
legacy RagService / RagStreamingService. No epistemic state ownership.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.services.chat_response_builder import DiagnosticsCollector
from app.services.feature_flags import reasoning_service_enabled
from app.services.rag_service import RagResult, RagService
from app.services.rag_streaming import RagStreamingService
from app.services.reasoning import ReasoningService


class ExecutiveService:
    """Coordinate chat workflows; sole global orchestration authority (v1 spec §2.1).

    Step 001: interface — ``answer`` / ``answer_stream`` delegate to RAG.
    Step 039: optional ReasoningService seam when ``reasoning_service_enabled``.
    """

    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._rag = RagService(db, settings)
        self._streaming = RagStreamingService(self._rag)

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
        """Non-streaming chat — ReasoningService or RagService passthrough."""
        if reasoning_service_enabled():
            return ReasoningService(self._db, self._settings).answer(
                message,
                session_id,
                request_id=request_id,
                user_ip=user_ip,
                user_agent=user_agent,
                referrer=referrer,
                debug=debug,
                bypass_cache=bypass_cache,
            )
        return self._rag.answer(
            message,
            session_id,
            request_id=request_id,
            user_ip=user_ip,
            user_agent=user_agent,
            referrer=referrer,
            debug=debug,
            bypass_cache=bypass_cache,
        )

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
        """Streaming chat — ReasoningService or RagStreamingService passthrough."""
        if reasoning_service_enabled():
            yield from ReasoningService(self._db, self._settings).answer_stream(
                message,
                session_id,
                request_id=request_id,
                collector=collector,
                user_ip=user_ip,
                user_agent=user_agent,
                referrer=referrer,
                debug=debug,
                bypass_cache=bypass_cache,
            )
            return
        yield from self._streaming.iter_events(
            message,
            session_id,
            request_id=request_id,
            collector=collector,
            user_ip=user_ip,
            user_agent=user_agent,
            referrer=referrer,
            debug=debug,
            bypass_cache=bypass_cache,
        )
