"""ExecutiveService — orchestration entry point (MIG-001 / RFC-100 Step 001).

Passthrough shell: delegates to legacy RagService / RagStreamingService with no
orchestration policy yet. Wiring behind ``knowledge_os_executive_enabled`` is
Step 002 (non-stream) and Step 003 (stream).
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.services.chat_response_builder import DiagnosticsCollector
from app.services.rag_service import RagResult, RagService
from app.services.rag_streaming import RagStreamingService


class ExecutiveService:
    """Coordinate chat workflows; sole global orchestration authority (v1 spec §2.1).

    Step 001 scope: interface only — ``answer`` and ``answer_stream`` delegate
    unchanged to the existing RAG path. No epistemic state, no refusal policy,
    no maintenance coordination yet.
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
        """Non-streaming chat — passthrough to RagService.answer."""
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
        """Streaming chat — passthrough to RagStreamingService.iter_events."""
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
